"""Fold-safe gene residue-event concentration features.

The family learns a coarse residue-bin distribution for each gene from one
outer-training partition. Validation and test rows only look up that frozen
distribution. A patient contributes at most once to a ``(gene, bin)`` pair,
so repeated source tokens or isoform-like duplicates cannot inflate support.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.canonical_mutation_events import parse_canonical_gene_cell
from open_cancer.feature_family import FeatureFamilyDescriptor
from open_cancer.hashing import sha256_lines


RESIDUE_EVENT_CONCENTRATION_VERSION = "1.0.0"
DEFAULT_BIN_WIDTH = 50
DEFAULT_MIN_PATIENT_BIN_SUPPORT = 20
FEATURE_NAMES = (
    "sample__residue_concentration_top_bin_hit_fraction",
    "sample__residue_concentration_mean_observed_bin_share",
    "sample__residue_concentration_mean_gene_hhi",
    "sample__residue_concentration_mean_gene_normalized_entropy",
)


def _non_wt(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value.strip().upper() != "WT"


def _eligible_positions(value: object) -> tuple[int, ...]:
    """Return parser-v4 positions that are safe for residue aggregation."""

    if not _non_wt(value):
        return ()
    positions: set[int] = set()
    for event in parse_canonical_gene_cell(value).events:
        # Parser-v4 frameshift grammars are intentionally ``partial`` because
        # the shifted peptide/termination distance is unknown, while their
        # positive anchor residue remains position-eligible.
        if event.route == "unresolved" or event.parse_status in {
            "unresolved",
            "not_applicable",
        }:
            continue
        if event.payload.get("position_eligible") is False:
            continue
        positions.update(int(position) for position in event.positions if int(position) > 0)
    return tuple(sorted(positions))


def _position_bins(value: object, *, bin_width: int) -> tuple[int, ...]:
    """Map eligible one-based residues to zero-based fixed-width bins."""

    return tuple(sorted({(position - 1) // bin_width for position in _eligible_positions(value)}))


def _json_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class GeneConcentrationProfile:
    gene: str
    patient_bin_support: int
    patient_support: int
    bin_counts: tuple[tuple[int, int], ...]
    bin_shares: tuple[tuple[int, float], ...]
    top_bin: int
    hhi: float
    normalized_entropy: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "gene": self.gene,
            "patient_bin_support": self.patient_bin_support,
            "patient_support": self.patient_support,
            "bin_counts": {str(key): value for key, value in self.bin_counts},
            "bin_shares": {str(key): value for key, value in self.bin_shares},
            "top_bin": self.top_bin,
            "hhi": self.hhi,
            "normalized_entropy": self.normalized_entropy,
        }


@dataclass(frozen=True)
class FittedResidueEventConcentrationFamily:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    bin_width: int
    min_patient_bin_support: int
    profiles: tuple[GeneConcentrationProfile, ...]

    def metadata(self) -> dict[str, Any]:
        profile_records = [profile.to_dict() for profile in self.profiles]
        return {
            "family": self.descriptor.name,
            "version": self.descriptor.version,
            "fit_scope": self.descriptor.fit_scope,
            "bin_width": self.bin_width,
            "min_patient_bin_support": self.min_patient_bin_support,
            "deduplication_unit": "patient_gene_bin",
            "position_source": "parser_v4_position_eligible_only",
            "gated_gene_count": len(self.profiles),
            "gated_genes": [profile.gene for profile in self.profiles],
            "gene_profiles": profile_records,
            "gene_profiles_sha256": _json_sha256(profile_records),
            "feature_names_sha256": self.descriptor.feature_names_sha256,
            "gene_columns_sha256": sha256_lines(self.gene_columns),
            "target_used_for_fit": False,
            "validation_used_for_fit": False,
            "test_distribution_used_for_fit": False,
        }

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")

        profiles = {profile.gene: profile for profile in self.profiles}
        values = np.zeros((len(frame), len(FEATURE_NAMES)), dtype=np.float32)
        top_hits = np.zeros(len(frame), dtype=np.float64)
        gene_observations = np.zeros(len(frame), dtype=np.int64)
        share_sums = np.zeros(len(frame), dtype=np.float64)
        share_observations = np.zeros(len(frame), dtype=np.int64)
        hhi_sums = np.zeros(len(frame), dtype=np.float64)
        entropy_sums = np.zeros(len(frame), dtype=np.float64)

        for gene, profile in profiles.items():
            share_lookup = dict(profile.bin_shares)
            gene_values = frame[gene].to_numpy(dtype=object, copy=False)
            for row_index, raw_value in enumerate(gene_values):
                bins = _position_bins(raw_value, bin_width=self.bin_width)
                if not bins:
                    continue
                gene_observations[row_index] += 1
                top_hits[row_index] += float(profile.top_bin in bins)
                share_sums[row_index] += sum(
                    share_lookup.get(bin_index, 0.0) for bin_index in bins
                )
                share_observations[row_index] += len(bins)
                hhi_sums[row_index] += profile.hhi
                entropy_sums[row_index] += profile.normalized_entropy

        observed_gene_rows = gene_observations > 0
        observed_bin_rows = share_observations > 0
        values[observed_gene_rows, 0] = (
            top_hits[observed_gene_rows] / gene_observations[observed_gene_rows]
        ).astype(np.float32)
        values[observed_bin_rows, 1] = (
            share_sums[observed_bin_rows] / share_observations[observed_bin_rows]
        ).astype(np.float32)
        values[observed_gene_rows, 2] = (
            hhi_sums[observed_gene_rows] / gene_observations[observed_gene_rows]
        ).astype(np.float32)
        values[observed_gene_rows, 3] = (
            entropy_sums[observed_gene_rows] / gene_observations[observed_gene_rows]
        ).astype(np.float32)
        return sparse.csr_matrix(values)


@dataclass(frozen=True)
class ResidueEventConcentrationFamily:
    gene_columns: tuple[str, ...]
    bin_width: int = DEFAULT_BIN_WIDTH
    min_patient_bin_support: int = DEFAULT_MIN_PATIENT_BIN_SUPPORT
    version: str = RESIDUE_EVENT_CONCENTRATION_VERSION

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedResidueEventConcentrationFamily:
        del target
        if self.bin_width < 1:
            raise ValueError("bin_width는 1 이상이어야 합니다.")
        if self.min_patient_bin_support < 1:
            raise ValueError("min_patient_bin_support는 1 이상이어야 합니다.")
        if not self.gene_columns:
            raise ValueError("유전자 열이 하나 이상 필요합니다.")
        missing = [gene for gene in self.gene_columns if gene not in train_frame.columns]
        if missing:
            raise ValueError(f"학습 입력에 유전자 열이 없습니다: {missing[:5]}")

        profiles: list[GeneConcentrationProfile] = []
        for gene in self.gene_columns:
            bin_counts: Counter[int] = Counter()
            patient_support = 0
            for raw_value in train_frame[gene].to_numpy(dtype=object, copy=False):
                bins = _position_bins(raw_value, bin_width=self.bin_width)
                if not bins:
                    continue
                patient_support += 1
                bin_counts.update(bins)
            total = sum(bin_counts.values())
            if total < self.min_patient_bin_support or len(bin_counts) < 2:
                continue

            ordered_counts = tuple(sorted(bin_counts.items()))
            shares = tuple((key, count / total) for key, count in ordered_counts)
            maximum_count = max(bin_counts.values())
            top_bin = min(key for key, count in ordered_counts if count == maximum_count)
            probabilities = np.asarray([share for _, share in shares], dtype=np.float64)
            hhi = float(np.square(probabilities).sum())
            entropy = -float(np.sum(probabilities * np.log(probabilities)))
            normalized_entropy = entropy / math.log(len(probabilities))
            profiles.append(
                GeneConcentrationProfile(
                    gene=gene,
                    patient_bin_support=total,
                    patient_support=patient_support,
                    bin_counts=ordered_counts,
                    bin_shares=shares,
                    top_bin=top_bin,
                    hhi=hhi,
                    normalized_entropy=normalized_entropy,
                )
            )

        profiles.sort(key=lambda item: item.gene)
        return FittedResidueEventConcentrationFamily(
            descriptor=FeatureFamilyDescriptor(
                name="residue_event_concentration",
                version=self.version,
                fit_scope="fold_train",
                feature_names=FEATURE_NAMES,
            ),
            gene_columns=self.gene_columns,
            bin_width=self.bin_width,
            min_patient_bin_support=self.min_patient_bin_support,
            profiles=tuple(profiles),
        )


def metadata_json(fitted: FittedResidueEventConcentrationFamily) -> str:
    return json.dumps(fitted.metadata(), ensure_ascii=False, sort_keys=True, indent=2)
