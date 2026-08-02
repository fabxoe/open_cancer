"""Fold-local categorical summaries for correlated mutation-presence pairs."""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from scipy import sparse

from open_cancer.fold_feature_selection import FoldFeatureSelectionError


PAIR_CATEGORIES = ("only_left", "only_right", "both_mutated")


def pair_feature_names(pairs: Sequence[dict[str, Any]]) -> tuple[str, ...]:
    """Return deterministic names for the three states of every gene pair."""
    names: list[str] = []
    for pair in pairs:
        left = str(pair["left_gene"])
        right = str(pair["right_gene"])
        prefix = f"correlation_pair__{left}__{right}"
        names.extend(f"{prefix}__{category}" for category in PAIR_CATEGORIES)
    return tuple(names)


def append_pair_categorical_features(
    features: sparse.csr_matrix,
    feature_names: Sequence[str],
    pairs: Sequence[dict[str, Any]],
) -> sparse.csr_matrix:
    """Append only-left, only-right and both-mutated features for fixed pairs.

    ``pairs`` must have been selected from the outer training split. This
    transformer only applies that frozen list, so validation and test values do
    not affect which pairs exist.
    """
    if not sparse.isspmatrix_csr(features):
        raise FoldFeatureSelectionError("pair feature 입력은 CSR sparse matrix여야 합니다.")
    if not pairs:
        return features
    name_to_index = {str(name): index for index, name in enumerate(feature_names)}
    columns: list[sparse.csr_matrix] = []
    for pair in pairs:
        left_name = f"{pair['left_gene']}__mutated"
        right_name = f"{pair['right_gene']}__mutated"
        if left_name not in name_to_index or right_name not in name_to_index:
            raise FoldFeatureSelectionError(f"pair 유전자 feature가 없습니다: {left_name}, {right_name}")
        left = features[:, name_to_index[left_name]].astype(np.int8)
        right = features[:, name_to_index[right_name]].astype(np.int8)
        left.data = np.ones_like(left.data, dtype=np.int8)
        right.data = np.ones_like(right.data, dtype=np.int8)
        both = left.multiply(right).tocsr()
        only_left = (left - both).tocsr()
        only_right = (right - both).tocsr()
        columns.extend((only_left, only_right, both))
    return sparse.hstack((features, *columns), format="csr", dtype=np.float32)
