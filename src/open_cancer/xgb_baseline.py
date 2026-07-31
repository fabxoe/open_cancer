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
        "gene_whitelist_path": None,
        "protect_gene_whitelist_path": None,
        "correlated_gene_top_k": None,
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


def read_gene_whitelist(path: str | Path) -> set[str]:
    """Read a whitelist CSV's `gene` column into a set."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} 를 찾을 수 없습니다. 라이선스 제한으로 Git에 커밋되지 "
            "않는 화이트리스트일 수 있으니, 로컬 재현 절차를 안내하는 문서를 먼저 확인하세요."
        )
    whitelist = pd.read_csv(path)
    if "gene" not in whitelist.columns:
        raise ValueError(f"화이트리스트 파일에 'gene' 컬럼이 없습니다: {path}")
    return set(whitelist["gene"])


def select_gene_columns(gene_columns: list[str], whitelist_path: str | Path) -> list[str]:
    """Filter gene_columns to a whitelist CSV's `gene` values, keeping train order."""
    whitelist_genes = read_gene_whitelist(whitelist_path)
    missing = whitelist_genes - set(gene_columns)
    if missing:
        raise ValueError(
            f"화이트리스트 유전자 중 train 컬럼에 없는 것이 있습니다: {sorted(missing)}"
        )

    selected = [gene for gene in gene_columns if gene in whitelist_genes]
    if not selected:
        raise ValueError(f"화이트리스트와 train 유전자 컬럼의 교집합이 비었습니다: {whitelist_path}")
    return selected


def _correlate_candidates_with_burden(
    feature_matrix: sparse.csr_matrix,
    protect_positions: list[int],
    candidate_positions: list[int],
) -> np.ndarray:
    """Pearson correlation of each candidate column with the protect-gene burden."""
    n_rows = feature_matrix.shape[0]
    burden = np.asarray(
        feature_matrix[:, protect_positions].sum(axis=1), dtype=np.float64
    ).ravel()
    candidate_matrix = feature_matrix[:, candidate_positions]

    sum_x = np.asarray(candidate_matrix.sum(axis=0), dtype=np.float64).ravel()
    sum_xy = candidate_matrix.T.dot(burden)
    sum_y = float(burden.sum())
    sum_yy = float(np.dot(burden, burden))

    numerator = n_rows * sum_xy - sum_x * sum_y
    denominator = np.sqrt((n_rows * sum_x - sum_x**2) * (n_rows * sum_yy - sum_y**2))
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(denominator > 0, numerator / denominator, 0.0)


def correlated_gene_weights(
    feature_matrix: sparse.csr_matrix,
    gene_columns: list[str],
    protect_genes: set[str],
    top_k: int,
) -> dict[str, float]:
    """Return {gene: |correlation|} for the top_k non-protect genes most
    correlated with protect-gene burden.

    Callers must pass a feature_matrix restricted to a single fold's training
    rows so the correlation is never informed by that fold's validation rows.
    """
    protect_positions = [i for i, gene in enumerate(gene_columns) if gene in protect_genes]
    candidate_positions = [i for i, gene in enumerate(gene_columns) if gene not in protect_genes]
    if not protect_positions:
        raise ValueError("protect_genes와 gene_columns의 교집합이 비었습니다.")
    if top_k < 1:
        raise ValueError("top_k는 1 이상이어야 합니다.")
    if top_k > len(candidate_positions):
        raise ValueError(
            f"top_k({top_k})가 후보 유전자 수({len(candidate_positions)})보다 큽니다."
        )

    correlation = _correlate_candidates_with_burden(
        feature_matrix, protect_positions, candidate_positions
    )
    order = np.argsort(-np.abs(correlation))[:top_k]
    return {gene_columns[candidate_positions[i]]: float(abs(correlation[i])) for i in order}


def select_correlated_genes(
    feature_matrix: sparse.csr_matrix,
    gene_columns: list[str],
    protect_genes: set[str],
    top_k: int,
) -> list[str]:
    """Return the top_k non-protect genes most correlated with protect-gene
    burden, in train column order. See correlated_gene_weights() for the
    fold-safety requirement on feature_matrix.
    """
    weights = correlated_gene_weights(feature_matrix, gene_columns, protect_genes, top_k)
    return [gene for gene in gene_columns if gene in weights]


def weighted_gene_burden(
    feature_matrix: sparse.csr_matrix,
    gene_columns: list[str],
    gene_weights: dict[str, float],
) -> np.ndarray:
    """Per-row weighted sum over genes in gene_weights (all other genes weighted 0)."""
    weights = np.array(
        [gene_weights.get(gene, 0.0) for gene in gene_columns],
        dtype=np.float64,
    )
    return np.asarray(feature_matrix.dot(weights), dtype=np.float32).ravel()


def weighted_protect_burden(
    feature_matrix: sparse.csr_matrix,
    gene_columns: list[str],
    protect_genes: set[str],
    correlated_weights: dict[str, float],
) -> np.ndarray:
    """Per-row score: protect genes weighted 1.0 plus correlated genes weighted
    by correlated_weights (see correlated_gene_weights), summed across genes.
    """
    gene_weights = {gene: 1.0 for gene in protect_genes}
    gene_weights.update(correlated_weights)
    return weighted_gene_burden(feature_matrix, gene_columns, gene_weights)


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
