"""Fold-safe gene indicators for ordinary protein range replacements."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FeatureFamilyDescriptor
from open_cancer.mutation_parser_contract import route_protein_mutation
from open_cancer.parser_support_gate import support_family_key


def is_ordinary_range_replacement(raw_token: str) -> bool:
    """Match the exact subtype admitted by the #407/#410 support gate."""

    routed = route_protein_mutation(raw_token)
    return support_family_key(
        route=routed.route,
        event_type=routed.event_type,
        payload=routed.payload,
    ) == ("range_replacement", "range_replacement")


def _cell_has_ordinary_range_replacement(cell: object) -> bool:
    if not isinstance(cell, str) or not cell.strip() or cell.upper() == "WT":
        return False
    return any(
        is_ordinary_range_replacement(token)
        for token in cell.split()
        if token and token.upper() != "WT"
    )


@dataclass(frozen=True)
class FittedOrdinaryRangeReplacementGeneFamily:
    descriptor: FeatureFamilyDescriptor
    selected_genes: tuple[str, ...]

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.selected_genes if gene not in frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")
        rows: list[int] = []
        columns: list[int] = []
        for column_index, gene in enumerate(self.selected_genes):
            for row_index, cell in enumerate(frame[gene].array):
                if _cell_has_ordinary_range_replacement(cell):
                    rows.append(row_index)
                    columns.append(column_index)
        values = np.ones(len(rows), dtype=np.float32)
        return sparse.csr_matrix(
            (values, (rows, columns)),
            shape=(len(frame), len(self.selected_genes)),
            dtype=np.float32,
        )


@dataclass(frozen=True)
class OrdinaryRangeReplacementGeneFamily:
    """Select genes observed in outer-train and emit one presence bit each."""

    gene_columns: tuple[str, ...]
    version: str = "1.0.0"

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedOrdinaryRangeReplacementGeneFamily:
        del target
        missing = [gene for gene in self.gene_columns if gene not in train_frame.columns]
        if missing or not self.gene_columns:
            raise ValueError("유전자 열 계약이 올바르지 않습니다.")
        selected_genes = tuple(
            gene
            for gene in self.gene_columns
            if any(
                _cell_has_ordinary_range_replacement(cell)
                for cell in train_frame[gene].array
            )
        )
        if not selected_genes:
            raise ValueError("outer-train에 ordinary range replacement가 없습니다.")
        feature_names = tuple(
            f"gene__{gene}__range_replacement_any" for gene in selected_genes
        )
        return FittedOrdinaryRangeReplacementGeneFamily(
            descriptor=FeatureFamilyDescriptor(
                name="ordinary_range_replacement_gene_indicator",
                version=self.version,
                fit_scope="fold_train",
                feature_names=feature_names,
            ),
            selected_genes=selected_genes,
        )
