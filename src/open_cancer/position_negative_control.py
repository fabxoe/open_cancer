"""Leakage-safe residue-position permutation helpers for negative controls."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

import numpy as np
from scipy import sparse


DEFAULT_STRATA_SUFFIXES = (
    "missense",
    "synonymous",
    "nonsense",
    "frameshift",
    "complex",
)


def feature_indices_with_suffix(
    feature_names: list[str], suffix: str
) -> tuple[list[str], list[int]]:
    """Return gene names and feature indices for an exact ``__suffix``."""

    marker = f"__{suffix}"
    pairs = [
        (name[: -len(marker)], index)
        for index, name in enumerate(feature_names)
        if name.endswith(marker)
    ]
    if not pairs:
        raise ValueError(f"피처를 찾을 수 없습니다: *{marker}")
    genes, indices = zip(*pairs, strict=True)
    return list(genes), list(indices)


def permute_position_values(
    matrix: sparse.spmatrix,
    feature_names: list[str],
    *,
    position_feature: str = "max_residue_position",
    seed: int,
    strata_suffixes: Iterable[str] = DEFAULT_STRATA_SUFFIXES,
) -> tuple[sparse.csr_matrix, dict[str, Any]]:
    """Shuffle observed position values within gene and mutation-type strata.

    Only non-zero values are permuted. Therefore every row/column support value,
    including mutation presence and the position-observed mask, stays unchanged.
    The caller must pass only an outer-fold training matrix; validation and test
    matrices must never be passed to this function.
    """

    if matrix.shape[1] != len(feature_names):
        raise ValueError("피처 행렬 열 수와 feature_names 수가 다릅니다.")

    genes, position_indices = feature_indices_with_suffix(
        feature_names, position_feature
    )
    name_to_index = {name: index for index, name in enumerate(feature_names)}
    strata_suffixes = tuple(strata_suffixes)
    strata_by_gene: dict[str, list[int]] = {}
    for gene in genes:
        indices = [
            name_to_index[f"{gene}__{suffix}"]
            for suffix in strata_suffixes
            if f"{gene}__{suffix}" in name_to_index
        ]
        if not indices:
            raise ValueError(f"{gene}의 permutation strata 피처를 찾을 수 없습니다.")
        strata_by_gene[gene] = indices

    source = matrix.tocsr(copy=False)
    result = matrix.tocsc(copy=True)
    rng = np.random.default_rng(seed)
    observed_values = 0
    shuffled_values = 0
    changed_values = 0
    eligible_groups = 0
    singleton_groups = 0

    for gene, column_index in zip(genes, position_indices, strict=True):
        start = int(result.indptr[column_index])
        stop = int(result.indptr[column_index + 1])
        if stop == start:
            continue
        rows = result.indices[start:stop]
        values = result.data[start:stop]
        if np.any(values <= 0):
            raise ValueError("position sparse data에는 양수만 저장되어야 합니다.")
        observed_values += len(values)

        signatures = (
            source[rows][:, strata_by_gene[gene]].astype(bool).toarray()
        )
        groups: dict[bytes, list[int]] = defaultdict(list)
        for local_index, signature in enumerate(signatures):
            groups[np.packbits(signature).tobytes()].append(local_index)

        original = values.copy()
        for local_indices in groups.values():
            if len(local_indices) < 2:
                singleton_groups += 1
                continue
            eligible_groups += 1
            shuffled_values += len(local_indices)
            selected = np.asarray(local_indices, dtype=np.int64)
            permuted = values[selected].copy()
            rng.shuffle(permuted)
            values[selected] = permuted
        changed_values += int(np.count_nonzero(values != original))

    permuted = result.tocsr()
    source_support = source.copy()
    permuted_support = permuted.copy()
    source_support.data = np.ones(source_support.nnz, dtype=np.int8)
    permuted_support.data = np.ones(permuted_support.nnz, dtype=np.int8)
    support_mismatches = int((source_support != permuted_support).nnz)
    if support_mismatches:
        raise AssertionError("permutation이 sparse support를 변경했습니다.")

    return permuted, {
        "seed": seed,
        "position_feature": position_feature,
        "strata_suffixes": list(strata_suffixes),
        "observed_values": observed_values,
        "values_in_shuffle_eligible_groups": shuffled_values,
        "changed_values": changed_values,
        "eligible_groups": eligible_groups,
        "singleton_groups": singleton_groups,
        "support_mismatches": support_mismatches,
    }
