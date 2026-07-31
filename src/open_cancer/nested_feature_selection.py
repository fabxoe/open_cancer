"""Leakage-safe nested permutation selection for EXP-045."""

from __future__ import annotations

from typing import Any

import numpy as np
import xgboost as xgb
from scipy import sparse
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.mutation_features import (
    LOG_BURDEN_FEATURES,
    MUTATION_TYPES,
    SAMPLE_DISTRIBUTION_FEATURES,
)


EXP043_CANDIDATE_GROUPS = {
    "log_burden": LOG_BURDEN_FEATURES,
    "mutation_type_log_counts": tuple(
        f"sample__{mutation_type}_count_log1p"
        for mutation_type in MUTATION_TYPES
    ),
    "mutation_type_affected_gene_counts": tuple(
        feature
        for feature in SAMPLE_DISTRIBUTION_FEATURES
        if "_gene_count" in feature and "single_variant" not in feature
    ),
    "functional_impact_proxies": (
        "sample__truncating_count",
        "sample__truncating_count_log1p",
        "sample__damaging_count",
        "sample__damaging_count_log1p",
    ),
    "mutation_type_mix": (
        "sample__mutation_type_diversity",
        "sample__mutation_type_entropy",
    ),
    "per_gene_distribution": (
        "sample__variants_per_mutated_gene_mean",
        "sample__max_variants_per_gene",
        "sample__single_variant_gene_count",
        "sample__single_variant_gene_count_log1p",
    ),
}


def permute_columns(
    matrix: sparse.csr_matrix,
    column_indices: list[int],
    permutation: np.ndarray,
) -> sparse.csr_matrix:
    """Return a copy with a small feature block jointly permuted by row."""

    if not column_indices:
        return matrix.copy()
    modified = matrix.tolil(copy=True)
    block = matrix[:, column_indices].toarray()
    modified[:, column_indices] = block[permutation]
    return modified.tocsr()


def select_nested_features(
    *,
    matrix: sparse.csr_matrix,
    labels: np.ndarray,
    outer_train_indices: np.ndarray,
    feature_names: list[str],
    candidate_groups: dict[str, tuple[str, ...]],
    model_params: dict[str, Any],
    seed: int,
    inner_splits: int,
    minimum_positive_folds: int,
    balanced_sample_weight: bool,
) -> tuple[list[int], dict[str, Any]]:
    """Select candidate groups, then features, using only outer-train rows."""

    name_to_index = {name: index for index, name in enumerate(feature_names)}
    candidate_names = tuple(
        name for names in candidate_groups.values() for name in names
    )
    if len(set(candidate_names)) != len(candidate_names):
        raise ValueError("candidate_groups 안에서 피처가 중복됐습니다.")
    missing = sorted(set(candidate_names) - set(name_to_index))
    if missing:
        raise ValueError(f"후보 피처가 전체 피처에 없습니다: {missing}")

    candidate_indices = {name: name_to_index[name] for name in candidate_names}
    inner = StratifiedKFold(
        n_splits=inner_splits,
        shuffle=True,
        random_state=seed,
    )
    outer_labels = labels[outer_train_indices]
    group_drops = {group: [] for group in candidate_groups}
    feature_drops = {name: [] for name in candidate_names}
    inner_rows: list[dict[str, Any]] = []

    for inner_fold, (fit_local, valid_local) in enumerate(
        inner.split(np.zeros(len(outer_train_indices)), outer_labels)
    ):
        fit_indices = outer_train_indices[fit_local]
        valid_indices = outer_train_indices[valid_local]
        y_fit = labels[fit_indices]
        y_valid = labels[valid_indices]
        model = xgb.XGBClassifier(
            **model_params,
            random_state=seed + inner_fold,
        )
        weights = (
            compute_sample_weight(class_weight="balanced", y=y_fit)
            if balanced_sample_weight
            else None
        )
        model.fit(
            matrix[fit_indices],
            y_fit,
            sample_weight=weights,
            eval_set=[(matrix[valid_indices], y_valid)],
            verbose=False,
        )
        baseline = float(
            f1_score(
                y_valid,
                model.predict(matrix[valid_indices]),
                average="macro",
            )
        )
        permutation = np.random.default_rng(seed + inner_fold).permutation(
            len(valid_indices)
        )
        fold_group_drops: dict[str, float] = {}
        for group, names in candidate_groups.items():
            permuted = permute_columns(
                matrix[valid_indices],
                [candidate_indices[name] for name in names],
                permutation,
            )
            score = float(
                f1_score(y_valid, model.predict(permuted), average="macro")
            )
            drop = baseline - score
            group_drops[group].append(drop)
            fold_group_drops[group] = drop

        fold_feature_drops: dict[str, float] = {}
        for name, column_index in candidate_indices.items():
            permuted = permute_columns(
                matrix[valid_indices],
                [column_index],
                permutation,
            )
            score = float(
                f1_score(y_valid, model.predict(permuted), average="macro")
            )
            drop = baseline - score
            feature_drops[name].append(drop)
            fold_feature_drops[name] = drop
        inner_rows.append(
            {
                "inner_fold": inner_fold,
                "baseline_macro_f1": baseline,
                "group_macro_f1_drops": fold_group_drops,
                "feature_macro_f1_drops": fold_feature_drops,
            }
        )

    selected_groups = [
        group
        for group, drops in group_drops.items()
        if sum(drop > 0 for drop in drops) >= minimum_positive_folds
    ]
    allowed_features = {
        name for group in selected_groups for name in candidate_groups[group]
    }
    selected_features = [
        name
        for name, drops in feature_drops.items()
        if name in allowed_features
        and sum(drop > 0 for drop in drops) >= minimum_positive_folds
    ]
    selected_set = set(selected_features)
    selected_indices = [
        index
        for index, name in enumerate(feature_names)
        if name not in candidate_indices or name in selected_set
    ]
    return selected_indices, {
        "selected_groups": selected_groups,
        "selected_features": selected_features,
        "group_positive_fold_counts": {
            group: sum(drop > 0 for drop in drops)
            for group, drops in group_drops.items()
        },
        "feature_positive_fold_counts": {
            name: sum(drop > 0 for drop in drops)
            for name, drops in feature_drops.items()
        },
        "inner_folds": inner_rows,
    }
