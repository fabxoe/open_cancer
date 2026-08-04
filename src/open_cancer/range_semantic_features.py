"""Compact sample summaries for semantically parsed range events."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FeatureFamilyDescriptor
from open_cancer.robust_mutation_parser import parse_robust_mutation_token


RANGE_SEMANTIC_FEATURE_VERSION = "1.0.0"
RANGE_SEMANTIC_FEATURE_NAMES: tuple[str, ...] = (
    "sample__range_stop_gene_count",
    "sample__range_stop_any",
    "sample__range_no_change_gene_count",
    "sample__range_no_change_any",
)


@dataclass(frozen=True)
class FittedRangeSemanticSummaryFamily:
    """Stateless four-column summary fitted only to satisfy family contracts."""

    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")

        output = np.zeros((len(frame), len(RANGE_SEMANTIC_FEATURE_NAMES)), dtype=np.float32)
        for row_index, row in enumerate(
            frame.loc[:, self.gene_columns].itertuples(index=False, name=None)
        ):
            range_stop_genes = 0
            range_no_change_genes = 0
            for cell in row:
                if not isinstance(cell, str) or ">" not in cell:
                    continue
                tokens = tuple(
                    parse_robust_mutation_token(raw)
                    for raw in cell.split()
                    if ">" in raw
                )
                has_range_stop = any(
                    token.source_structure == "range_replacement"
                    and token.contains_stop
                    for token in tokens
                )
                has_range_no_change = any(
                    token.source_structure == "range_replacement"
                    and token.protein_no_change
                    for token in tokens
                )
                range_stop_genes += int(has_range_stop)
                range_no_change_genes += int(has_range_no_change)

            output[row_index] = (
                range_stop_genes,
                int(range_stop_genes > 0),
                range_no_change_genes,
                int(range_no_change_genes > 0),
            )
        return sparse.csr_matrix(output)


@dataclass(frozen=True)
class RangeSemanticSummaryFamily:
    """Four predeclared unique-gene count/any features from Issue #380."""

    gene_columns: tuple[str, ...]
    version: str = RANGE_SEMANTIC_FEATURE_VERSION

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedRangeSemanticSummaryFamily:
        del target
        if not self.gene_columns:
            raise ValueError("유전자 열이 하나 이상 필요합니다.")
        missing = [gene for gene in self.gene_columns if gene not in train_frame.columns]
        if missing:
            raise ValueError(f"학습 입력에 유전자 열이 없습니다: {missing[:5]}")
        return FittedRangeSemanticSummaryFamily(
            descriptor=FeatureFamilyDescriptor(
                name="range_semantic_summary",
                version=self.version,
                fit_scope="stateless",
                feature_names=RANGE_SEMANTIC_FEATURE_NAMES,
            ),
            gene_columns=self.gene_columns,
        )
