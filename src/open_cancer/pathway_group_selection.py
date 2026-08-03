"""Leakage-safe helpers for pathway-group permutation selection."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def summarize_group_importance(
    records: Iterable[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Aggregate inner-fold permutation deltas without using outer validation."""
    grouped: dict[str, list[float]] = {}
    for record in records:
        grouped.setdefault(str(record["group"]), []).append(float(record["mean_delta"]))
    return {
        group: {
            "inner_fold_deltas": values,
            "positive_inner_folds": sum(value > 0.0 for value in values),
            "mean_delta": sum(values) / len(values),
        }
        for group, values in sorted(grouped.items())
    }


def select_recurrent_positive_groups(
    records: Iterable[dict[str, Any]],
    *,
    minimum_positive_inner_folds: int,
    minimum_mean_delta: float = 0.0,
) -> tuple[tuple[str, ...], dict[str, dict[str, Any]]]:
    """Keep groups with recurrent positive importance across inner folds."""
    if minimum_positive_inner_folds < 1:
        raise ValueError("minimum_positive_inner_folds는 1 이상이어야 합니다.")
    summary = summarize_group_importance(records)
    selected = tuple(
        group
        for group, values in summary.items()
        if values["positive_inner_folds"] >= minimum_positive_inner_folds
        and values["mean_delta"] > minimum_mean_delta
    )
    return selected, summary
