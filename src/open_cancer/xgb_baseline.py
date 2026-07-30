"""Configuration and deterministic feature helpers for the XGBoost baseline."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from scipy import sparse

from open_cancer.constants import CLASS_LABELS

DEFAULT_XGB_BASELINE_CONFIG: dict[str, Any] = {
    "experiment": {
        "slug": "xgb_baseline",
    },
    "data": {
        "train_path": "data/raw/train.csv",
        "test_path": "data/raw/test.csv",
        "sample_submission_path": "data/raw/sample_submission.csv",
        "split_path": "data/splits/stratified_5fold_seed42.csv",
    },
    "run": {
        "seed": 42,
        "n_splits": 5,
        "n_jobs": 8,
    },
    "features": {
        "encoding": "mutation_presence",
        "include_mutation_burden": False,
        "empty_value_policy": "treat_as_wild_type",
        "matrix_format": "csr_float32",
    },
    "model": {
        "library": "xgboost",
        "class_name": "XGBClassifier",
        "use_balanced_sample_weight": False,
        "params": {
            "objective": "multi:softprob",
            "num_class": len(CLASS_LABELS),
            "n_estimators": 800,
            "learning_rate": 0.05,
            "max_depth": 4,
            "min_child_weight": 1.0,
            "subsample": 0.8,
            "colsample_bytree": 0.2,
            "reg_alpha": 0.0,
            "reg_lambda": 1.0,
            "gamma": 0.0,
            "eval_metric": "mlogloss",
            "early_stopping_rounds": 50,
            "tree_method": "hist",
            "device": "cpu",
            "verbosity": 0,
        },
    },
}


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Return a recursive merge without mutating either input mapping."""
    result = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_resolved_baseline_config(path: str | Path) -> dict[str, Any]:
    """Load optional YAML overrides and merge every project/model default."""
    path = Path(path)
    overrides = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(overrides, dict):
        raise ValueError("실험 config의 최상위 값은 mapping이어야 합니다.")

    resolved = _deep_merge(DEFAULT_XGB_BASELINE_CONFIG, overrides)
    if resolved["features"]["encoding"] != "mutation_presence":
        raise ValueError("이 baseline 실행기는 mutation_presence 인코딩만 지원합니다.")
    if int(resolved["run"]["n_splits"]) < 2:
        raise ValueError("n_splits는 2 이상이어야 합니다.")
    if int(resolved["run"]["n_jobs"]) < 1:
        raise ValueError("n_jobs는 1 이상이어야 합니다.")
    return resolved


def mutation_presence_matrix(
    frame: pd.DataFrame,
    gene_columns: list[str],
) -> sparse.csr_matrix:
    """Encode WT/empty as 0 and any mutation string as 1 in float32 CSR."""
    values = frame.loc[:, gene_columns]
    is_mutated = values.ne("WT") & values.ne("")
    return sparse.csr_matrix(
        is_mutated.to_numpy(dtype=np.float32, copy=False),
        dtype=np.float32,
    )


def encode_fixed_labels(labels: pd.Series) -> np.ndarray:
    """Encode targets using the immutable project class order."""
    label_to_index = {label: index for index, label in enumerate(CLASS_LABELS)}
    unknown = sorted(set(labels) - set(label_to_index))
    if unknown:
        raise ValueError(f"고정 클래스 순서에 없는 라벨입니다: {unknown}")
    return labels.map(label_to_index).to_numpy(dtype=np.int32)


def align_fold_ids(train_ids: pd.Series, fold_table: pd.DataFrame, n_splits: int) -> np.ndarray:
    """Align the canonical ID/fold table to train order with one-to-one checks."""
    if list(fold_table.columns) != ["ID", "fold"]:
        raise ValueError("공용 split 열은 ID,fold여야 합니다.")
    if fold_table["ID"].duplicated().any():
        raise ValueError("공용 split에 중복 ID가 있습니다.")
    if set(fold_table["ID"]) != set(train_ids):
        raise ValueError("공용 split과 train의 ID 집합이 다릅니다.")

    fold_by_id = fold_table.set_index("ID")["fold"]
    aligned = train_ids.map(fold_by_id)
    if aligned.isna().any():
        raise ValueError("공용 split에 없는 train ID가 있습니다.")

    fold_ids = aligned.to_numpy(dtype=np.int32)
    expected_folds = set(range(n_splits))
    if set(fold_ids) != expected_folds:
        raise ValueError(
            f"공용 split fold 집합이 다릅니다: {sorted(set(fold_ids))} / "
            f"{sorted(expected_folds)}"
        )
    return fold_ids
