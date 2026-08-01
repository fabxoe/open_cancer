"""ABC-Stack B families: complex morphology and frequency-tier spectrum."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FeatureFamilyDescriptor
from open_cancer.mutation_features import MUTATION_TYPES, parse_mutation_token

ComplexMorphology = Literal[
    "multi_position_complex",
    "inframe_or_delins",
    "other_complex",
]

COMPLEX_MORPHOLOGIES: tuple[ComplexMorphology, ...] = (
    "multi_position_complex",
    "inframe_or_delins",
    "other_complex",
)
COMPLEX_MORPHOLOGY_FEATURES = (
    *(f"sample__{name}_count" for name in COMPLEX_MORPHOLOGIES),
    *(f"sample__{name}_fraction" for name in COMPLEX_MORPHOLOGIES),
    "sample__truncating_fraction",
    "sample__nonsynonymous_to_synonymous_ratio_smooth1",
)
FREQUENCY_TIER_FEATURES = (
    *(
        f"sample__frequency_tier_{tier}__{mutation_type}_count"
        for tier in range(1, 5)
        for mutation_type in MUTATION_TYPES
    ),
    *(
        f"sample__frequency_tier_{tier}__{mutation_type}_fraction"
        for tier in range(1, 5)
        for mutation_type in MUTATION_TYPES
    ),
)


class ABCSpectrumError(ValueError):
    """Raised when a B-family configuration or source frame is invalid."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ABCSpectrumError(message)


def _tokens(cell: Any) -> tuple[str, ...]:
    if not isinstance(cell, str) or cell == "" or cell == "WT":
        return ()
    return tuple(token for token in cell.split() if token and token != "WT")


def _validate_genes(frame: pd.DataFrame, genes: tuple[str, ...]) -> None:
    missing = [gene for gene in genes if gene not in frame.columns]
    _require(bool(genes), "유전자 열이 하나 이상 필요합니다.")
    _require(not missing, f"입력에 유전자 열이 없습니다: {missing[:5]}")


def classify_complex_morphology(token: str) -> ComplexMorphology | None:
    """Split complex tokens into three disjoint lexical shapes."""
    parsed = parse_mutation_token(token)
    if not parsed.is_complex:
        return None
    if len(parsed.residue_positions) > 1:
        return "multi_position_complex"
    lowered = parsed.raw.lower()
    if any(marker in lowered for marker in ("del", "ins", ">", "_")):
        return "inframe_or_delins"
    return "other_complex"


@dataclass(frozen=True)
class FittedComplexMorphologyFamily:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        _validate_genes(frame, self.gene_columns)
        output = np.zeros((len(frame), len(COMPLEX_MORPHOLOGY_FEATURES)), dtype=np.float32)
        morphology_index = {name: index for index, name in enumerate(COMPLEX_MORPHOLOGIES)}
        for row_index, row in enumerate(frame.loc[:, self.gene_columns].itertuples(index=False, name=None)):
            type_counts: Counter[str] = Counter()
            morphology_counts: Counter[str] = Counter()
            total = 0
            for cell in row:
                for token in _tokens(cell):
                    parsed = parse_mutation_token(token)
                    total += 1
                    type_counts[parsed.mutation_type] += 1
                    morphology = classify_complex_morphology(token)
                    if morphology is not None:
                        morphology_counts[morphology] += 1
            denominator = max(total, 1)
            for morphology, count in morphology_counts.items():
                index = morphology_index[morphology]
                output[row_index, index] = count
                output[row_index, len(COMPLEX_MORPHOLOGIES) + index] = count / denominator
            output[row_index, 6] = (
                type_counts["nonsense"] + type_counts["frameshift"]
            ) / denominator
            nonsynonymous = (
                type_counts["missense"]
                + type_counts["nonsense"]
                + type_counts["frameshift"]
                + type_counts["complex"]
            )
            output[row_index, 7] = nonsynonymous / (type_counts["synonymous"] + 1)
        return sparse.csr_matrix(output)


@dataclass(frozen=True)
class ComplexMorphologyFamily:
    gene_columns: tuple[str, ...]
    version: str = "1.0.0"

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedComplexMorphologyFamily:
        del target
        _validate_genes(train_frame, self.gene_columns)
        return FittedComplexMorphologyFamily(
            descriptor=FeatureFamilyDescriptor(
                name="complex_morphology",
                version=self.version,
                fit_scope="stateless",
                feature_names=COMPLEX_MORPHOLOGY_FEATURES,
            ),
            gene_columns=self.gene_columns,
        )


@dataclass(frozen=True)
class FittedFrequencyTierSpectrumFamily:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    gene_tiers: dict[str, int]
    gene_support: dict[str, int]

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        _validate_genes(frame, self.gene_columns)
        output = np.zeros((len(frame), len(FREQUENCY_TIER_FEATURES)), dtype=np.float32)
        type_index = {mutation_type: index for index, mutation_type in enumerate(MUTATION_TYPES)}
        count_dimension = 4 * len(MUTATION_TYPES)
        for row_index, row in enumerate(frame.loc[:, self.gene_columns].itertuples(index=False, name=None)):
            total = 0
            for gene, cell in zip(self.gene_columns, row, strict=True):
                tier = self.gene_tiers[gene]
                for token in _tokens(cell):
                    mutation_type = parse_mutation_token(token).mutation_type
                    column = tier * len(MUTATION_TYPES) + type_index[mutation_type]
                    output[row_index, column] += 1
                    total += 1
            if total:
                output[row_index, count_dimension:] = output[row_index, :count_dimension] / total
        return sparse.csr_matrix(output)


@dataclass(frozen=True)
class FrequencyTierSpectrumFamily:
    """Fit four deterministic gene-frequency tiers on outer fold-train only."""

    gene_columns: tuple[str, ...]
    tier_count: int = 4
    version: str = "1.0.0"

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedFrequencyTierSpectrumFamily:
        del target
        _validate_genes(train_frame, self.gene_columns)
        _require(self.tier_count == 4, "v1 frequency spectrum은 고정 4개 tier만 지원합니다.")
        support: dict[str, int] = {}
        for gene in self.gene_columns:
            support[gene] = sum(bool(_tokens(cell)) for cell in train_frame[gene])
        ranked = sorted(self.gene_columns, key=lambda gene: (support[gene], gene))
        gene_tiers = {
            gene: min(self.tier_count - 1, index * self.tier_count // len(ranked))
            for index, gene in enumerate(ranked)
        }
        return FittedFrequencyTierSpectrumFamily(
            descriptor=FeatureFamilyDescriptor(
                name="frequency_tier_spectrum",
                version=self.version,
                fit_scope="fold_train",
                feature_names=FREQUENCY_TIER_FEATURES,
            ),
            gene_columns=self.gene_columns,
            gene_tiers=gene_tiers,
            gene_support=support,
        )
