#!/usr/bin/env python3
"""Run EXP-476 with nested fold-safe panels, Optuna and class weights."""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
import optuna
import pandas as pd
import yaml
from scipy import sparse
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
)
from sklearn.model_selection import StratifiedKFold
from xgboost import XGBClassifier


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if SRC.exists():
    sys.path.insert(0, str(SRC))

from open_cancer.constants import CLASS_LABELS  # noqa: E402


AA_ORDER = "ACDEFGHIKLMNPQRSTVWY"
AA_INDEX = {value: index for index, value in enumerate(AA_ORDER)}
MUTATION_FAMILIES = ("FS", "ST", "S", "M", "MT")
FAMILY_INDEX = {value: index for index, value in enumerate(MUTATION_FAMILIES)}
SIMPLE_SUBSTITUTION = re.compile(
    r"^([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]*)([ACDEFGHIKLMNPQRSTVWY])$",
    re.IGNORECASE,
)
SIMPLE_STOP = re.compile(
    r"^([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]*)(?:\*|X|TER)$",
    re.IGNORECASE,
)
TOKEN_SPLIT = re.compile(r"[\s,;|/]+")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=float) + "\n",
        encoding="utf-8",
    )


def git_output(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def validate_official_source(config: dict[str, Any]) -> dict[str, str]:
    issue = int(config["issue_number"])
    if config["experiment_id"] != f"EXP-{issue:03d}":
        raise RuntimeError("experiment_id와 issue_number가 일치하지 않습니다.")
    branch = git_output("branch", "--show-current")
    allowed = (f"issue-{issue}", f"issue-{issue}-", str(issue), f"{issue}-")
    if not branch.startswith(allowed):
        raise RuntimeError(f"현재 브랜치({branch})가 Issue #{issue}와 다릅니다.")
    dirty = git_output("status", "--porcelain", "--untracked-files=normal")
    if dirty:
        raise RuntimeError("official 실행은 clean worktree에서만 가능합니다.\n" + dirty)
    return {"branch": branch, "commit": git_output("rev-parse", "HEAD")}


def split_tokens(value: object) -> tuple[str, ...]:
    text = "" if value is None else str(value).strip()
    if not text or text.upper() == "WT":
        return ()
    seen: set[str] = set()
    result: list[str] = []
    for raw in TOKEN_SPLIT.split(text):
        token = raw.strip()
        if token and token.upper() != "WT" and token not in seen:
            seen.add(token)
            result.append(token)
    return tuple(result)


def normalize_stop(token: str) -> str:
    match = SIMPLE_STOP.fullmatch(token.strip())
    if match is None:
        return token.strip()
    return f"{match.group(1).upper()}{match.group(2)}*"


def classify_token(token: str, *, multi_token: bool = False) -> tuple[str, str | None]:
    normalized = normalize_stop(token)
    reference = normalized[:1].upper()
    amino_acid = reference if reference in AA_INDEX else None
    if multi_token:
        return "MT", amino_acid
    if "FS" in normalized.upper():
        return "FS", amino_acid
    if normalized.endswith("*"):
        return "ST", amino_acid
    match = SIMPLE_SUBSTITUTION.fullmatch(normalized)
    if match is not None:
        source = match.group(1).upper()
        alternate = match.group(3).upper()
        return ("S" if source == alternate else "M"), source
    return "MT", amino_acid


def engineered_feature_names() -> tuple[str, ...]:
    aa_names = tuple(
        f"sample__aa_{aa}__{family}_count"
        for aa in AA_ORDER
        for family in MUTATION_FAMILIES
    )
    summary = (
        "sample__mutated_gene_count",
        "sample__raw_event_count",
        "sample__explicit_wt_gene_count",
        "sample__blank_gene_count",
        "sample__log1p_mutated_gene_count",
        "sample__log1p_raw_event_count",
        "sample__max_aa_family_count",
    )
    family_names = tuple(
        f"sample__{family}_event_count" for family in MUTATION_FAMILIES
    )
    return aa_names + summary + family_names


def build_stateless_features(
    frame: pd.DataFrame,
    gene_columns: list[str],
) -> tuple[sparse.csr_matrix, sparse.csr_matrix, dict[str, int]]:
    sample_count = len(frame)
    rows: list[int] = []
    columns: list[int] = []
    aa_family = np.zeros((sample_count, 100), dtype=np.float32)
    family_counts = np.zeros((sample_count, 5), dtype=np.float32)
    mutated = np.zeros(sample_count, dtype=np.float32)
    raw_events = np.zeros(sample_count, dtype=np.float32)
    explicit_wt = np.zeros(sample_count, dtype=np.float32)
    blank = np.zeros(sample_count, dtype=np.float32)

    for gene_index, gene in enumerate(gene_columns):
        for row_index, raw_value in enumerate(frame[gene].to_numpy(copy=False)):
            text = "" if raw_value is None else str(raw_value).strip()
            if not text:
                blank[row_index] += 1
                continue
            if text.upper() == "WT":
                explicit_wt[row_index] += 1
                continue
            tokens = split_tokens(text)
            if not tokens:
                continue
            rows.append(row_index)
            columns.append(gene_index)
            mutated[row_index] += 1
            raw_events[row_index] += len(tokens)
            is_multi = len(tokens) > 1
            for token in tokens:
                family, amino_acid = classify_token(token, multi_token=is_multi)
                family_index = FAMILY_INDEX[family]
                family_counts[row_index, family_index] += 1
                if amino_acid is not None:
                    position = AA_INDEX[amino_acid] * 5 + family_index
                    aa_family[row_index, position] += 1

    gene_matrix = sparse.csr_matrix(
        (
            np.ones(len(rows), dtype=np.float32),
            (np.asarray(rows), np.asarray(columns)),
        ),
        shape=(sample_count, len(gene_columns)),
        dtype=np.float32,
    )
    summary = np.column_stack(
        [
            mutated,
            raw_events,
            explicit_wt,
            blank,
            np.log1p(mutated),
            np.log1p(raw_events),
            aa_family.max(axis=1),
        ]
    ).astype(np.float32)
    engineered = sparse.csr_matrix(
        np.hstack([aa_family, summary, family_counts]),
        dtype=np.float32,
    )
    if engineered.shape[1] != len(engineered_feature_names()):
        raise RuntimeError("engineered feature schema가 일치하지 않습니다.")
    return gene_matrix, engineered, {
        "sample_count": sample_count,
        "gene_count": len(gene_columns),
        "non_wt_cell_count": int(gene_matrix.nnz),
        "raw_event_count": int(raw_events.sum()),
        "blank_cell_count": int(blank.sum()),
    }


def select_recurrent_genes(
    gene_matrix: sparse.csr_matrix,
    fit_rows: np.ndarray,
    *,
    minimum_support: int,
    maximum_features: int,
) -> np.ndarray:
    support = np.asarray(gene_matrix[fit_rows].sum(axis=0)).ravel()
    candidates = np.flatnonzero(support >= minimum_support)
    order = np.lexsort((candidates, -support[candidates]))
    return np.sort(candidates[order[:maximum_features]].astype(np.int32))


def fit_class_panels(
    gene_matrix: sparse.csr_matrix,
    target: np.ndarray,
    fit_rows: np.ndarray,
    *,
    top_k: int,
    minimum_support: int,
) -> tuple[np.ndarray, ...]:
    """Fit equally sized one-vs-rest panels using only supplied training rows."""
    matrix = gene_matrix[fit_rows]
    labels = target[fit_rows]
    total_support = np.asarray(matrix.sum(axis=0)).ravel()
    eligible = np.flatnonzero(total_support >= minimum_support)
    panels: list[np.ndarray] = []
    for class_index in range(len(CLASS_LABELS)):
        positive_mask = labels == class_index
        negative_mask = ~positive_mask
        positive = np.asarray(matrix[positive_mask].sum(axis=0)).ravel()
        negative = np.asarray(matrix[negative_mask].sum(axis=0)).ravel()
        positive_rate = (positive + 0.5) / (positive_mask.sum() + 1.0)
        negative_rate = (negative + 0.5) / (negative_mask.sum() + 1.0)
        score = np.log(positive_rate / (1.0 - positive_rate)) - np.log(
            negative_rate / (1.0 - negative_rate)
        )
        order = np.lexsort((eligible, -score[eligible]))
        panels.append(np.sort(eligible[order[:top_k]].astype(np.int32)))
    return tuple(panels)


def transform_class_panels(
    gene_matrix: sparse.csr_matrix,
    row_indices: np.ndarray,
    panels: tuple[np.ndarray, ...],
) -> sparse.csr_matrix:
    values = np.column_stack(
        [
            np.asarray(gene_matrix[row_indices][:, panel].sum(axis=1)).ravel()
            for panel in panels
        ]
    ).astype(np.float32)
    return sparse.csr_matrix(values)


def combine_features(
    gene_matrix: sparse.csr_matrix,
    engineered: sparse.csr_matrix,
    row_indices: np.ndarray,
    selected_genes: np.ndarray,
    panels: tuple[np.ndarray, ...],
) -> sparse.csr_matrix:
    return sparse.hstack(
        [
            gene_matrix[row_indices][:, selected_genes],
            engineered[row_indices],
            transform_class_panels(gene_matrix, row_indices, panels),
        ],
        format="csr",
        dtype=np.float32,
    )


def balanced_power_weights(target: np.ndarray, power: float) -> np.ndarray:
    classes, counts = np.unique(target, return_counts=True)
    base = {value: len(target) / (len(classes) * count) for value, count in zip(classes, counts)}
    weights = np.asarray([base[value] ** power for value in target], dtype=np.float32)
    return weights / weights.mean()


def suggest_parameters(trial: optuna.Trial, config: dict[str, Any]) -> dict[str, Any]:
    space = config["model"]["search_space"]
    return {
        "learning_rate": trial.suggest_float("learning_rate", *space["learning_rate"], log=True),
        "max_depth": trial.suggest_int("max_depth", *space["max_depth"]),
        "min_child_weight": trial.suggest_float("min_child_weight", *space["min_child_weight"], log=True),
        "subsample": trial.suggest_float("subsample", *space["subsample"]),
        "colsample_bytree": trial.suggest_float("colsample_bytree", *space["colsample_bytree"]),
        "reg_alpha": trial.suggest_float("reg_alpha", *space["reg_alpha"], log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", *space["reg_lambda"], log=True),
        "gamma": trial.suggest_float("gamma", *space["gamma"]),
        "weight_power": trial.suggest_categorical(
            "weight_power", config["imbalance"]["power_choices"]
        ),
    }


def xgb_parameters(
    config: dict[str, Any],
    candidate: dict[str, Any],
    *,
    seed: int,
    n_estimators: int,
    early_stopping_rounds: int | None,
) -> dict[str, Any]:
    parameters = {
        key: value for key, value in candidate.items() if key != "weight_power"
    }
    parameters.update(
        {
            "objective": config["model"]["objective"],
            "eval_metric": config["model"]["eval_metric"],
            "tree_method": config["model"]["tree_method"],
            "device": config["model"]["device"],
            "n_jobs": int(config["model"]["n_jobs"]),
            "verbosity": int(config["model"]["verbosity"]),
            "num_class": len(CLASS_LABELS),
            "random_state": seed,
            "n_estimators": n_estimators,
        }
    )
    if early_stopping_rounds is not None:
        parameters["early_stopping_rounds"] = early_stopping_rounds
    return parameters


def tune_outer_fold(
    config: dict[str, Any],
    target: np.ndarray,
    gene_matrix: sparse.csr_matrix,
    engineered: sparse.csr_matrix,
    outer_train: np.ndarray,
    *,
    outer_fold: int,
) -> tuple[dict[str, Any], int, list[dict[str, Any]]]:
    seed = int(config["seed"])
    tuning = config["nested_optuna"]
    features = config["features"]
    panels_config = features["class_panel"]
    splitter = StratifiedKFold(
        n_splits=int(tuning["inner_n_splits"]),
        shuffle=True,
        random_state=seed + outer_fold,
    )

    def objective(trial: optuna.Trial) -> float:
        candidate = suggest_parameters(trial, config)
        scores: list[float] = []
        iterations: list[int] = []
        outer_target = target[outer_train]
        for inner_fold, (relative_train, relative_valid) in enumerate(
            splitter.split(np.zeros(len(outer_train)), outer_target)
        ):
            inner_train = outer_train[relative_train]
            inner_valid = outer_train[relative_valid]
            selected = select_recurrent_genes(
                gene_matrix,
                inner_train,
                minimum_support=int(features["minimum_fold_train_gene_support"]),
                maximum_features=int(features["maximum_gene_features"]),
            )
            panels = fit_class_panels(
                gene_matrix,
                target,
                inner_train,
                top_k=int(panels_config["top_k_genes_per_class"]),
                minimum_support=int(panels_config["minimum_fold_train_support"]),
            )
            x_train = combine_features(gene_matrix, engineered, inner_train, selected, panels)
            x_valid = combine_features(gene_matrix, engineered, inner_valid, selected, panels)
            parameters = xgb_parameters(
                config,
                candidate,
                seed=seed + outer_fold * 1000 + trial.number * 10 + inner_fold,
                n_estimators=int(tuning["n_estimators_ceiling"]),
                early_stopping_rounds=int(tuning["early_stopping_rounds"]),
            )
            model = XGBClassifier(**parameters)
            weights = balanced_power_weights(target[inner_train], candidate["weight_power"])
            model.fit(
                x_train,
                target[inner_train],
                sample_weight=weights,
                eval_set=[(x_valid, target[inner_valid])],
                verbose=False,
            )
            probability = model.predict_proba(x_valid)
            scores.append(f1_score(target[inner_valid], probability.argmax(axis=1), average="macro"))
            iterations.append(int(model.best_iteration) + 1)
        trial.set_user_attr("selected_iterations", iterations)
        return float(np.mean(scores))

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=seed + outer_fold),
    )
    study.optimize(objective, n_trials=int(tuning["n_trials"]), show_progress_bar=False)
    selected_iterations = study.best_trial.user_attrs["selected_iterations"]
    n_estimators = max(20, int(round(float(np.median(selected_iterations)))))
    trials = [
        {
            "number": trial.number,
            "macro_f1": trial.value,
            "parameters": trial.params,
            "selected_iterations": trial.user_attrs.get("selected_iterations", []),
        }
        for trial in study.trials
    ]
    return dict(study.best_params), n_estimators, trials


def load_canonical_folds(config: dict[str, Any], train_ids: pd.Series) -> np.ndarray:
    data = config["data"]
    path = ROOT / data["canonical_split_path"]
    if not path.is_file():
        raise FileNotFoundError("canonical split이 없으며 임의 split fallback은 금지됩니다.")
    if sha256_file(path) != data["canonical_split_sha256"]:
        raise RuntimeError("canonical split SHA-256이 다릅니다.")
    split = pd.read_csv(path, dtype={data["id_column"]: str})
    mapping = split.set_index(data["id_column"])[data["fold_column"]]
    aligned = mapping.reindex(train_ids.astype(str))
    if aligned.isna().any() or set(aligned.astype(int)) != {0, 1, 2, 3, 4}:
        raise RuntimeError("canonical split ID 또는 fold 계약이 다릅니다.")
    return aligned.astype(int).to_numpy()


def main(config_path: Path) -> None:
    started_at = utc_now()
    started = time.perf_counter()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    source = validate_official_source(config)
    data = config["data"]
    paths = {
        key: ROOT / data[key]
        for key in ("train_path", "test_path", "sample_submission_path")
    }
    for path in paths.values():
        if not path.is_file():
            raise FileNotFoundError(path)
    train = pd.read_csv(paths["train_path"], dtype=str, keep_default_na=False)
    test = pd.read_csv(paths["test_path"], dtype=str, keep_default_na=False)
    id_column = data["id_column"]
    target_column = data["target_column"]
    genes = [column for column in train.columns if column not in {id_column, target_column}]
    if list(test.columns) != [id_column, *genes]:
        raise RuntimeError("train/test 유전자 열 이름 또는 순서가 다릅니다.")
    class_to_index = {label: index for index, label in enumerate(CLASS_LABELS)}
    if set(train[target_column]) - set(class_to_index):
        raise RuntimeError("고정 CLASS_LABELS에 없는 target이 있습니다.")
    target = train[target_column].map(class_to_index).to_numpy(dtype=np.int32)
    folds = load_canonical_folds(config, train[id_column])
    gene_train, engineered_train, train_qc = build_stateless_features(train, genes)
    gene_test, engineered_test, test_qc = build_stateless_features(test, genes)

    artifact_slug = f"exp476_{config['slug']}"
    report_dir = ROOT / "reports" / artifact_slug
    model_dir = ROOT / "models" / artifact_slug
    oof_path = ROOT / "oof" / f"{artifact_slug}.csv"
    test_probability_path = ROOT / "preds" / f"{artifact_slug}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{artifact_slug}.csv"
    resolved_path = ROOT / "reproducibility" / artifact_slug / "config.resolved.yaml"
    for directory in (report_dir, model_dir, oof_path.parent, test_probability_path.parent, submission_path.parent, resolved_path.parent):
        directory.mkdir(parents=True, exist_ok=True)

    oof_probability = np.zeros((len(train), len(CLASS_LABELS)), dtype=np.float32)
    test_probabilities: list[np.ndarray] = []
    fold_metrics: list[dict[str, Any]] = []
    fold_records: list[dict[str, Any]] = []
    for fold in range(5):
        outer_train = np.flatnonzero(folds != fold)
        outer_valid = np.flatnonzero(folds == fold)
        candidate, n_estimators, trials = tune_outer_fold(
            config,
            target,
            gene_train,
            engineered_train,
            outer_train,
            outer_fold=fold,
        )
        feature_config = config["features"]
        panel_config = feature_config["class_panel"]
        selected = select_recurrent_genes(
            gene_train,
            outer_train,
            minimum_support=int(feature_config["minimum_fold_train_gene_support"]),
            maximum_features=int(feature_config["maximum_gene_features"]),
        )
        panels = fit_class_panels(
            gene_train,
            target,
            outer_train,
            top_k=int(panel_config["top_k_genes_per_class"]),
            minimum_support=int(panel_config["minimum_fold_train_support"]),
        )
        x_train = combine_features(gene_train, engineered_train, outer_train, selected, panels)
        x_valid = combine_features(gene_train, engineered_train, outer_valid, selected, panels)
        x_test = combine_features(
            gene_test,
            engineered_test,
            np.arange(len(test), dtype=np.int32),
            selected,
            panels,
        )
        parameters = xgb_parameters(
            config,
            candidate,
            seed=int(config["seed"]) + fold,
            n_estimators=n_estimators,
            early_stopping_rounds=None,
        )
        model = XGBClassifier(**parameters)
        weights = balanced_power_weights(target[outer_train], candidate["weight_power"])
        model.fit(x_train, target[outer_train], sample_weight=weights, verbose=False)
        valid_probability = model.predict_proba(x_valid)
        test_probability = model.predict_proba(x_test)
        oof_probability[outer_valid] = valid_probability
        test_probabilities.append(test_probability.astype(np.float32))
        prediction = valid_probability.argmax(axis=1)
        fold_metric = {
            "fold": fold,
            "macro_f1": float(f1_score(target[outer_valid], prediction, average="macro")),
            "accuracy": float(accuracy_score(target[outer_valid], prediction)),
            "log_loss": float(log_loss(target[outer_valid], valid_probability, labels=np.arange(len(CLASS_LABELS)))),
            "best_iteration": n_estimators - 1,
        }
        fold_metrics.append(fold_metric)
        model_path = model_dir / f"fold_{fold:02d}.json"
        model.save_model(model_path)
        record = {
            "fold": fold,
            "selected_gene_indices": selected.tolist(),
            "class_panel_gene_indices": [panel.tolist() for panel in panels],
            "class_panel_labels": list(CLASS_LABELS),
            "best_parameters": candidate,
            "selected_n_estimators": n_estimators,
            "inner_trials": trials,
            "model_path": str(model_path.relative_to(ROOT)),
            "model_sha256": sha256_file(model_path),
        }
        fold_records.append(record)
        write_json(model_dir / f"fold_{fold:02d}_metadata.json", record)
        print(json.dumps(fold_metric, ensure_ascii=False), flush=True)

    oof_prediction = oof_probability.argmax(axis=1)
    test_probability = np.mean(test_probabilities, axis=0)
    test_prediction = test_probability.argmax(axis=1)
    oof_frame = pd.DataFrame(oof_probability, columns=CLASS_LABELS)
    oof_frame.insert(0, id_column, train[id_column])
    oof_frame["true_SUBCLASS"] = train[target_column]
    oof_frame["pred_SUBCLASS"] = np.asarray(CLASS_LABELS)[oof_prediction]
    oof_frame["fold"] = folds
    oof_frame.to_csv(oof_path, index=False)
    test_frame = pd.DataFrame(test_probability, columns=CLASS_LABELS)
    test_frame.insert(0, id_column, test[id_column])
    test_frame.to_csv(test_probability_path, index=False)
    sample = pd.read_csv(paths["sample_submission_path"], dtype=str)
    if sample[id_column].tolist() != test[id_column].tolist():
        raise RuntimeError("sample_submission과 test ID 순서가 다릅니다.")
    submission = pd.DataFrame(
        {id_column: test[id_column], target_column: np.asarray(CLASS_LABELS)[test_prediction]}
    )
    submission.to_csv(submission_path, index=False)

    report = classification_report(
        target,
        oof_prediction,
        labels=np.arange(len(CLASS_LABELS)),
        target_names=list(CLASS_LABELS),
        output_dict=True,
        zero_division=0,
    )
    write_json(report_dir / "classification_report.json", report)
    write_json(report_dir / "fold_feature_and_search.json", fold_records)
    scores = [item["macro_f1"] for item in fold_metrics]
    metrics = {
        "experiment_id": config["experiment_id"],
        "record_role": config["record_role"],
        "status": "COMPLETED",
        "owner": config["owner"],
        "issue_number": int(config["issue_number"]),
        "parent_experiment": config.get("parent_experiment"),
        "git_commit": source["commit"],
        "started_at": started_at,
        "finished_at": utc_now(),
        "primary_metric": "macro_f1",
        "split_id": data["canonical_split_path"],
        "folds": fold_metrics,
        "oof": {
            "macro_f1": float(f1_score(target, oof_prediction, average="macro")),
            "fold_mean": float(np.mean(scores)),
            "fold_std": float(np.std(scores)),
            "accuracy": float(accuracy_score(target, oof_prediction)),
            "log_loss": float(log_loss(target, oof_probability, labels=np.arange(len(CLASS_LABELS)))),
            "per_class_f1": {label: float(report[label]["f1-score"]) for label in CLASS_LABELS},
            "confusion_matrix": confusion_matrix(target, oof_prediction, labels=np.arange(len(CLASS_LABELS))).tolist(),
        },
        "leaderboard": None,
        "runtime": {"seconds": time.perf_counter() - started, "hardware": platform.platform()},
        "artifacts": {
            "resolved_config": str(resolved_path.relative_to(ROOT)),
            "oof": str(oof_path.relative_to(ROOT)),
            "test_probability": str(test_probability_path.relative_to(ROOT)),
            "submission": str(submission_path.relative_to(ROOT)),
            "models": str(model_dir.relative_to(ROOT)),
            "submission_sha256": sha256_file(submission_path),
        },
        "notes": (
            "Issue #476. All 26 class panels, gene recurrence masks, Optuna parameters "
            "and class-weight powers are fitted within the applicable training partition. "
            "Canonical folds are mandatory; test is transform-only; oversampling is disabled."
        ),
    }
    metrics_path = report_dir / "metrics.json"
    write_json(metrics_path, metrics)
    resolved = dict(config)
    resolved["source"] = source
    resolved["data_hashes"] = {
        "train_sha256": sha256_file(paths["train_path"]),
        "test_sha256": sha256_file(paths["test_path"]),
        "canonical_split_sha256": sha256_file(ROOT / data["canonical_split_path"]),
    }
    resolved["runtime_folds"] = fold_records
    resolved_path.write_text(
        yaml.safe_dump(resolved, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    (report_dir / "README.md").write_text(
        f"# EXP-476 config feature pipeline\n\n"
        f"- OOF Macro F1: `{metrics['oof']['macro_f1']:.10f}`\n"
        f"- OOF Accuracy: `{metrics['oof']['accuracy']:.10f}`\n"
        f"- OOF Log Loss: `{metrics['oof']['log_loss']:.10f}`\n"
        "- Canonical outer folds and nested inner tuning were used.\n"
        "- Test data was transform-only. Oversampling and SMOTE were not used.\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "experiment_id": "EXP-476",
                "oof_macro_f1": metrics["oof"]["macro_f1"],
                "submission": str(submission_path.relative_to(ROOT)),
                "metrics": str(metrics_path.relative_to(ROOT)),
                "history_update_required": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / "exp476_config_feature_pipeline.yaml",
    )
    arguments = parser.parse_args()
    main(arguments.config.resolve())
