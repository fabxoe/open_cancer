"""Mechanical train-support gates for parser semantic families."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence


SupportDecision = Literal[
    "EXPERIMENT_ELIGIBLE", "ANALYSIS_ONLY", "UNRESOLVED_ONLY"
]


@dataclass(frozen=True)
class SupportGateResult:
    decision: SupportDecision
    reason: str


def support_family_key(
    *,
    route: str,
    event_type: str,
    payload: Mapping[str, Any],
) -> tuple[str, str]:
    """Return the audit key without collapsing stop-containing ranges.

    A range replacement whose alternate sequence contains a non-immediate stop
    remains ``event_type=range_replacement`` in the semantic router.  The
    support audit must nevertheless keep it separate from ordinary ranges so
    an experiment cannot silently combine two biological consequences.
    """

    if (
        route == "range_replacement"
        and event_type == "range_replacement"
        and payload.get("contains_stop") is True
    ):
        return route, "stop_containing"
    return route, event_type


def decide_support_gate(
    *,
    route: str,
    train_sample_count: int,
    fold_sample_counts: Sequence[int],
    minimum_total_samples: int = 50,
    minimum_samples_per_fold: int = 5,
) -> SupportGateResult:
    """Apply a feasibility gate, never a performance/feature-selection gate."""

    if route == "unresolved":
        return SupportGateResult(
            "UNRESOLVED_ONLY",
            "semantic route is unresolved and remains provenance/QC only",
        )
    if train_sample_count == 0:
        return SupportGateResult(
            "ANALYSIS_ONLY", "family has zero train samples"
        )
    if len(fold_sample_counts) != 5 or min(fold_sample_counts, default=0) < minimum_samples_per_fold:
        return SupportGateResult(
            "ANALYSIS_ONLY",
            f"canonical fold support is below {minimum_samples_per_fold} samples",
        )
    if train_sample_count < minimum_total_samples:
        return SupportGateResult(
            "ANALYSIS_ONLY",
            f"train support is below {minimum_total_samples} samples",
        )
    return SupportGateResult(
        "EXPERIMENT_ELIGIBLE",
        "mechanical train/fold support gate passed; performance is untested",
    )
