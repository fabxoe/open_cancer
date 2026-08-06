"""Fold-safe parser-v4 Hotspot-12 features.

The transformer learns one narrow missense-residue window per supported gene
from an outer-training partition.  Validation and test rows can only be
transformed with those frozen windows.  A patient contributes at most once to
each ``(gene, residue_position)`` support count, preventing repeated tokens or
isoform annotations from inflating a hotspot.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.canonical_mutation_events import (
    CANONICAL_PARSER_CONTRACT_KEY,
    parse_canonical_gene_cell,
)
from open_cancer.feature_family import FeatureFamilyDescriptor
from open_cancer.hashing import sha256_lines


HOTSPOT12_VERSION = "1.0.0"
DEFAULT_WINDOW_WIDTH = 12
DEFAULT_MIN_EVENT_SUPPORT = 5
DEFAULT_MIN_WINDOW_FRACTION = 0.40
AGGREGATE_FEATURE_NAMES = (
    "sample__hotspot12_gene_count",
    "sample__hotspot12_event_count",
    "sample__hotspot12_fraction",
)


def _non_wt(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value.strip().upper() != "WT"


def _missense_positions(value: object) -> tuple[int, ...]:
    """Return unique positive parser-v4 missense residue positions."""

    if not _non_wt(value):
        return ()
    positions: set[int] = set()
    for event in parse_canonical_gene_cell(value).events:
        if event.route != "substitution" or event.event_type != "missense":
            continue
        if event.parse_status in {"unresolved", "not_applicable"}:
            continue
        if event.payload.get("position_eligible") is False:
            continue
        positions.update(int(position) for position in event.positions if int(position) > 0)
    return tuple(sorted(positions))


def _json_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _best_window(
    position_counts: Counter[int], *, window_width: int
) -> tuple[int, int, int]:
    """Return deterministic ``(start, end, count)`` for the densest window."""

    if not position_counts:
        raise ValueError("position_counts가 비어 있습니다.")
    ordered = sorted(position_counts.items())
    best_start = ordered[0][0]
    best_count = -1
    right = 0
    running_count = 0
    for left, (start, left_count) in enumerate(ordered):
        if left > 0:
            running_count -= ordered[left - 1][1]
        while right < len(ordered) and ordered[right][0] <= start + window_width - 1:
            running_count += ordered[right][1]
            right += 1
        count = running_count
        if count > best_count or (count == best_count and start < best_start):
            best_start = start
            best_count = count
    return best_start, best_start + window_width - 1, best_count


@dataclass(frozen=True)
class Hotspot12WindowProfile:
    gene: str
    window_start: int
    window_end: int
    total_event_support: int
    window_event_support: int
    window_fraction: float
    patient_support: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene": self.gene,
            "window_start": self.window_start,
            "window_end": self.window_end,
            "total_event_support": self.total_event_support,
            "window_event_support": self.window_event_support,
            "window_fraction": self.window_fraction,
            "patient_support": self.patient_support,
        }


@dataclass(frozen=True)
class FittedResidueHotspot12Family:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    window_width: int
    min_event_support: int
    min_window_fraction: float
    profiles: tuple[Hotspot12WindowProfile, ...]
    fit_audit: dict[str, int]

    def metadata(self) -> dict[str, Any]:
        records = [profile.to_dict() for profile in self.profiles]
        return {
            "family": self.descriptor.name,
            "version": self.descriptor.version,
            "fit_scope": self.descriptor.fit_scope,
            "parser_contract_key": CANONICAL_PARSER_CONTRACT_KEY,
            "event_scope": "parser_v4_substitution_missense_resolved_positive_position",
            "deduplication_unit": "patient_gene_residue_position",
            "window_width": self.window_width,
            "min_event_support": self.min_event_support,
            "min_window_fraction": self.min_window_fraction,
            "candidate_gene_count": self.fit_audit["candidate_gene_count"],
            "selected_gene_count": len(self.profiles),
            "selected_genes": [profile.gene for profile in self.profiles],
            "window_profiles": records,
            "window_profiles_sha256": _json_sha256(records),
            "feature_names_sha256": self.descriptor.feature_names_sha256,
            "gene_columns_sha256": sha256_lines(self.gene_columns),
            "fraction_denominator": "eligible_missense_events_in_selected_genes",
            "fit_audit": dict(self.fit_audit),
            "target_used_for_fit": False,
            "validation_used_for_fit": False,
            "test_distribution_used_for_fit": False,
        }

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")

        gene_index = {gene: index for index, gene in enumerate(self.gene_columns)}
        rows: list[int] = []
        columns: list[int] = []
        data: list[float] = []
        gene_counts = np.zeros(len(frame), dtype=np.float32)
        hotspot_event_counts = np.zeros(len(frame), dtype=np.float32)
        eligible_event_counts = np.zeros(len(frame), dtype=np.float32)

        for profile in self.profiles:
            feature_column = gene_index[profile.gene]
            raw_values = frame[profile.gene].to_numpy(dtype=object, copy=False)
            for row_index, raw_value in enumerate(raw_values):
                positions = _missense_positions(raw_value)
                if not positions:
                    continue
                eligible_event_counts[row_index] += len(positions)
                hits = sum(
                    profile.window_start <= position <= profile.window_end
                    for position in positions
                )
                if hits == 0:
                    continue
                rows.append(row_index)
                columns.append(feature_column)
                data.append(1.0)
                gene_counts[row_index] += 1.0
                hotspot_event_counts[row_index] += float(hits)

        indicators = sparse.csr_matrix(
            (np.asarray(data, dtype=np.float32), (rows, columns)),
            shape=(len(frame), len(self.gene_columns)),
            dtype=np.float32,
        )
        aggregates = np.zeros((len(frame), len(AGGREGATE_FEATURE_NAMES)), dtype=np.float32)
        aggregates[:, 0] = gene_counts
        aggregates[:, 1] = hotspot_event_counts
        observed = eligible_event_counts > 0
        aggregates[observed, 2] = (
            hotspot_event_counts[observed] / eligible_event_counts[observed]
        )
        return sparse.hstack([indicators, sparse.csr_matrix(aggregates)], format="csr")


@dataclass(frozen=True)
class ResidueHotspot12Family:
    gene_columns: tuple[str, ...]
    window_width: int = DEFAULT_WINDOW_WIDTH
    min_event_support: int = DEFAULT_MIN_EVENT_SUPPORT
    min_window_fraction: float = DEFAULT_MIN_WINDOW_FRACTION
    version: str = HOTSPOT12_VERSION

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedResidueHotspot12Family:
        del target
        if self.window_width < 1:
            raise ValueError("window_width는 1 이상이어야 합니다.")
        if self.min_event_support < 1:
            raise ValueError("min_event_support는 1 이상이어야 합니다.")
        if not 0 < self.min_window_fraction <= 1:
            raise ValueError("min_window_fraction은 0 초과 1 이하여야 합니다.")
        if not self.gene_columns:
            raise ValueError("유전자 열이 하나 이상 필요합니다.")
        missing = [gene for gene in self.gene_columns if gene not in train_frame.columns]
        if missing:
            raise ValueError(f"학습 입력에 유전자 열이 없습니다: {missing[:5]}")

        profiles: list[Hotspot12WindowProfile] = []
        candidate_gene_count = 0
        genes_with_any_eligible_event = 0
        total_eligible_events = 0
        for gene in self.gene_columns:
            position_counts: Counter[int] = Counter()
            patient_support = 0
            for raw_value in train_frame[gene].to_numpy(dtype=object, copy=False):
                positions = _missense_positions(raw_value)
                if not positions:
                    continue
                patient_support += 1
                position_counts.update(positions)
            total = sum(position_counts.values())
            total_eligible_events += total
            if total:
                genes_with_any_eligible_event += 1
            if total < self.min_event_support:
                continue
            candidate_gene_count += 1
            start, end, window_count = _best_window(
                position_counts, window_width=self.window_width
            )
            fraction = window_count / total
            if fraction < self.min_window_fraction:
                continue
            profiles.append(
                Hotspot12WindowProfile(
                    gene=gene,
                    window_start=start,
                    window_end=end,
                    total_event_support=total,
                    window_event_support=window_count,
                    window_fraction=fraction,
                    patient_support=patient_support,
                )
            )

        profiles.sort(key=lambda profile: profile.gene)
        feature_names = tuple(
            f"gene__{gene}__hotspot12_hit" for gene in self.gene_columns
        ) + AGGREGATE_FEATURE_NAMES
        return FittedResidueHotspot12Family(
            descriptor=FeatureFamilyDescriptor(
                name="residue_hotspot12",
                version=self.version,
                fit_scope="fold_train",
                feature_names=feature_names,
            ),
            gene_columns=self.gene_columns,
            window_width=self.window_width,
            min_event_support=self.min_event_support,
            min_window_fraction=self.min_window_fraction,
            profiles=tuple(profiles),
            fit_audit={
                "row_count": len(train_frame),
                "genes_with_any_eligible_event": genes_with_any_eligible_event,
                "candidate_gene_count": candidate_gene_count,
                "selected_gene_count": len(profiles),
                "total_eligible_event_support": total_eligible_events,
            },
        )


def summarize_fold_stability(
    fitted_folds: Sequence[FittedResidueHotspot12Family],
) -> dict[str, Any]:
    """Summarize selected-gene overlap and exact-window stability."""

    selected = [set(profile.gene for profile in fitted.profiles) for fitted in fitted_folds]
    pairwise_jaccard: list[float] = []
    for left_index, left in enumerate(selected):
        for right in selected[left_index + 1 :]:
            union = left | right
            pairwise_jaccard.append(len(left & right) / len(union) if union else 1.0)

    windows_by_gene: dict[str, set[tuple[int, int]]] = {}
    fold_support_by_gene: Counter[str] = Counter()
    for fitted in fitted_folds:
        for profile in fitted.profiles:
            fold_support_by_gene[profile.gene] += 1
            windows_by_gene.setdefault(profile.gene, set()).add(
                (profile.window_start, profile.window_end)
            )
    exact_window_stable = sum(
        1
        for gene, windows in windows_by_gene.items()
        if fold_support_by_gene[gene] == len(fitted_folds) and len(windows) == 1
    )
    return {
        "fold_count": len(fitted_folds),
        "selected_gene_counts": [len(item) for item in selected],
        "pairwise_gene_jaccard": pairwise_jaccard,
        "mean_pairwise_gene_jaccard": (
            float(np.mean(pairwise_jaccard)) if pairwise_jaccard else 1.0
        ),
        "genes_selected_in_all_folds": sorted(
            gene
            for gene, count in fold_support_by_gene.items()
            if count == len(fitted_folds)
        ),
        "genes_with_exact_window_in_all_folds": exact_window_stable,
    }


def metadata_json(fitted: FittedResidueHotspot12Family) -> str:
    return json.dumps(fitted.metadata(), ensure_ascii=False, sort_keys=True, indent=2)
