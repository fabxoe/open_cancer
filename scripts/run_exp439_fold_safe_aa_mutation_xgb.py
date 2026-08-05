#!/usr/bin/env python3
"""EXP-439: fold-safe amino-acid x mutation XGBoost pipeline."""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
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
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if SRC.exists():
    sys.path.insert(0, str(SRC))

try:
    from open_cancer.constants import CLASS_LABELS
except ImportError as exc:  # pragma: no cover - repository contract check
    raise RuntimeError("src/open_cancer/constants.py를 찾을 수 없습니다.") from exc


AA_ORDER = "ACDEFGHIKLMNPQRSTVWY"
AA_INDEX = {amino_acid: index for index, amino_acid in enumerate(AA_ORDER)}
EVENT_GROUPS = ("FS", "S", "ST", "M", "MT")
EVENT_INDEX = {event: index for index, event in enumerate(EVENT_GROUPS)}
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
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    """Calculate SHA-256 without loading an entire artifact into memory."""
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_output(*arguments: str) -> str:
    """Run a read-only git command in the repository root."""
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def assert_official_source(config: dict[str, Any]) -> dict[str, str]:
    """Enforce the team issue/branch/clean-source contract."""
    experiment_id = str(config["experiment_id"])
    issue_number = int(config["issue_number"])
    expected_id = f"EXP-{issue_number:03d}"
    if experiment_id != expected_id:
        raise RuntimeError(f"experiment_id는 {expected_id}여야 합니다.")

    branch = git_output("branch", "--show-current")
    allowed_prefixes = (
        str(issue_number),
        f"{issue_number}-",
        f"issue-{issue_number}",
        f"issue-{issue_number}-",
    )
    if not branch.startswith(allowed_prefixes):
        raise RuntimeError(
            f"현재 브랜치({branch})가 Issue #{issue_number}와 연결되지 않았습니다."
        )

    dirty = git_output("status", "--porcelain", "--untracked-files=normal")
    if dirty:
        raise RuntimeError(
            "official 실행은 커밋된 clean worktree에서만 가능합니다.\n" + dirty
        )
    return {"branch": branch, "commit": git_output("rev-parse", "HEAD")}


def split_mutation_tokens(value: object) -> tuple[str, ...]:
    """Split one cell while preserving only explicit non-WT tokens."""
    text = "" if value is None else str(value).strip()
    if not text or text.upper() == "WT":
        return ()
    return tuple(token for token in TOKEN_SPLIT.split(text) if token)


def normalize_stop_notation_token(token: str) -> str:
    """Normalize simple protein stop suffixes X/Ter to the canonical '*' form."""
    match = SIMPLE_STOP.fullmatch(token.strip())
    if match is None:
        return token.strip()
    return f"{match.group(1).upper()}{match.group(2)}*"


def classify_mutation_token(token: str, *, multi_token: bool = False) -> tuple[str, str | None]:
    """Map a token to FS/S/ST/M/MT and its reference amino acid.

    Complex or ambiguous notation is deliberately isolated as MT instead of
    being guessed as missense. A multi-token cell is also classified as MT.
    """
    normalized = normalize_stop_notation_token(token)
    reference = normalized[:1].upper()
    amino_acid = reference if reference in AA_INDEX else None
    if multi_token:
        return "MT", amino_acid
    if "FS" in normalized.upper():
        return "FS", amino_acid
    if normalized.endswith("*"):
        return "ST", amino_acid
    substitution = SIMPLE_SUBSTITUTION.fullmatch(normalized)
    if substitution is not None:
        ref = substitution.group(1).upper()
        alt = substitution.group(3).upper()
        return ("S" if ref == alt else "M"), ref
    return "MT", amino_acid


def engineered_feature_names() -> tuple[str, ...]:
    """Return the fixed names of all label-free sample features."""
    matrix_names = tuple(
        f"sample__aa_{amino_acid}__event_{event}__count"
        for amino_acid in AA_ORDER
        for event in EVENT_GROUPS
    )
    summary_names = (
        "sample__aa_event_count_sum",
        "sample__mutated_gene_count",
        "sample__raw_event_count",
        "sample__aa_event_count_max",
        "sample__explicit_wt_gene_count",
        "sample__blank_gene_count",
        "sample__log1p_mutated_gene_count",
        "sample__log1p_raw_event_count",
        "sample__weighted_event_digit_code",
    )
    group_names = tuple(
        f"sample__event_{event}__count" for event in EVENT_GROUPS
    )
    occurrence_names = tuple(
        name
        for event in EVENT_GROUPS
        for name in (
            f"sample__event_{event}__one_gene_count",
            f"sample__event_{event}__multi_gene_count",
        )
    )
    digit_names = tuple(
        f"sample__event_{event}__capped_digit"
        for event in ("FS", "ST", "S", "M")
    )
    return matrix_names + summary_names + group_names + occurrence_names + digit_names


def build_stateless_features(
    frame: pd.DataFrame,
    gene_columns: list[str],
) -> tuple[sparse.csr_matrix, sparse.csr_matrix, dict[str, Any]]:
    """Build gene-presence and fixed engineered matrices without labels."""
    sample_count = len(frame)
    gene_rows: list[int] = []
    gene_indices: list[int] = []
    aa_event = np.zeros((sample_count, 100), dtype=np.float32)
    group_counts = np.zeros((sample_count, 5), dtype=np.float32)
    group_one = np.zeros((sample_count, 5), dtype=np.float32)
    group_multi = np.zeros((sample_count, 5), dtype=np.float32)
    mutated_genes = np.zeros(sample_count, dtype=np.float32)
    raw_events = np.zeros(sample_count, dtype=np.float32)
    explicit_wt = np.zeros(sample_count, dtype=np.float32)
    blank = np.zeros(sample_count, dtype=np.float32)
    unparsed_events = 0

    for gene_index, gene in enumerate(gene_columns):
        values = frame[gene].to_numpy(copy=False)
        for row_index, raw_value in enumerate(values):
            text = "" if raw_value is None else str(raw_value).strip()
            if not text:
                blank[row_index] += 1.0
                continue
            if text.upper() == "WT":
                explicit_wt[row_index] += 1.0
                continue

            gene_rows.append(row_index)
            gene_indices.append(gene_index)
            mutated_genes[row_index] += 1.0
            tokens = split_mutation_tokens(text)
            raw_events[row_index] += len(tokens)
            per_cell_groups: Counter[str] = Counter()
            is_multi = len(tokens) > 1

            for token in tokens:
                event, amino_acid = classify_mutation_token(
                    token,
                    multi_token=is_multi,
                )
                event_index = EVENT_INDEX[event]
                group_counts[row_index, event_index] += 1.0
                per_cell_groups[event] += 1
                if amino_acid is not None:
                    position = AA_INDEX[amino_acid] * len(EVENT_GROUPS) + event_index
                    aa_event[row_index, position] += 1.0
                else:
                    unparsed_events += 1

            for event, count in per_cell_groups.items():
                event_index = EVENT_INDEX[event]
                if count == 1:
                    group_one[row_index, event_index] += 1.0
                else:
                    group_multi[row_index, event_index] += 1.0

    gene_matrix = sparse.csr_matrix(
        (
            np.ones(len(gene_rows), dtype=np.float32),
            (np.asarray(gene_rows), np.asarray(gene_indices)),
        ),
        shape=(sample_count, len(gene_columns)),
        dtype=np.float32,
    )
    capped_digits = np.minimum(
        group_counts[:, [EVENT_INDEX[event] for event in ("FS", "ST", "S", "M")]],
        9.0,
    )
    digit_code = (
        capped_digits[:, 0] * 1000.0
        + capped_digits[:, 1] * 100.0
        + capped_digits[:, 2] * 10.0
        + capped_digits[:, 3]
    )
    summary = np.column_stack(
        [
            aa_event.sum(axis=1),
            mutated_genes,
            raw_events,
            aa_event.max(axis=1),
            explicit_wt,
            blank,
            np.log1p(mutated_genes),
            np.log1p(raw_events),
            digit_code,
        ]
    ).astype(np.float32)
    occurrence = np.column_stack(
        [column for index in range(5) for column in (group_one[:, index], group_multi[:, index])]
    ).astype(np.float32)
    engineered = sparse.csr_matrix(
        np.hstack([aa_event, summary, group_counts, occurrence, capped_digits]),
        dtype=np.float32,
    )
    expected_features = len(engineered_feature_names())
    if engineered.shape[1] != expected_features:
        raise RuntimeError("고정 engineered feature 이름과 행렬 차원이 다릅니다.")
    metadata = {
        "sample_count": sample_count,
        "gene_count": len(gene_columns),
        "non_wt_cell_count": int(gene_matrix.nnz),
        "blank_cell_count": int(blank.sum()),
        "raw_event_count": int(raw_events.sum()),
        "events_without_reference_amino_acid": int(unparsed_events),
        "engineered_feature_count": int(engineered.shape[1]),
    }
    return gene_matrix, engineered, metadata


def select_gene_indices(
    gene_matrix: sparse.csr_matrix,
    train_indices: np.ndarray,
    *,
    minimum_support: int,
    top_n: int,
) -> np.ndarray:
    """Fit an unsupervised recurrence selector using one training partition."""
    support = np.asarray(gene_matrix[train_indices].sum(axis=0)).ravel()
    candidates = np.flatnonzero(support >= minimum_support)
    order = np.lexsort((candidates, -support[candidates]))
    selected = candidates[order[:top_n]]
    return np.sort(selected.astype(np.int32))


def combine_features(
    gene_matrix: sparse.csr_matrix,
    engineered_matrix: sparse.csr_matrix,
    row_indices: np.ndarray,
    selected_genes: np.ndarray,
) -> sparse.csr_matrix:
    """Combine fold-selected gene indicators with fixed label-free features."""
    return sparse.hstack(
        [gene_matrix[row_indices][:, selected_genes], engineered_matrix[row_indices]],
        format="csr",
        dtype=np.float32,
    )


def sample_parameters(trial: optuna.Trial, config: dict[str, Any]) -> dict[str, Any]:
    """Sample regularized XGBoost parameters from the YAML search space."""
    space = config["model"]["parameter_space"]
    return {
        "learning_rate": trial.suggest_float(
            "learning_rate", *space["learning_rate"], log=True
        ),
        "max_depth": trial.suggest_int("max_depth", *space["max_depth"]),
        "min_child_weight": trial.suggest_float(
            "min_child_weight", *space["min_child_weight"], log=True
        ),
        "subsample": trial.suggest_float("subsample", *space["subsample"]),
        "colsample_bytree": trial.suggest_float(
            "colsample_bytree", *space["colsample_bytree"]
        ),
        "reg_alpha": trial.suggest_float("reg_alpha", *space["reg_alpha"], log=True),
        "reg_lambda": trial.suggest_float(
            "reg_lambda", *space["reg_lambda"], log=True
        ),
        "gamma": trial.suggest_float("gamma", *space["gamma"]),
    }


def model_parameters(
    config: dict[str, Any],
    sampled: dict[str, Any],
    *,
    seed: int,
    n_estimators: int,
    early_stopping_rounds: int | None,
) -> dict[str, Any]:
    """Build one complete XGBoost parameter dictionary."""
    model_config = config["model"]
    parameters: dict[str, Any] = {
        "objective": model_config["objective"],
        "eval_metric": model_config["eval_metric"],
        "tree_method": model_config["tree_method"],
        "device": model_config["device"],
        "n_jobs": int(model_config["n_jobs"]),
        "verbosity": int(model_config["verbosity"]),
        "num_class": len(CLASS_LABELS),
        "random_state": seed,
        "n_estimators": n_estimators,
        **sampled,
    }
    if early_stopping_rounds is not None:
        parameters["early_stopping_rounds"] = early_stopping_rounds
    return parameters


def tune_outer_fold(
    config: dict[str, Any],
    y: np.ndarray,
    gene_train: sparse.csr_matrix,
    engineered_train: sparse.csr_matrix,
    outer_train_indices: np.ndarray,
    *,
    outer_fold: int,
) -> tuple[dict[str, Any], int, list[dict[str, Any]]]:
    """Tune only inside one canonical outer-train partition."""
    seed = int(config["seed"])
    search = config["search"]
    feature_config = config["features"]
    inner = StratifiedKFold(
        n_splits=int(search["inner_splits"]),
        shuffle=True,
        random_state=seed + outer_fold,
    )

    def objective(trial: optuna.Trial) -> float:
        sampled = sample_parameters(trial, config)
        scores: list[float] = []
        iterations: list[int] = []
        outer_y = y[outer_train_indices]
        for inner_fold, (relative_train, relative_valid) in enumerate(
            inner.split(np.zeros(len(outer_train_indices)), outer_y)
        ):
            inner_train = outer_train_indices[relative_train]
            inner_valid = outer_train_indices[relative_valid]
            selected = select_gene_indices(
                gene_train,
                inner_train,
                minimum_support=int(feature_config["minimum_fold_train_support"]),
                top_n=int(feature_config["top_n_genes"]),
            )
            x_train = combine_features(
                gene_train, engineered_train, inner_train, selected
            )
            x_valid = combine_features(
                gene_train, engineered_train, inner_valid, selected
            )
            parameters = model_parameters(
                config,
                sampled,
                seed=seed + outer_fold * 1000 + trial.number * 10 + inner_fold,
                n_estimators=int(search["n_estimators_ceiling"]),
                early_stopping_rounds=int(search["early_stopping_rounds"]),
            )
            model = XGBClassifier(**parameters)
            weights = compute_sample_weight("balanced", y[inner_train])
            model.fit(
                x_train,
                y[inner_train],
                sample_weight=weights,
                eval_set=[(x_valid, y[inner_valid])],
                verbose=False,
            )
            probability = model.predict_proba(x_valid)
            prediction = probability.argmax(axis=1)
            scores.append(f1_score(y[inner_valid], prediction, average="macro"))
            iterations.append(int(model.best_iteration) + 1)
        trial.set_user_attr("best_iterations", iterations)
        return float(np.mean(scores))

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=seed + outer_fold),
    )
    study.optimize(objective, n_trials=int(search["n_trials"]), show_progress_bar=False)
    best_iterations = study.best_trial.user_attrs["best_iterations"]
    chosen_iterations = max(20, int(round(float(np.median(best_iterations)))))
    trials = [
        {
            "number": trial.number,
            "macro_f1": trial.value,
            "parameters": trial.params,
            "best_iterations": trial.user_attrs.get("best_iterations", []),
        }
        for trial in study.trials
    ]
    return dict(study.best_params), chosen_iterations, trials


def load_canonical_folds(
    path: Path,
    train_ids: pd.Series,
    *,
    id_column: str,
    fold_column: str,
) -> np.ndarray:
    """Align the canonical split to train IDs and reject malformed mappings."""
    split = pd.read_csv(path, dtype={id_column: str})
    if id_column not in split or fold_column not in split:
        raise RuntimeError("canonical split에 ID/fold 컬럼이 없습니다.")
    if split[id_column].duplicated().any():
        raise RuntimeError("canonical split ID가 중복되었습니다.")
    mapping = split.set_index(id_column)[fold_column]
    aligned = mapping.reindex(train_ids.astype(str))
    if aligned.isna().any():
        raise RuntimeError("canonical split에서 일부 train ID를 찾을 수 없습니다.")
    folds = aligned.astype(int).to_numpy()
    if set(np.unique(folds)) != {0, 1, 2, 3, 4}:
        raise RuntimeError("canonical split은 fold 0~4를 모두 포함해야 합니다.")
    return folds


def write_json(path: Path, value: Any) -> None:
    """Write deterministic UTF-8 JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=float) + "\n",
        encoding="utf-8",
    )


def main(config_path: Path) -> None:
    """Run nested fold-safe training, OOF evaluation, and test inference."""
    started_at = utc_now()
    started = time.perf_counter()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    source = assert_official_source(config)
    seed = int(config["seed"])
    np.random.seed(seed)

    data = config["data"]
    train_path = ROOT / data["train_path"]
    test_path = ROOT / data["test_path"]
    sample_path = ROOT / data["sample_submission_path"]
    split_path = ROOT / data["canonical_split_path"]
    for path in (train_path, test_path, sample_path, split_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    train = pd.read_csv(train_path, dtype=str, keep_default_na=False)
    test = pd.read_csv(test_path, dtype=str, keep_default_na=False)
    id_column = data["id_column"]
    target_column = data["target_column"]
    gene_columns = [
        column for column in train.columns if column not in {id_column, target_column}
    ]
    if list(test.columns) != [id_column, *gene_columns]:
        raise RuntimeError("train/test 유전자 열 이름 또는 순서가 다릅니다.")
    if train[id_column].duplicated().any() or test[id_column].duplicated().any():
        raise RuntimeError("ID가 중복되었습니다.")

    class_to_index = {label: index for index, label in enumerate(CLASS_LABELS)}
    unknown_classes = sorted(set(train[target_column]) - set(class_to_index))
    if unknown_classes:
        raise RuntimeError(f"고정 CLASS_LABELS에 없는 클래스: {unknown_classes}")
    y = train[target_column].map(class_to_index).to_numpy(dtype=np.int32)
    fold_assignment = load_canonical_folds(
        split_path,
        train[id_column],
        id_column=id_column,
        fold_column=data["fold_column"],
    )

    gene_train, engineered_train, train_qc = build_stateless_features(
        train, gene_columns
    )
    gene_test, engineered_test, test_qc = build_stateless_features(test, gene_columns)
    if engineered_train.shape[1] != engineered_test.shape[1]:
        raise RuntimeError("train/test engineered feature 차원이 다릅니다.")

    slug = config["outputs"]["artifact_slug"]
    report_dir = ROOT / "reports" / slug
    model_dir = ROOT / "models" / slug
    oof_dir = ROOT / "oof"
    prediction_dir = ROOT / "preds"
    reproducibility_dir = ROOT / "reproducibility" / slug
    submission_path = ROOT / "submissions" / f"{slug}.csv"
    for directory in (report_dir, model_dir, oof_dir, prediction_dir, reproducibility_dir):
        directory.mkdir(parents=True, exist_ok=True)
    submission_path.parent.mkdir(parents=True, exist_ok=True)

    oof_probability = np.zeros((len(train), len(CLASS_LABELS)), dtype=np.float32)
    test_probability_folds: list[np.ndarray] = []
    fold_metrics: list[dict[str, Any]] = []
    search_records: list[dict[str, Any]] = []
    importance_totals: defaultdict[str, list[float]] = defaultdict(list)
    selected_gene_records: list[dict[str, Any]] = []

    for fold in range(5):
        outer_train = np.flatnonzero(fold_assignment != fold)
        outer_valid = np.flatnonzero(fold_assignment == fold)
        sampled, n_estimators, trials = tune_outer_fold(
            config,
            y,
            gene_train,
            engineered_train,
            outer_train,
            outer_fold=fold,
        )
        selected = select_gene_indices(
            gene_train,
            outer_train,
            minimum_support=int(config["features"]["minimum_fold_train_support"]),
            top_n=int(config["features"]["top_n_genes"]),
        )
        x_train = combine_features(
            gene_train, engineered_train, outer_train, selected
        )
        x_valid = combine_features(
            gene_train, engineered_train, outer_valid, selected
        )
        x_test = combine_features(
            gene_test,
            engineered_test,
            np.arange(len(test), dtype=np.int32),
            selected,
        )
        parameters = model_parameters(
            config,
            sampled,
            seed=seed + fold,
            n_estimators=n_estimators,
            early_stopping_rounds=None,
        )
        model = XGBClassifier(**parameters)
        weights = compute_sample_weight("balanced", y[outer_train])
        fold_started = time.perf_counter()
        model.fit(x_train, y[outer_train], sample_weight=weights, verbose=False)
        valid_probability = model.predict_proba(x_valid)
        test_probability = model.predict_proba(x_test)
        oof_probability[outer_valid] = valid_probability
        test_probability_folds.append(test_probability.astype(np.float32))
        valid_prediction = valid_probability.argmax(axis=1)
        metrics = {
            "fold": fold,
            "macro_f1": float(
                f1_score(y[outer_valid], valid_prediction, average="macro")
            ),
            "accuracy": float(accuracy_score(y[outer_valid], valid_prediction)),
            "log_loss": float(
                log_loss(
                    y[outer_valid],
                    valid_probability,
                    labels=np.arange(len(CLASS_LABELS)),
                )
            ),
            "best_iteration": n_estimators - 1,
        }
        fold_metrics.append(metrics)
        model_path = model_dir / f"fold_{fold:02d}.json"
        model.save_model(model_path)
        selected_names = [gene_columns[index] for index in selected]
        feature_names = selected_names + list(engineered_feature_names())
        for name, importance in zip(feature_names, model.feature_importances_):
            importance_totals[name].append(float(importance))
        selected_record = {
            "fold": fold,
            "selected_gene_indices": selected.tolist(),
            "selected_gene_names": selected_names,
            "selected_gene_count": len(selected_names),
            "parameters": parameters,
            "model_path": str(model_path.relative_to(ROOT)),
            "model_sha256": sha256_file(model_path),
        }
        selected_gene_records.append(selected_record)
        write_json(model_dir / f"fold_{fold:02d}_metadata.json", selected_record)
        search_records.append(
            {
                "fold": fold,
                "best_parameters": sampled,
                "selected_n_estimators": n_estimators,
                "trials": trials,
            }
        )
        print(
            json.dumps(
                {
                    **metrics,
                    "selected_genes": len(selected),
                    "elapsed_seconds": time.perf_counter() - fold_started,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    oof_prediction = oof_probability.argmax(axis=1)
    test_probability = np.mean(test_probability_folds, axis=0)
    test_prediction = test_probability.argmax(axis=1)

    oof_frame = pd.DataFrame(oof_probability, columns=CLASS_LABELS)
    oof_frame.insert(0, id_column, train[id_column].to_numpy())
    oof_frame["true_SUBCLASS"] = train[target_column].to_numpy()
    oof_frame["pred_SUBCLASS"] = np.asarray(CLASS_LABELS)[oof_prediction]
    oof_frame["fold"] = fold_assignment
    oof_path = oof_dir / f"{slug}.csv"
    oof_frame.to_csv(oof_path, index=False)

    test_frame = pd.DataFrame(test_probability, columns=CLASS_LABELS)
    test_frame.insert(0, id_column, test[id_column].to_numpy())
    test_probability_path = prediction_dir / f"{slug}_test_proba.csv"
    test_frame.to_csv(test_probability_path, index=False)

    sample_submission = pd.read_csv(sample_path)
    if sample_submission[id_column].astype(str).tolist() != test[id_column].tolist():
        raise RuntimeError("sample_submission과 test ID 순서가 다릅니다.")
    submission = pd.DataFrame(
        {
            id_column: test[id_column],
            target_column: np.asarray(CLASS_LABELS)[test_prediction],
        }
    )
    submission.to_csv(submission_path, index=False)

    class_report = classification_report(
        y,
        oof_prediction,
        labels=np.arange(len(CLASS_LABELS)),
        target_names=list(CLASS_LABELS),
        output_dict=True,
        zero_division=0,
    )
    importance = sorted(
        (
            {
                "feature": name,
                "mean_importance": float(np.mean(values)),
                "fold_occurrences": len(values),
            }
            for name, values in importance_totals.items()
        ),
        key=lambda item: (-item["mean_importance"], item["feature"]),
    )
    pd.DataFrame(importance).to_csv(report_dir / "feature_importance.csv", index=False)
    write_json(report_dir / "classification_report.json", class_report)
    write_json(report_dir / "nested_search.json", search_records)
    write_json(
        report_dir / "feature_contract.json",
        {
            "class_order": list(CLASS_LABELS),
            "gene_count": len(gene_columns),
            "engineered_feature_count": len(engineered_feature_names()),
            "train_qc": train_qc,
            "test_qc": test_qc,
            "fold_selected_genes": selected_gene_records,
            "test_used_for_fit": False,
            "smoteenn_used": False,
            "sample_weight": "balanced_per_training_partition",
        },
    )

    fold_scores = [item["macro_f1"] for item in fold_metrics]
    metrics_document = {
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
            "macro_f1": float(f1_score(y, oof_prediction, average="macro")),
            "fold_mean": float(np.mean(fold_scores)),
            "fold_std": float(np.std(fold_scores)),
            "accuracy": float(accuracy_score(y, oof_prediction)),
            "log_loss": float(
                log_loss(y, oof_probability, labels=np.arange(len(CLASS_LABELS)))
            ),
            "per_class_f1": {
                label: float(class_report[label]["f1-score"])
                for label in CLASS_LABELS
            },
            "confusion_matrix": confusion_matrix(
                y, oof_prediction, labels=np.arange(len(CLASS_LABELS))
            ).tolist(),
        },
        "leaderboard": None,
        "runtime": {
            "seconds": time.perf_counter() - started,
            "hardware": platform.platform(),
        },
        "artifacts": {
            "resolved_config": str(
                (reproducibility_dir / "config.resolved.yaml").relative_to(ROOT)
            ),
            "oof": str(oof_path.relative_to(ROOT)),
            "test_probability": str(test_probability_path.relative_to(ROOT)),
            "submission": str(submission_path.relative_to(ROOT)),
            "models": str(model_dir.relative_to(ROOT)),
            "submission_sha256": sha256_file(submission_path),
        },
        "notes": (
            "Issue #439. Canonical outer folds are fixed. Gene recurrence selection, "
            "Optuna tuning and balanced sample weights are fitted only inside the "
            "corresponding training partition. Test rows are transform-only. SMOTEENN "
            "is excluded because synthetic interpolation is not meaningful for sparse "
            "mutation indicators and discrete event counts."
        ),
    }
    metrics_path = report_dir / "metrics.json"
    write_json(metrics_path, metrics_document)

    resolved = dict(config)
    resolved["source"] = source
    resolved["data_hashes"] = {
        "train_sha256": sha256_file(train_path),
        "test_sha256": sha256_file(test_path),
        "canonical_split_sha256": sha256_file(split_path),
    }
    resolved["runtime"] = {
        "class_order": list(CLASS_LABELS),
        "folds": selected_gene_records,
    }
    (reproducibility_dir / "config.resolved.yaml").write_text(
        yaml.safe_dump(resolved, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    readme = (
        f"# {config['experiment_id']} fold-safe amino-acid × mutation XGBoost\n\n"
        f"- OOF Macro F1: `{metrics_document['oof']['macro_f1']:.10f}`\n"
        f"- OOF Accuracy: `{metrics_document['oof']['accuracy']:.10f}`\n"
        f"- OOF Log Loss: `{metrics_document['oof']['log_loss']:.10f}`\n"
        f"- Submission: `{submission_path.relative_to(ROOT)}`\n"
        "- Test rows were not used for fitting, selection, or tuning.\n"
        "- Reproducibility bundle: `NOT_STARTED` (prepare after leaderboard submission).\n"
    )
    (report_dir / "README.md").write_text(readme, encoding="utf-8")
    print(
        json.dumps(
            {
                "experiment_id": config["experiment_id"],
                "artifact_slug": slug,
                "oof_macro_f1": metrics_document["oof"]["macro_f1"],
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
        default=ROOT / "configs" / "exp439_fold_safe_aa_mutation_xgb.yaml",
    )
    arguments = parser.parse_args()
    main(arguments.config.resolve())
