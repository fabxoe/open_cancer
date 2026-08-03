"""Deterministic helpers for validation-only multiclass TreeSHAP audits."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def feature_family(name: str) -> str:
    """Return a stable, human-readable family for a feature name."""

    if name.startswith("sample__pathway_") or name.startswith("pathway__"):
        return "fixed_pathway"
    if name.startswith("sample__"):
        return "sample_aggregate"
    if name.startswith("hotspot__"):
        return "fixed_hotspot"
    if "__" not in name:
        return "other"
    suffix = name.rsplit("__", 1)[-1]
    if suffix in {
        "mutated",
        "missense",
        "synonymous",
        "nonsense",
        "frameshift",
        "complex",
        "missing",
        "max_residue_position",
    }:
        return f"gene_{suffix}"
    return "other"


def stratified_validation_sample(
    validation_indices: Sequence[int],
    target: np.ndarray,
    *,
    fold: int,
    class_count: int,
    max_per_class: int,
    seed: int,
) -> np.ndarray:
    """Select a deterministic class-stratified subset of one validation fold."""

    indices = np.asarray(validation_indices, dtype=np.int64)
    if indices.ndim != 1:
        raise ValueError("validation_indices must be one-dimensional")
    if max_per_class < 1:
        raise ValueError("max_per_class must be positive")
    if indices.size and (indices.min() < 0 or indices.max() >= len(target)):
        raise ValueError("validation index is outside target")

    selected: list[int] = []
    for class_index in range(class_count):
        candidates = indices[target[indices] == class_index]
        if candidates.size <= max_per_class:
            chosen = candidates
        else:
            rng = np.random.default_rng(seed + fold * 10_000 + class_index)
            chosen = np.sort(rng.choice(candidates, size=max_per_class, replace=False))
        selected.extend(int(value) for value in chosen)
    return np.asarray(sorted(selected), dtype=np.int64)


def accumulate_contribution_chunk(
    contributions: np.ndarray,
    target: np.ndarray,
    *,
    class_count: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Reduce one ``(rows, classes, features+1)`` SHAP chunk.

    The final column is the expected-value bias and is deliberately excluded.
    The first output sums absolute SHAP over every output class. The second
    keeps the absolute contribution for each row's true-class output only.
    """

    values = np.asarray(contributions)
    labels = np.asarray(target, dtype=np.int64)
    if values.ndim != 3:
        raise ValueError("contributions must have shape (rows, classes, features+1)")
    if values.shape[0] != labels.size or values.shape[1] != class_count:
        raise ValueError("contribution and target shapes do not agree")
    if values.shape[2] < 2:
        raise ValueError("contributions must contain at least one feature and bias")
    if labels.size and (labels.min() < 0 or labels.max() >= class_count):
        raise ValueError("target contains an invalid class index")

    feature_values = np.abs(values[:, :, :-1]).astype(np.float64, copy=False)
    global_sum = feature_values.sum(axis=(0, 1))
    true_class_sum = np.zeros((class_count, feature_values.shape[2]), dtype=np.float64)
    class_rows = np.zeros(class_count, dtype=np.int64)
    for class_index in range(class_count):
        mask = labels == class_index
        class_rows[class_index] = int(mask.sum())
        if mask.any():
            true_class_sum[class_index] = feature_values[mask, class_index].sum(axis=0)
    return global_sum, true_class_sum, class_rows
