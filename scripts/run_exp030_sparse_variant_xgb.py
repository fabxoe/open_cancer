#!/usr/bin/env python
"""Official XGBoost runner for the open_cancer team repository.

Copy this file into the repository ``scripts/`` directory.  The runner derives
EXP-NNN from the current Issue branch, reads the persisted canonical split,
fits every preprocessing decision on fold-train only, writes the project
artifact layout, and reloads saved checkpoints to verify inference.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
import xgboost as xgb
import yaml
from scipy import sparse
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
)
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.hashing import sha256_file, sha256_lines
from open_cancer.paths import relative_posix
from open_cancer.validation import (
    validate_competition_data,
    validate_json_document,
    validate_submission,
)


CANONICAL_SPLIT_SHA256 = (
    "1a99b82e758948fdf70c014b8270b73f0de805cd2450d119fcb20c08a9b169cf"
)
EFFECT_TYPES = (
    "MISSENSE",
    "SYNONYMOUS",
    "STOP_GAIN",
    "FRAMESHIFT",
    "COMPLEX_REPLACEMENT",
    "DELETION",
    "NONSTANDARD",
)
EFFECT_TO_INDEX = {name: index for index, name in enumerate(EFFECT_TYPES)}

RE_SUBSTITUTION = re.compile(r"^([A-Z])(\d+)([A-Z])$")
RE_STOP_GAIN = re.compile(r"^([A-Z])(\d+)\*$")
RE_FRAMESHIFT = re.compile(r"^(?:[A-Z]+|-|\*)(\d+)fs$", re.IGNORECASE)
RE_COMPLEX = re.compile(r"^\d+_\d+[A-Z*]+>[A-Z*]+$")
RE_DELETION = re.compile(r"^(?:[A-Z]?)(\d+)del$", re.IGNORECASE)


def find_project_root() -> Path:
    """Find a checkout containing PROJECT_CONTEXT.md and src/open_cancer."""
    candidates = [Path.cwd(), *Path.cwd().parents, Path(__file__).resolve().parent]
    candidates.extend(Path(__file__).resolve().parents)
    for candidate in candidates:
        if (
            (candidate / "PROJECT_CONTEXT.md").is_file()
            and (candidate / "src" / "open_cancer").is_dir()
        ):
            return candidate.resolve()
    raise FileNotFoundError(
        "open_cancer 저장소 루트를 찾지 못했습니다. 이 파일을 저장소의 "
        "scripts/ 폴더로 복사한 뒤 저장소 루트에서 실행하세요."
    )


ROOT = find_project_root()
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
SAMPLE_SUBMISSION_PATH = ROOT / "data" / "raw" / "sample_submission.csv"
SPLIT_PATH = ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": relative_posix(path, ROOT),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def classify_event(token: str) -> str:
    """Classify notation conservatively without inventing HGVS information."""
    token = token.strip()
    if not token:
        return "NONSTANDARD"
    match = RE_SUBSTITUTION.fullmatch(token)
    if match:
        reference, _, alternate = match.groups()
        return "SYNONYMOUS" if reference == alternate else "MISSENSE"
    if RE_STOP_GAIN.fullmatch(token):
        return "STOP_GAIN"
    if RE_FRAMESHIFT.fullmatch(token) or "fs" in token.lower():
        return "FRAMESHIFT"
    if RE_COMPLEX.fullmatch(token):
        return "COMPLEX_REPLACEMENT"
    if RE_DELETION.fullmatch(token) or "del" in token.lower():
        return "DELETION"
    return "NONSTANDARD"


def feature_count(gene_count: int) -> int:
    return gene_count * (1 + len(EFFECT_TYPES)) + 2 + len(EFFECT_TYPES)


def feature_names(gene_columns: list[str]) -> list[str]:
    names = [f"gene__{gene}" for gene in gene_columns]
    for effect in EFFECT_TYPES:
        names.extend(f"gene_effect__{gene}__{effect}" for gene in gene_columns)
    names.extend(
        [
            "sample__mutated_gene_count",
            "sample__raw_event_count",
            *(f"sample__{effect.lower()}_event_count" for effect in EFFECT_TYPES),
        ]
    )
    return names


def build_sparse_features(
    csv_path: Path,
    gene_columns: list[str],
    *,
    chunk_size: int,
) -> tuple[sparse.csr_matrix, dict[str, Any]]:
    """Build deterministic notation features without using labels."""
    gene_count = len(gene_columns)
    summary_start = gene_count * (1 + len(EFFECT_TYPES))
    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    cache: dict[str, int] = {}
    effects: Counter[str] = Counter()
    row_offset = 0
    blank_cells = 0
    non_wt_cells = 0

    reader = pd.read_csv(
        csv_path,
        usecols=["ID", *gene_columns],
        dtype=str,
        keep_default_na=False,
        chunksize=chunk_size,
    )
    for chunk in reader:
        gene_values = chunk[gene_columns].to_numpy(dtype=object)
        blank_mask = gene_values == ""
        mutation_mask = (gene_values != "WT") & ~blank_mask
        locations = np.argwhere(mutation_mask)
        blank_cells += int(blank_mask.sum())
        non_wt_cells += int(len(locations))

        mutated_gene_count = np.zeros(len(chunk), dtype=np.float32)
        raw_event_count = np.zeros(len(chunk), dtype=np.float32)
        effect_counts = np.zeros(
            (len(chunk), len(EFFECT_TYPES)), dtype=np.float32
        )

        for local_row_raw, gene_index_raw in locations:
            local_row = int(local_row_raw)
            gene_index = int(gene_index_raw)
            global_row = row_offset + local_row
            raw_cell = str(gene_values[local_row, gene_index]).strip()
            if not raw_cell:
                continue

            rows.append(global_row)
            columns.append(gene_index)
            values.append(1.0)
            mutated_gene_count[local_row] += 1.0

            tokens = raw_cell.split()
            raw_event_count[local_row] += float(len(tokens))
            cell_effects: set[int] = set()
            for token in tokens:
                effect_index = cache.get(token)
                if effect_index is None:
                    effect_index = EFFECT_TO_INDEX[classify_event(token)]
                    cache[token] = effect_index
                effect = EFFECT_TYPES[effect_index]
                effects[effect] += 1
                effect_counts[local_row, effect_index] += 1.0
                cell_effects.add(effect_index)

            for effect_index in cell_effects:
                rows.append(global_row)
                columns.append((effect_index + 1) * gene_count + gene_index)
                values.append(1.0)

        for local_row in range(len(chunk)):
            summary = [
                float(mutated_gene_count[local_row]),
                float(raw_event_count[local_row]),
                *effect_counts[local_row].tolist(),
            ]
            for offset, value in enumerate(summary):
                if value:
                    rows.append(row_offset + local_row)
                    columns.append(summary_start + offset)
                    values.append(value)
        row_offset += len(chunk)

    matrix = sparse.coo_matrix(
        (
            np.asarray(values, dtype=np.float32),
            (
                np.asarray(rows, dtype=np.int32),
                np.asarray(columns, dtype=np.int32),
            ),
        ),
        shape=(row_offset, feature_count(gene_count)),
        dtype=np.float32,
    ).tocsr()
    matrix.sum_duplicates()
    matrix.sort_indices()
    metadata = {
        "file": csv_path.name,
        "sample_count": row_offset,
        "gene_count": gene_count,
        "feature_count": matrix.shape[1],
        "matrix_nnz": int(matrix.nnz),
        "non_wt_cell_count": non_wt_cells,
        "blank_cell_count": blank_cells,
        "blank_cell_policy": "treated as no recorded mutation",
        "unique_event_token_count": len(cache),
        "effect_occurrences": dict(sorted(effects.items())),
    }
    return matrix, metadata


def select_fold_features(
    matrix: sparse.csr_matrix,
    train_indices: np.ndarray,
    *,
    minimum_support: int,
) -> np.ndarray:
    """Fit an unsupervised support filter on fold-train rows only."""
    support = np.asarray(
        matrix[train_indices].getnnz(axis=0)
    ).ravel()
    selected = np.flatnonzero(support >= minimum_support).astype(np.int32)
    if not len(selected):
        raise ValueError("선택된 특징이 없습니다.")
    return selected


def default_config() -> dict[str, Any]:
    return {
        "run_mode": "experiment",
        "slug": "xgb_canonical_effects",
        "seed": 42,
        "split": {
            "path": "data/splits/stratified_5fold_seed42.csv",
            "n_splits": 5,
            "sha256": CANONICAL_SPLIT_SHA256,
        },
        "features": {
            "chunk_size": 256,
            "minimum_fold_train_support": 1,
            "blank_cell_policy": "treated as no recorded mutation",
            "types": [
                "mutation_presence",
                "gene_by_effect",
                "sample_mutation_counts",
            ],
        },
        "model": {
            "objective": "multi:softprob",
            "n_estimators": 3000,
            "learning_rate": 0.03,
            "max_depth": 6,
            "min_child_weight": 2.0,
            "subsample": 0.8,
            "colsample_bytree": 0.6,
            "reg_alpha": 0.05,
            "reg_lambda": 2.0,
            "gamma": 0.0,
            "max_bin": 256,
            "eval_metric": "mlogloss",
            "early_stopping_rounds": 100,
            "tree_method": "hist",
            "device": "cpu",
            "n_jobs": 8,
            "verbosity": 0,
        },
        "training": {
            "balanced_sample_weight": True,
            "test_used_for_fit": False,
            "postprocessing": "none",
        },
    }


def validate_config(config: dict[str, Any]) -> None:
    if config.get("run_mode") != "experiment":
        raise ValueError("공식 runner의 run_mode는 experiment여야 합니다.")
    if not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", str(config.get("slug", ""))):
        raise ValueError("slug는 소문자·숫자·밑줄만 사용하세요.")
    if config["split"]["path"] != "data/splits/stratified_5fold_seed42.csv":
        raise ValueError("공식 비교 실험은 canonical split 경로를 사용해야 합니다.")
    if int(config["split"]["n_splits"]) != 5:
        raise ValueError("canonical split의 fold 수는 5입니다.")
    if config["split"].get("sha256") != CANONICAL_SPLIT_SHA256:
        raise ValueError("config의 canonical split SHA-256이 올바르지 않습니다.")
    if config["training"].get("postprocessing") != "none":
        raise ValueError("후처리는 이 baseline 실험 범위에 포함되지 않습니다.")


def make_paths(artifact_slug: str) -> dict[str, Path]:
    report_dir = ROOT / "reports" / artifact_slug
    reproducibility_dir = ROOT / "reproducibility" / artifact_slug
    return {
        "config": ROOT / "configs" / f"{artifact_slug}.yaml",
        "processed": ROOT / "data" / "processed" / artifact_slug,
        "models": ROOT / "models" / artifact_slug,
        "oof": ROOT / "oof" / f"{artifact_slug}.csv",
        "test_probability": ROOT / "preds" / f"{artifact_slug}_test_proba.csv",
        "submission": ROOT / "submissions" / f"{artifact_slug}.csv",
        "report_dir": report_dir,
        "metrics": report_dir / "metrics.json",
        "report": report_dir / "README.md",
        "reproducibility": reproducibility_dir,
        "resolved_config": reproducibility_dir / "config.resolved.yaml",
    }


def initialize_config(context: Any) -> Path:
    artifact_slug = f"{context.artifact_prefix}_xgb_canonical_effects"
    path = ROOT / "configs" / f"{artifact_slug}.yaml"
    if path.exists():
        raise FileExistsError(f"이미 config가 있습니다: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(default_config(), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
        newline="\n",
    )
    print(f"생성: {relative_posix(path, ROOT)}")
    print(
        "다음 단계: 이 runner를 "
        f"scripts/run_{artifact_slug}.py 로 복사하고 config와 함께 commit하세요."
    )
    return path


def load_fold_assignments(train_ids: pd.Series) -> np.ndarray:
    if sha256_file(SPLIT_PATH) != CANONICAL_SPLIT_SHA256:
        raise ValueError(
            "canonical split SHA-256이 다릅니다. 줄바꿈 변환이나 파일 수정을 "
            "확인하세요."
        )
    split = pd.read_csv(SPLIT_PATH, dtype={"ID": str, "fold": int})
    if split["ID"].duplicated().any():
        raise ValueError("canonical split ID가 중복됩니다.")
    if set(split["ID"]) != set(train_ids):
        raise ValueError("canonical split과 train의 ID 집합이 다릅니다.")
    assignments = train_ids.map(split.set_index("ID")["fold"])
    if assignments.isna().any():
        raise ValueError("fold를 찾을 수 없는 train ID가 있습니다.")
    assignments = assignments.to_numpy(dtype=np.int8)
    counts = dict(
        pd.Series(assignments).value_counts().sort_index().astype(int)
    )
    expected = {0: 1241, 1: 1240, 2: 1240, 3: 1240, 4: 1240}
    if counts != expected:
        raise ValueError(f"canonical fold 개수가 다릅니다: {counts}")
    return assignments


def build_resolved_config(
    *,
    context: Any,
    owner: str,
    source_commit: str,
    started_at: str,
    config: dict[str, Any],
    gene_columns: list[str],
    paths: dict[str, Path],
    feature_metadata: dict[str, Any],
    best_iterations: list[int],
) -> dict[str, Any]:
    return {
        "experiment": {
            "issue_number": context.issue_number,
            "experiment_id": context.experiment_id,
            "branch": context.branch,
            "owner": owner,
            "source_commit": source_commit,
            "dirty_worktree": False,
            "started_at": started_at,
        },
        "data": {
            "train": {
                "path": relative_posix(TRAIN_PATH, ROOT),
                "sha256": sha256_file(TRAIN_PATH),
            },
            "test": {
                "path": relative_posix(TEST_PATH, ROOT),
                "sha256": sha256_file(TEST_PATH),
            },
            "sample_submission": {
                "path": relative_posix(SAMPLE_SUBMISSION_PATH, ROOT),
                "sha256": sha256_file(SAMPLE_SUBMISSION_PATH),
            },
            "class_order": list(CLASS_LABELS),
        },
        "split": {
            "path": relative_posix(SPLIT_PATH, ROOT),
            "n_splits": 5,
            "sha256": sha256_file(SPLIT_PATH),
            "method": "persisted StratifiedKFold assignment",
            "shuffle": True,
            "seed": 42,
        },
        "features": {
            "target_used_for_features": False,
            "test_used_for_feature_fit": False,
            "gene_count": len(gene_columns),
            "gene_order_sha256": sha256_lines(gene_columns),
            "effect_types": list(EFFECT_TYPES),
            "feature_count_before_fold_filter": feature_metadata["train"][
                "feature_count"
            ],
            "minimum_fold_train_support": config["features"][
                "minimum_fold_train_support"
            ],
            "fold_filter_fit_scope": "fold_train_only",
            "blank_cell_policy": config["features"]["blank_cell_policy"],
        },
        "feature_outputs": {
            name: file_record(paths["processed"] / name)
            for name in (
                "train_features.npz",
                "test_features.npz",
                "train_ids.csv",
                "test_ids.csv",
                "train_labels.csv",
                "feature_names.json",
                "metadata.json",
            )
        },
        "model": {
            "class": "xgboost.XGBClassifier",
            "parameters": {
                **config["model"],
                "num_class": len(CLASS_LABELS),
            },
        },
        "training": {
            **config["training"],
            "fold_seeds": [
                int(config["seed"]) + fold for fold in range(5)
            ],
            "best_iterations": best_iterations,
            "command": (
                f"uv run python scripts/run_{paths['models'].name}.py "
                f"--config {relative_posix(paths['config'], ROOT)}"
            ),
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "xgboost": xgb.__version__,
            "pythonhashseed": os.environ.get("PYTHONHASHSEED"),
            "uv_lock_sha256": (
                sha256_file(ROOT / "uv.lock")
                if (ROOT / "uv.lock").is_file()
                else None
            ),
        },
    }


def save_processed_features(
    *,
    paths: dict[str, Path],
    train_features: sparse.csr_matrix,
    test_features: sparse.csr_matrix,
    train_ids: pd.Series,
    test_ids: pd.Series,
    labels: pd.Series,
    names: list[str],
    metadata: dict[str, Any],
) -> None:
    output = paths["processed"]
    output.mkdir(parents=True, exist_ok=True)
    sparse.save_npz(output / "train_features.npz", train_features)
    sparse.save_npz(output / "test_features.npz", test_features)
    pd.DataFrame({"ID": train_ids}).to_csv(
        output / "train_ids.csv", index=False, lineterminator="\n"
    )
    pd.DataFrame({"ID": test_ids}).to_csv(
        output / "test_ids.csv", index=False, lineterminator="\n"
    )
    pd.DataFrame({"ID": train_ids, "SUBCLASS": labels}).to_csv(
        output / "train_labels.csv", index=False, lineterminator="\n"
    )
    write_json(output / "feature_names.json", names)
    write_json(output / "metadata.json", metadata)


def train_models(
    *,
    config: dict[str, Any],
    paths: dict[str, Path],
    train_features: sparse.csr_matrix,
    test_features: sparse.csr_matrix,
    labels: pd.Series,
    fold_assignments: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    class_to_index = {label: index for index, label in enumerate(CLASS_LABELS)}
    try:
        y = labels.map(class_to_index).to_numpy(dtype=np.int32)
    except (TypeError, ValueError) as error:
        raise ValueError("고정 클래스에 없는 SUBCLASS가 있습니다.") from error
    if np.any(pd.isna(labels.map(class_to_index))):
        raise ValueError("고정 클래스에 없는 SUBCLASS가 있습니다.")

    oof = np.zeros((len(labels), len(CLASS_LABELS)), dtype=np.float32)
    test_probability = np.zeros(
        (test_features.shape[0], len(CLASS_LABELS)), dtype=np.float64
    )
    filled = np.zeros(len(labels), dtype=np.int8)
    fold_metrics: list[dict[str, Any]] = []
    paths["models"].mkdir(parents=True, exist_ok=True)

    base_parameters = {
        **config["model"],
        "num_class": len(CLASS_LABELS),
    }
    minimum_support = int(
        config["features"]["minimum_fold_train_support"]
    )
    for fold in range(5):
        train_indices = np.flatnonzero(fold_assignments != fold)
        valid_indices = np.flatnonzero(fold_assignments == fold)
        selected = select_fold_features(
            train_features,
            train_indices,
            minimum_support=minimum_support,
        )
        x_train = train_features[train_indices][:, selected]
        x_valid = train_features[valid_indices][:, selected]
        x_test = test_features[:, selected]
        y_train = y[train_indices]
        y_valid = y[valid_indices]
        weights = compute_sample_weight(class_weight="balanced", y=y_train)

        parameters = {
            **base_parameters,
            "random_state": int(config["seed"]) + fold,
        }
        model = xgb.XGBClassifier(**parameters)
        fold_started = time.perf_counter()
        model.fit(
            x_train,
            y_train,
            sample_weight=weights,
            eval_set=[(x_valid, y_valid)],
            verbose=False,
        )
        valid_probability = model.predict_proba(x_valid).astype(np.float32)
        oof[valid_indices] = valid_probability
        filled[valid_indices] += 1
        test_probability += (
            model.predict_proba(x_test).astype(np.float64) / 5.0
        )

        model.get_booster().set_attr(
            selected_feature_indices=",".join(map(str, selected.tolist()))
        )
        model_path = paths["models"] / f"fold_{fold:02d}.json"
        model.save_model(model_path)
        valid_prediction = valid_probability.argmax(axis=1)
        fold_row = {
            "fold": fold,
            "train_rows": int(len(train_indices)),
            "valid_rows": int(len(valid_indices)),
            "selected_features": int(len(selected)),
            "macro_f1": float(
                f1_score(y_valid, valid_prediction, average="macro")
            ),
            "accuracy": float(accuracy_score(y_valid, valid_prediction)),
            "log_loss": float(
                log_loss(y_valid, valid_probability, labels=range(26))
            ),
            "best_iteration": int(model.best_iteration),
            "elapsed_seconds": float(time.perf_counter() - fold_started),
        }
        fold_metrics.append(fold_row)
        print(json.dumps(fold_row, ensure_ascii=False))

    if not np.all(filled == 1):
        raise ValueError("각 train 행은 정확히 한 번 OOF 예측되어야 합니다.")
    if not np.allclose(oof.sum(axis=1), 1.0, atol=1e-5):
        raise ValueError("OOF 확률 행의 합이 1이 아닙니다.")
    if not np.allclose(test_probability.sum(axis=1), 1.0, atol=1e-5):
        raise ValueError("test 확률 행의 합이 1이 아닙니다.")
    return oof, test_probability.astype(np.float32), fold_metrics


def save_prediction_artifacts(
    *,
    paths: dict[str, Path],
    train_ids: pd.Series,
    test_ids: pd.Series,
    labels: pd.Series,
    fold_assignments: np.ndarray,
    oof: np.ndarray,
    test_probability: np.ndarray,
) -> None:
    class_array = np.asarray(CLASS_LABELS)
    oof_frame = pd.DataFrame(oof, columns=PROBABILITY_COLUMNS)
    oof_frame.insert(0, "FOLD", fold_assignments)
    oof_frame.insert(0, "SUBCLASS_PRED", class_array[oof.argmax(axis=1)])
    oof_frame.insert(0, "SUBCLASS_TRUE", labels.to_numpy())
    oof_frame.insert(0, "ID", train_ids.to_numpy())
    paths["oof"].parent.mkdir(parents=True, exist_ok=True)
    oof_frame.to_csv(paths["oof"], index=False, lineterminator="\n")

    test_frame = pd.DataFrame(
        test_probability, columns=PROBABILITY_COLUMNS
    )
    test_frame.insert(0, "ID", test_ids.to_numpy())
    paths["test_probability"].parent.mkdir(parents=True, exist_ok=True)
    test_frame.to_csv(
        paths["test_probability"], index=False, lineterminator="\n"
    )

    submission = pd.read_csv(
        SAMPLE_SUBMISSION_PATH, dtype=str, keep_default_na=False
    )
    submission["SUBCLASS"] = class_array[test_probability.argmax(axis=1)]
    paths["submission"].parent.mkdir(parents=True, exist_ok=True)
    submission.to_csv(
        paths["submission"], index=False, lineterminator="\n"
    )
    validate_submission(paths["submission"], TEST_PATH)


def calculate_metrics(
    *,
    context: Any,
    owner: str,
    source_commit: str,
    started_at: str,
    elapsed_seconds: float,
    config: dict[str, Any],
    paths: dict[str, Path],
    labels: pd.Series,
    oof: np.ndarray,
    fold_metrics: list[dict[str, Any]],
) -> dict[str, Any]:
    class_to_index = {label: index for index, label in enumerate(CLASS_LABELS)}
    y = labels.map(class_to_index).to_numpy(dtype=np.int32)
    prediction = oof.argmax(axis=1)
    report = classification_report(
        y,
        prediction,
        labels=range(26),
        target_names=CLASS_LABELS,
        output_dict=True,
        zero_division=0,
    )
    fold_scores = [row["macro_f1"] for row in fold_metrics]
    schema_fold_metrics = [
        {
            key: row[key]
            for key in (
                "fold",
                "macro_f1",
                "accuracy",
                "log_loss",
                "best_iteration",
            )
        }
        for row in fold_metrics
    ]
    return {
        "experiment_id": context.experiment_id,
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": context.issue_number,
        "parent_experiment": None,
        "git_commit": source_commit,
        "started_at": started_at,
        "finished_at": utc_now(),
        "primary_metric": "macro_f1",
        "split_id": config["split"]["path"],
        "folds": schema_fold_metrics,
        "oof": {
            "macro_f1": float(f1_score(y, prediction, average="macro")),
            "fold_mean": float(np.mean(fold_scores)),
            "fold_std": float(np.std(fold_scores)),
            "accuracy": float(accuracy_score(y, prediction)),
            "log_loss": float(log_loss(y, oof, labels=range(26))),
            "per_class_f1": {
                label: float(report[label]["f1-score"])
                for label in CLASS_LABELS
            },
            "confusion_matrix": confusion_matrix(
                y, prediction, labels=range(26)
            ).tolist(),
        },
        "leaderboard": None,
        "runtime": {
            "seconds": elapsed_seconds,
            "hardware": platform.platform(),
        },
        "artifacts": {
            "resolved_config": relative_posix(
                paths["resolved_config"], ROOT
            ),
            "oof": relative_posix(paths["oof"], ROOT),
            "test_probability": relative_posix(
                paths["test_probability"], ROOT
            ),
            "submission": relative_posix(paths["submission"], ROOT),
            "models": relative_posix(paths["models"], ROOT),
            "submission_sha256": sha256_file(paths["submission"]),
        },
        "notes": (
            "Canonical persisted split; notation-based sparse features; "
            "fold-train-only support filtering; no postprocessing."
        ),
    }


def write_report(
    *,
    context: Any,
    paths: dict[str, Path],
    metrics: dict[str, Any],
    config: dict[str, Any],
    fold_details: list[dict[str, Any]],
) -> None:
    paths["report_dir"].mkdir(parents=True, exist_ok=True)
    folds = "\n".join(
        (
            f"| {row['fold']} | {row['selected_features']} | "
            f"{row['macro_f1']:.6f} | {row['accuracy']:.6f} | "
            f"{row['log_loss']:.6f} | {row['best_iteration']} |"
        )
        for row in fold_details
    )
    paths["report"].write_text(
        (
            f"# {context.experiment_id}: XGBoost canonical effects\n\n"
            "## 실험 요약\n\n"
            "- 입력: 유전자 변이 유무, 유전자×변이 유형, 샘플별 변이 수\n"
            "- split: `data/splits/stratified_5fold_seed42.csv`\n"
            "- feature support 선택: 각 fold의 학습 행에서만 계산\n"
            "- test 사용: fold 모델 학습 완료 후 추론에만 사용\n"
            "- 후처리: 없음\n\n"
            "## 결과\n\n"
            f"- 전체 OOF Macro F1: {metrics['oof']['macro_f1']:.10f}\n"
            f"- Accuracy: {metrics['oof']['accuracy']:.10f}\n"
            f"- Log Loss: {metrics['oof']['log_loss']:.10f}\n"
            f"- Fold 표준편차: {metrics['oof']['fold_std']:.10f}\n\n"
            "| Fold | 선택 특징 | Macro F1 | Accuracy | Log Loss | Best iteration |\n"
            "|---:|---:|---:|---:|---:|---:|\n"
            f"{folds}\n\n"
            "## 재현성\n\n"
            "- 저장된 5개 checkpoint를 다시 불러와 test 추론을 반복했습니다.\n"
            "- 확률 허용 오차와 제출 라벨·SHA-256 일치를 검증했습니다.\n"
            f"- resolved config: `{relative_posix(paths['resolved_config'], ROOT)}`\n"
            f"- metrics: `{relative_posix(paths['metrics'], ROOT)}`\n"
            f"- minimum support: {config['features']['minimum_fold_train_support']}\n"
        ),
        encoding="utf-8",
        newline="\n",
    )


def verify_saved_inference(
    *,
    context: Any,
    owner: str,
    source_commit: str,
    paths: dict[str, Path],
    test_features: sparse.csr_matrix,
    test_ids: pd.Series,
    resolved_config: dict[str, Any],
    metrics: dict[str, Any],
) -> None:
    hash_records = [
        (
            ROOT / resolved_config["data"]["train"]["path"],
            resolved_config["data"]["train"]["sha256"],
        ),
        (
            ROOT / resolved_config["data"]["test"]["path"],
            resolved_config["data"]["test"]["sha256"],
        ),
        (
            ROOT / resolved_config["data"]["sample_submission"]["path"],
            resolved_config["data"]["sample_submission"]["sha256"],
        ),
        (
            ROOT / resolved_config["split"]["path"],
            resolved_config["split"]["sha256"],
        ),
        *[
            (ROOT / record["path"], record["sha256"])
            for record in resolved_config["feature_outputs"].values()
        ],
    ]
    data_hashes_match = all(
        path.is_file() and sha256_file(path) == expected
        for path, expected in hash_records
    )
    reproduced = np.zeros(
        (len(test_ids), len(CLASS_LABELS)), dtype=np.float64
    )
    model_paths = [
        paths["models"] / f"fold_{fold:02d}.json" for fold in range(5)
    ]
    for model_path in model_paths:
        model = xgb.XGBClassifier()
        model.load_model(model_path)
        encoded_indices = model.get_booster().attr(
            "selected_feature_indices"
        )
        if encoded_indices is None:
            raise ValueError(f"checkpoint에 feature mask가 없습니다: {model_path}")
        selected = np.fromstring(encoded_indices, sep=",", dtype=np.int32)
        reproduced += (
            model.predict_proba(test_features[:, selected]).astype(np.float64)
            / 5.0
        )

    original_frame = pd.read_csv(paths["test_probability"])
    original = original_frame[list(PROBABILITY_COLUMNS)].to_numpy()
    probability_match = bool(
        np.allclose(reproduced, original, atol=1e-6, rtol=1e-6)
    )
    maximum_difference = float(np.max(np.abs(reproduced - original)))
    class_array = np.asarray(CLASS_LABELS)
    reproduced_submission = pd.DataFrame(
        {
            "ID": test_ids,
            "SUBCLASS": class_array[reproduced.argmax(axis=1)],
        }
    )
    with tempfile.TemporaryDirectory(
        prefix=f"{paths['models'].name}_verify_"
    ) as temporary:
        reproduced_path = Path(temporary) / paths["submission"].name
        reproduced_submission.to_csv(
            reproduced_path, index=False, lineterminator="\n"
        )
        validate_submission(reproduced_path, TEST_PATH)
        reproduced_sha = sha256_file(reproduced_path)

    original_submission = pd.read_csv(
        paths["submission"], dtype=str, keep_default_na=False
    )
    original_sha = sha256_file(paths["submission"])
    label_agreement = float(
        (
            reproduced_submission["SUBCLASS"].to_numpy()
            == original_submission["SUBCLASS"].to_numpy()
        ).mean()
    )
    submission_match = reproduced_sha == original_sha
    passed = bool(
        data_hashes_match
        and probability_match
        and submission_match
        and label_agreement == 1.0
    )
    if not passed:
        raise RuntimeError("checkpoint 기반 추론 재현 검증에 실패했습니다.")

    repro = paths["reproducibility"]
    repro.mkdir(parents=True, exist_ok=True)
    verified_at = utc_now()
    comparison = {
        "verified_at": verified_at,
        "data_hashes_match": data_hashes_match,
        "original_submission_sha256": original_sha,
        "reproduced_submission_sha256": reproduced_sha,
        "submission_sha256_match": submission_match,
        "test_label_agreement": label_agreement,
        "test_probability_allclose": probability_match,
        "test_probability_max_abs_diff": maximum_difference,
        "probability_atol": 1e-6,
        "probability_rtol": 1e-6,
        "passed": passed,
    }
    environment_path = repro / "environment.json"
    data_manifest_path = repro / "data_manifest.json"
    original_metrics_path = repro / "original_metrics.json"
    reproduction_metrics_path = repro / "reproduction_metrics.json"
    comparison_path = repro / "comparison.json"
    artifact_manifest_path = repro / "artifact_manifest.json"
    reproduce_path = repro / "REPRODUCE.md"

    write_json(
        environment_path,
        {"verified_at": verified_at, **resolved_config["environment"]},
    )
    write_json(
        data_manifest_path,
        {
            "verified_at": verified_at,
            "files": [
                {**file_record(path), "expected_sha256": expected}
                for path, expected in hash_records
            ],
        },
    )
    write_json(original_metrics_path, metrics)
    write_json(comparison_path, comparison)
    write_json(
        reproduction_metrics_path,
        {
            "experiment_id": context.experiment_id,
            "verification_type": "checkpoint_inference",
            **comparison,
        },
    )
    reproduce_path.write_text(
        (
            f"# {context.experiment_id} 재현 절차\n\n"
            "```bash\n"
            "uv sync --frozen\n"
            f"uv run python scripts/run_{paths['models'].name}.py "
            f"--config {relative_posix(paths['config'], ROOT)}\n"
            "uv run python scripts/validate_experiment.py\n"
            "```\n\n"
            "원본 CSV는 Git에 포함하지 않고 `data/raw/`에 별도로 배치합니다.\n"
        ),
        encoding="utf-8",
        newline="\n",
    )

    artifacts = [
        {"kind": "checkpoint", **file_record(path), "storage_uri": None}
        for path in model_paths
    ]
    artifacts.extend(
        [
            {
                "kind": "oof_probability",
                **file_record(paths["oof"]),
                "storage_uri": None,
            },
            {
                "kind": "test_probability",
                **file_record(paths["test_probability"]),
                "storage_uri": None,
            },
            {
                "kind": "submission",
                **file_record(paths["submission"]),
                "storage_uri": None,
            },
            {
                "kind": "resolved_config",
                **file_record(paths["resolved_config"]),
                "storage_uri": None,
            },
            {
                "kind": "metrics",
                **file_record(paths["metrics"]),
                "storage_uri": None,
            },
        ]
    )
    manifest = {
        "experiment_id": context.experiment_id,
        "issue_number": context.issue_number,
        "reproducibility_status": "INFERENCE_VERIFIED",
        "source_commit": source_commit,
        "source_tag": None,
        "dirty_worktree": False,
        "data_manifest": relative_posix(data_manifest_path, ROOT),
        "environment": relative_posix(environment_path, ROOT),
        "release_url": None,
        "verifier": owner,
        "verified_at": verified_at,
        "artifacts": artifacts,
        "verification": {
            "data_hashes_match": data_hashes_match,
            "submission_sha256_match": submission_match,
            "test_label_agreement": label_agreement,
            "probability_atol": 1e-6,
            "probability_rtol": 1e-6,
            "passed": passed,
        },
    }
    write_json(artifact_manifest_path, manifest)
    schema = ROOT / "schemas" / "reproducibility_manifest.schema.json"
    if schema.is_file():
        validate_json_document(artifact_manifest_path, schema)

    checksum_paths = [
        paths["resolved_config"],
        environment_path,
        data_manifest_path,
        artifact_manifest_path,
        original_metrics_path,
        reproduction_metrics_path,
        comparison_path,
        reproduce_path,
    ]
    (repro / "checksums.sha256").write_text(
        "".join(
            f"{sha256_file(path)}  {path.name}\n" for path in checksum_paths
        ),
        encoding="utf-8",
        newline="\n",
    )


def run_experiment(config_path: Path | None) -> None:
    started_at = utc_now()
    start_time = time.perf_counter()
    context = resolve_experiment_context("experiment", cwd=ROOT)
    artifact_prefix = context.artifact_prefix
    if artifact_prefix is None:
        raise ValueError("브랜치에서 EXP-ID를 파생할 수 없습니다.")

    if config_path is None:
        candidates = sorted(
            (ROOT / "configs").glob(f"{artifact_prefix}_*.yaml")
        )
        if len(candidates) != 1:
            raise ValueError(
                f"{artifact_prefix} config를 하나로 특정할 수 없습니다. "
                "--config 경로를 지정하세요."
            )
        config_path = candidates[0]
    else:
        config_path = (
            config_path
            if config_path.is_absolute()
            else ROOT / config_path
        )
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    validate_config(config)
    artifact_slug = f"{artifact_prefix}_{config['slug']}"
    paths = make_paths(artifact_slug)
    paths["config"] = config_path
    if config_path.name != f"{artifact_slug}.yaml":
        raise ValueError(
            f"config 파일명은 {artifact_slug}.yaml 이어야 합니다."
        )

    dirty_status = run_git("status", "--porcelain")
    if dirty_status:
        raise RuntimeError(
            "공식 실험은 clean worktree에서만 실행합니다. 변경을 commit 또는 "
            f"stash한 뒤 다시 실행하세요.\n{dirty_status}"
        )
    source_commit = run_git("rev-parse", "HEAD")
    owner = (
        run_git("config", "user.name")
        or os.environ.get("USER")
        or os.environ.get("USERNAME")
        or "unknown"
    )

    data_contract = validate_competition_data(
        TRAIN_PATH,
        TEST_PATH,
        SAMPLE_SUBMISSION_PATH,
        strict_shape=True,
    )
    if sha256_file(SPLIT_PATH) != CANONICAL_SPLIT_SHA256:
        raise ValueError("canonical split SHA-256 검증에 실패했습니다.")
    train_meta = pd.read_csv(
        TRAIN_PATH,
        usecols=["ID", "SUBCLASS"],
        dtype=str,
        keep_default_na=False,
    )
    test_meta = pd.read_csv(
        TEST_PATH,
        usecols=["ID"],
        dtype=str,
        keep_default_na=False,
    )
    gene_columns = pd.read_csv(TRAIN_PATH, nrows=0).columns[2:].tolist()
    fold_assignments = load_fold_assignments(train_meta["ID"])

    train_features, train_feature_metadata = build_sparse_features(
        TRAIN_PATH,
        gene_columns,
        chunk_size=int(config["features"]["chunk_size"]),
    )
    test_features, test_feature_metadata = build_sparse_features(
        TEST_PATH,
        gene_columns,
        chunk_size=int(config["features"]["chunk_size"]),
    )
    metadata = {
        "data_contract": data_contract,
        "train": train_feature_metadata,
        "test": test_feature_metadata,
    }
    save_processed_features(
        paths=paths,
        train_features=train_features,
        test_features=test_features,
        train_ids=train_meta["ID"],
        test_ids=test_meta["ID"],
        labels=train_meta["SUBCLASS"],
        names=feature_names(gene_columns),
        metadata=metadata,
    )

    oof, test_probability, fold_metrics = train_models(
        config=config,
        paths=paths,
        train_features=train_features,
        test_features=test_features,
        labels=train_meta["SUBCLASS"],
        fold_assignments=fold_assignments,
    )
    save_prediction_artifacts(
        paths=paths,
        train_ids=train_meta["ID"],
        test_ids=test_meta["ID"],
        labels=train_meta["SUBCLASS"],
        fold_assignments=fold_assignments,
        oof=oof,
        test_probability=test_probability,
    )
    elapsed = time.perf_counter() - start_time
    metrics = calculate_metrics(
        context=context,
        owner=owner,
        source_commit=source_commit,
        started_at=started_at,
        elapsed_seconds=elapsed,
        config=config,
        paths=paths,
        labels=train_meta["SUBCLASS"],
        oof=oof,
        fold_metrics=fold_metrics,
    )
    write_json(paths["metrics"], metrics)
    resolved_config = build_resolved_config(
        context=context,
        owner=owner,
        source_commit=source_commit,
        started_at=started_at,
        config=config,
        gene_columns=gene_columns,
        paths=paths,
        feature_metadata=metadata,
        best_iterations=[
            row["best_iteration"] for row in fold_metrics
        ],
    )
    paths["reproducibility"].mkdir(parents=True, exist_ok=True)
    paths["resolved_config"].write_text(
        yaml.safe_dump(
            resolved_config, sort_keys=False, allow_unicode=True
        ),
        encoding="utf-8",
        newline="\n",
    )
    write_report(
        context=context,
        paths=paths,
        metrics=metrics,
        config=config,
        fold_details=fold_metrics,
    )
    verify_saved_inference(
        context=context,
        owner=owner,
        source_commit=source_commit,
        paths=paths,
        test_features=test_features,
        test_ids=test_meta["ID"],
        resolved_config=resolved_config,
        metrics=metrics,
    )
    print(
        json.dumps(
            {
                "experiment_id": context.experiment_id,
                "artifact_slug": artifact_slug,
                "oof_macro_f1": metrics["oof"]["macro_f1"],
                "reproducibility_status": "INFERENCE_VERIFIED",
                "submission": relative_posix(paths["submission"], ROOT),
                "metrics": relative_posix(paths["metrics"], ROOT),
                "history_update_required": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="configs/expNNN_<slug>.yaml; 생략 시 현재 EXP의 단일 config 사용",
    )
    parser.add_argument(
        "--init-config",
        action="store_true",
        help="현재 Issue 브랜치 번호로 공식 config 템플릿만 생성",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.init_config:
        context = resolve_experiment_context("experiment", cwd=ROOT)
        initialize_config(context)
        return
    run_experiment(args.config)


if __name__ == "__main__":
    main()
