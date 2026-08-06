"""Distribution-oriented XGBoost pipeline for cancer subtype prediction.

This runner deliberately avoids transcript/isoform knowledge and raw mutation-token
one-hot encoding.  It represents each sample using stable event families and
distribution/concentration statistics.  The canonical split is mandatory and every
support filter is fitted on the corresponding outer-training fold only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np
import pandas as pd
import yaml
from scipy import sparse
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.metrics import f1_score, log_loss
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier


NO_EVENT = {"", "WT", "WILDTYPE", "WILD_TYPE", "NA", "N/A", "NAN", "NONE"}
EXPECTED_EXPERIMENT_ID = "EXP-513"
FAMILIES = ("FRAMESHIFT", "STOP", "SPLICE", "SYNONYMOUS", "INDEL", "MISSENSE", "OTHER")
TRUNCATING = {"FRAMESHIFT", "STOP", "SPLICE"}
AA = "ACDEFGHIKLMNPQRSTVWY"
TOKEN_SPLIT = re.compile(r"[\s,;|]+")
SIMPLE_AA = re.compile(rf"^[{AA}](\d+)([{AA}])$", re.IGNORECASE)
STOP_TOKEN = re.compile(rf"^[{AA}]\d+(?:\*|X|TER)$", re.IGNORECASE)


@dataclass(frozen=True)
class FeatureBundle:
    matrix: sparse.csr_matrix
    names: tuple[str, ...]
    sample_ids: tuple[str, ...]
    qc: dict[str, Any]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("config 최상위는 mapping이어야 합니다.")
    return config


def is_no_event(value: object) -> bool:
    return str(value).strip().upper() in NO_EVENT


def split_tokens(value: object) -> tuple[str, ...]:
    text = str(value).strip().upper()
    if text in NO_EVENT:
        return ()
    return tuple(token for token in TOKEN_SPLIT.split(text) if token and token not in NO_EVENT)


def classify_token(token: str) -> str:
    value = token.upper()
    if "FRAME_SHIFT" in value or "FRAMESHIFT" in value or "FS" in value:
        return "FRAMESHIFT"
    if "NONSENSE" in value or "STOP_GAIN" in value or STOP_TOKEN.fullmatch(value):
        return "STOP"
    if "SPLICE" in value:
        return "SPLICE"
    if "SILENT" in value or "SYNONYMOUS" in value:
        return "SYNONYMOUS"
    match = SIMPLE_AA.fullmatch(value)
    if match:
        return "SYNONYMOUS" if value[0] == match.group(2).upper() else "MISSENSE"
    if any(mark in value for mark in ("DELINS", "IN_FRAME", "INFRAME", "INS", "DEL")):
        return "INDEL"
    if "MISSENSE" in value or re.match(rf"^[{AA}]\d+[{AA}]", value):
        return "MISSENSE"
    return "OTHER"


def _gini(nonnegative: np.ndarray) -> float:
    values = nonnegative[nonnegative > 0].astype(np.float64)
    if values.size <= 1:
        return 0.0
    values.sort()
    ranks = np.arange(1, values.size + 1, dtype=np.float64)
    return float((2.0 * np.dot(ranks, values) / values.sum() - values.size - 1) / values.size)


def concentration_statistics(counts: np.ndarray) -> tuple[float, float, float, float, float, float]:
    positive = counts[counts > 0].astype(np.float64)
    if positive.size == 0:
        return (0.0,) * 6
    probabilities = positive / positive.sum()
    ordered = np.sort(probabilities)[::-1]
    entropy = -float(np.sum(probabilities * np.log(probabilities + 1e-12)))
    normalized_entropy = entropy / math.log(positive.size) if positive.size > 1 else 0.0
    return (
        float(np.sum(probabilities**2)),
        normalized_entropy,
        float(ordered[0]),
        float(ordered[:3].sum()),
        float(ordered[:5].sum()),
        _gini(positive),
    )


def build_features(frame: pd.DataFrame, gene_columns: list[str], cfg: dict[str, Any]) -> FeatureBundle:
    row_count = len(frame)
    gene_count = len(gene_columns)
    family_index = {name: index for index, name in enumerate(FAMILIES)}
    gene_events = np.zeros((row_count, gene_count), dtype=np.uint8)
    family_counts = np.zeros((row_count, len(FAMILIES)), dtype=np.uint16)
    unique_tokens: list[set[str]] = [set() for _ in range(row_count)]
    repeated_tokens = np.zeros(row_count, dtype=np.uint16)
    truncating_gene_count = np.zeros(row_count, dtype=np.uint16)
    missing_count = np.zeros(row_count, dtype=np.uint16)

    presence_rows: list[int] = []
    presence_cols: list[int] = []
    event_data: list[float] = []
    trunc_rows: list[int] = []
    trunc_cols: list[int] = []
    multi_rows: list[int] = []
    multi_cols: list[int] = []
    raw_event_count = 0

    for gene_idx, gene in enumerate(gene_columns):
        values = frame[gene].to_numpy(dtype=object)
        for row_idx, raw_value in enumerate(values):
            raw_text = str(raw_value).strip()
            if raw_text == "":
                missing_count[row_idx] += 1
            tokens = split_tokens(raw_value)
            if not tokens:
                continue
            event_n = min(len(tokens), int(cfg["count_clip"]))
            gene_events[row_idx, gene_idx] = event_n
            presence_rows.append(row_idx)
            presence_cols.append(gene_idx)
            event_data.append(float(event_n))
            if event_n >= 2:
                multi_rows.append(row_idx)
                multi_cols.append(gene_idx)
            seen_here: Counter[str] = Counter(tokens)
            repeated_tokens[row_idx] += sum(count - 1 for count in seen_here.values())
            unique_tokens[row_idx].update(tokens)
            has_truncating = False
            for token in tokens:
                family = classify_token(token)
                family_counts[row_idx, family_index[family]] += 1
                has_truncating |= family in TRUNCATING
                raw_event_count += 1
            if has_truncating:
                trunc_rows.append(row_idx)
                trunc_cols.append(gene_idx)
                truncating_gene_count[row_idx] += 1

    ones = np.ones(len(presence_rows), dtype=np.float32)
    shape = (row_count, gene_count)
    blocks: list[sparse.csr_matrix] = []
    names: list[str] = []
    if cfg["include_gene_presence"]:
        blocks.append(sparse.csr_matrix((ones, (presence_rows, presence_cols)), shape=shape))
        names.extend(f"gene_presence__{gene}" for gene in gene_columns)
    if cfg["include_gene_event_count"]:
        values = np.log1p(np.asarray(event_data, dtype=np.float32))
        blocks.append(sparse.csr_matrix((values, (presence_rows, presence_cols)), shape=shape))
        names.extend(f"gene_log_event_count__{gene}" for gene in gene_columns)
    if cfg["include_gene_truncating_presence"]:
        blocks.append(sparse.csr_matrix((np.ones(len(trunc_rows)), (trunc_rows, trunc_cols)), shape=shape))
        names.extend(f"gene_truncating__{gene}" for gene in gene_columns)
    if cfg["include_gene_multi_event_presence"]:
        blocks.append(sparse.csr_matrix((np.ones(len(multi_rows)), (multi_rows, multi_cols)), shape=shape))
        names.extend(f"gene_multi_event__{gene}" for gene in gene_columns)

    summary_names = [
        "sample__mutated_gene_count", "sample__raw_event_count", "sample__unique_token_count",
        "sample__repeated_token_count", "sample__singleton_gene_count", "sample__multi_event_gene_count",
        "sample__truncating_gene_count", "sample__missing_cell_count", "sample__mean_events_per_mutated_gene",
        "sample__std_events_per_mutated_gene", "sample__max_events_in_gene", "sample__event_hhi",
        "sample__event_normalized_entropy", "sample__top1_event_share", "sample__top3_event_share",
        "sample__top5_event_share", "sample__event_gini",
    ]
    summary_names += [f"sample__{family.lower()}_count" for family in FAMILIES]
    summary_names += [f"sample__{family.lower()}_ratio" for family in FAMILIES]
    summary = np.zeros((row_count, len(summary_names)), dtype=np.float32)
    for row_idx in range(row_count):
        counts = gene_events[row_idx]
        positive = counts[counts > 0].astype(np.float32)
        mutated = int(positive.size)
        total = int(positive.sum())
        summary[row_idx, :17] = (
            mutated, total, len(unique_tokens[row_idx]), repeated_tokens[row_idx],
            int(np.sum(positive == 1)), int(np.sum(positive >= 2)), truncating_gene_count[row_idx],
            missing_count[row_idx], float(positive.mean()) if mutated else 0.0,
            float(positive.std()) if mutated else 0.0, float(positive.max()) if mutated else 0.0,
            *concentration_statistics(counts),
        )
        summary[row_idx, 17:17 + len(FAMILIES)] = family_counts[row_idx]
        denominator = max(int(family_counts[row_idx].sum()), 1)
        summary[row_idx, 17 + len(FAMILIES):] = family_counts[row_idx] / denominator
    blocks.append(sparse.csr_matrix(summary))
    names.extend(summary_names)
    matrix = sparse.hstack(blocks, format="csr", dtype=np.float32)
    return FeatureBundle(
        matrix=matrix,
        names=tuple(names),
        sample_ids=tuple(frame["ID"].astype(str)),
        qc={
            "sample_count": row_count,
            "gene_count": gene_count,
            "feature_count": matrix.shape[1],
            "matrix_nnz": int(matrix.nnz),
            "non_wt_cell_count": len(presence_rows),
            "raw_event_count": raw_event_count,
            "family_occurrences": dict(zip(FAMILIES, family_counts.sum(axis=0).astype(int).tolist())),
        },
    )


def select_supported_features(matrix: sparse.csr_matrix, train_indices: np.ndarray, minimum: int) -> np.ndarray:
    support = np.asarray((matrix[train_indices] != 0).sum(axis=0)).ravel()
    selected = np.flatnonzero(support >= minimum)
    if selected.size == 0:
        raise RuntimeError("support 조건을 만족하는 특징이 없습니다.")
    return selected


def sample_weights(y: np.ndarray, power: float) -> np.ndarray:
    counts = np.bincount(y)
    base = len(y) / (len(counts) * counts)
    weights = np.power(base[y], power)
    return (weights / weights.mean()).astype(np.float32)


def resolve_folds(split: pd.DataFrame, train: pd.DataFrame, fold_column: str) -> np.ndarray:
    if fold_column not in split.columns:
        candidates = [column for column in split.columns if column.lower() in {"fold", "fold_id", "canonical_fold"}]
        if len(candidates) != 1:
            raise ValueError(f"canonical fold 열을 찾지 못했습니다: {split.columns.tolist()}")
        fold_column = candidates[0]
    if "ID" in split.columns:
        mapping = split.set_index("ID")[fold_column]
        if set(train["ID"].astype(str)) != set(mapping.index.astype(str)):
            raise ValueError("canonical split ID와 train ID 집합이 다릅니다.")
        return train["ID"].astype(str).map(mapping).to_numpy(dtype=int)
    if len(split) != len(train):
        raise ValueError("canonical split 행 수가 train과 다릅니다.")
    return split[fold_column].to_numpy(dtype=int)


def make_model(config: dict[str, Any], num_class: int, seed: int) -> XGBClassifier:
    return XGBClassifier(
        objective="multi:softprob", num_class=num_class,
        n_estimators=config["n_estimators"], learning_rate=config["learning_rate"],
        max_depth=config["max_depth"], min_child_weight=config["min_child_weight"],
        subsample=config["subsample"], colsample_bytree=config["colsample_bytree"],
        reg_alpha=config["reg_alpha"], reg_lambda=config["reg_lambda"], gamma=config["gamma"],
        eval_metric="mlogloss", early_stopping_rounds=config["early_stopping_rounds"],
        tree_method=config["tree_method"], device=config["device"], n_jobs=config["n_jobs"],
        random_state=seed, verbosity=0,
    )


def main(config_path: Path) -> None:
    config = load_config(config_path)

    declared_experiment_id = config.get("experiment_id")
    runtime_experiment_id = config.get("experiment", {}).get("id")

    if declared_experiment_id != EXPECTED_EXPERIMENT_ID:
        raise ValueError(
            "config experiment_id가 runner와 다릅니다: "
            f"{declared_experiment_id!r} != "
            f"{EXPECTED_EXPERIMENT_ID!r}"
        )

    if runtime_experiment_id != EXPECTED_EXPERIMENT_ID:
        raise ValueError(
            "config experiment.id가 runner와 다릅니다: "
            f"{runtime_experiment_id!r} != "
            f"{EXPECTED_EXPERIMENT_ID!r}"
        )

    root = Path.cwd()
    data_cfg, feature_cfg = config["data"], config["features"]
    train_path, test_path = root / data_cfg["train_path"], root / data_cfg["test_path"]
    sample_path, split_path = root / data_cfg["sample_submission_path"], root / data_cfg["canonical_split_path"]
    for path in (train_path, test_path, sample_path, split_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    actual_sha = sha256_file(split_path)
    if actual_sha != data_cfg["canonical_split_sha256"]:
        raise RuntimeError(f"canonical split SHA 불일치: {actual_sha}")

    train = pd.read_csv(train_path, dtype=str, keep_default_na=False)
    test = pd.read_csv(test_path, dtype=str, keep_default_na=False)
    sample = pd.read_csv(sample_path, dtype=str, keep_default_na=False)
    if len(train) != data_cfg["expected_train_rows"] or len(test) != data_cfg["expected_test_rows"]:
        raise ValueError("데이터 행 수가 config 계약과 다릅니다.")
    excluded = {data_cfg["id_column"], data_cfg["target_column"]}
    genes = [column for column in train.columns if column not in excluded]
    if genes != [column for column in test.columns if column != data_cfg["id_column"]]:
        raise ValueError("train/test 유전자 열 이름 또는 순서가 다릅니다.")

    print(json.dumps({"stage": "feature_build", "genes": len(genes)}, ensure_ascii=False), flush=True)
    train_features = build_features(train, genes, feature_cfg)
    test_features = build_features(test, genes, feature_cfg)
    if train_features.names != test_features.names:
        raise RuntimeError("train/test 특징 이름이 다릅니다.")

    encoder = LabelEncoder()
    y = encoder.fit_transform(train[data_cfg["target_column"]])
    if len(encoder.classes_) != data_cfg["expected_classes"]:
        raise ValueError("클래스 수가 config 계약과 다릅니다.")
    split = pd.read_csv(split_path, dtype={"ID": str})
    folds = resolve_folds(split, train, data_cfg["fold_column"])
    if sorted(np.unique(folds).tolist()) != [0, 1, 2, 3, 4]:
        raise ValueError("canonical split은 정확히 0~4 fold여야 합니다.")

    output_cfg = config["output"]
    report_dir, model_dir = root / output_cfg["report_dir"], root / output_cfg["model_dir"]
    report_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)
    oof = np.zeros((len(train), len(encoder.classes_)), dtype=np.float32)
    test_probability = np.zeros((len(test), len(encoder.classes_)), dtype=np.float64)
    fold_metrics: list[dict[str, Any]] = []

    for fold in range(5):
        started = time.perf_counter()
        train_idx, valid_idx = np.flatnonzero(folds != fold), np.flatnonzero(folds == fold)
        selected = select_supported_features(train_features.matrix, train_idx, feature_cfg["minimum_fold_train_support"])
        model = make_model(config["training"], len(encoder.classes_), config["experiment"]["seed"] + fold)
        model.fit(
            train_features.matrix[train_idx][:, selected], y[train_idx],
            sample_weight=sample_weights(y[train_idx], config["training"]["class_weight_power"]),
            eval_set=[(train_features.matrix[valid_idx][:, selected], y[valid_idx])], verbose=False,
        )
        valid_probability = model.predict_proba(train_features.matrix[valid_idx][:, selected])
        oof[valid_idx] = valid_probability
        test_probability += model.predict_proba(test_features.matrix[:, selected]) / 5.0
        prediction = valid_probability.argmax(axis=1)
        metrics = {
            "fold": fold, "macro_f1": f1_score(y[valid_idx], prediction, average="macro"),
            "accuracy": accuracy_score(y[valid_idx], prediction),
            "log_loss": log_loss(y[valid_idx], valid_probability, labels=np.arange(len(encoder.classes_))),
            "best_iteration": int(model.best_iteration), "selected_features": int(selected.size),
            "elapsed_seconds": time.perf_counter() - started,
        }
        fold_metrics.append(metrics)
        joblib.dump({"model": model, "selected": selected, "classes": encoder.classes_}, model_dir / f"fold_{fold:02d}.joblib")
        print(json.dumps(metrics, ensure_ascii=False), flush=True)

    oof_prediction = oof.argmax(axis=1)
    oof_metrics = {
        "macro_f1": f1_score(y, oof_prediction, average="macro"),
        "accuracy": accuracy_score(y, oof_prediction),
        "log_loss": log_loss(y, oof, labels=np.arange(len(encoder.classes_))),
        "classification_report": classification_report(y, oof_prediction, target_names=encoder.classes_, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(y, oof_prediction).tolist(),
    }
    metrics_document = {
        "experiment_id": config["experiment"]["id"], "status": "COMPLETED",
        "canonical_split_sha256": actual_sha, "folds": fold_metrics, "oof": oof_metrics,
        "feature_qc": {"train": train_features.qc, "test": test_features.qc},
        "test_used_for_fit": False,
    }
    (report_dir / "metrics.json").write_text(json.dumps(metrics_document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    np.savez_compressed(report_dir / "oof_probabilities.npz", probabilities=oof, labels=y, ids=np.asarray(train_features.sample_ids))
    np.savez_compressed(report_dir / "test_probabilities.npz", probabilities=test_probability, ids=np.asarray(test_features.sample_ids), classes=encoder.classes_)

    submission = sample.copy()
    if submission[data_cfg["id_column"]].astype(str).tolist() != list(test_features.sample_ids):
        raise ValueError("sample_submission과 test ID 순서가 다릅니다.")
    submission[data_cfg["target_column"]] = encoder.inverse_transform(test_probability.argmax(axis=1))
    submission_path = root / output_cfg["submission_path"]
    submission_path.parent.mkdir(parents=True, exist_ok=True)
    submission.to_csv(submission_path, index=False)
    print(json.dumps({"experiment_id": config["experiment"]["id"], "oof_macro_f1": oof_metrics["macro_f1"], "submission": str(submission_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config.yaml"))
    args = parser.parse_args()
    main(args.config)

