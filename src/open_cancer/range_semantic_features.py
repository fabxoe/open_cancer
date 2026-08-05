"""Fold-safe gene indicators for stop/no-change protein range semantics."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FeatureFamilyDescriptor
from open_cancer.mutation_parser_contract import route_protein_mutation


RANGE_SEMANTIC_TYPES = ("range_stop", "range_no_change")


def range_semantic_type(raw_token: str) -> str | None:
    """Return only the two pre-registered #392 range consequences."""

    routed = route_protein_mutation(raw_token)
    if routed.route != "range_replacement":
        return None
    if routed.payload.get("protein_truncating") is True:
        return "range_stop"
    if routed.payload.get("protein_no_change") is True:
        return "range_no_change"
    return None


def _cell_semantics(cell: object) -> frozenset[str]:
    if not isinstance(cell, str) or not cell.strip() or cell.upper() == "WT":
        return frozenset()
    return frozenset(
        semantic
        for token in cell.split()
        if token and token.upper() != "WT"
        if (semantic := range_semantic_type(token)) is not None
    )


@dataclass(frozen=True)
class FittedRangeSemanticGeneFamily:
    descriptor: FeatureFamilyDescriptor
    selected_gene_semantics: tuple[tuple[str, str], ...]

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = sorted(
            {gene for gene, _ in self.selected_gene_semantics if gene not in frame.columns}
        )
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")
        rows: list[int] = []
        columns: list[int] = []
        cached: dict[str, list[frozenset[str]]] = {}
        for column_index, (gene, semantic) in enumerate(self.selected_gene_semantics):
            values = cached.setdefault(
                gene, [_cell_semantics(cell) for cell in frame[gene].array]
            )
            for row_index, observed in enumerate(values):
                if semantic in observed:
                    rows.append(row_index)
                    columns.append(column_index)
        return sparse.csr_matrix(
            (np.ones(len(rows), dtype=np.float32), (rows, columns)),
            shape=(len(frame), len(self.selected_gene_semantics)),
            dtype=np.float32,
        )


@dataclass(frozen=True)
class RangeSemanticGeneFamily:
    gene_columns: tuple[str, ...]
    version: str = "1.0.0"

    def fit(
        self, train_frame: pd.DataFrame, target: pd.Series | None = None
    ) -> FittedRangeSemanticGeneFamily:
        del target
        missing = [gene for gene in self.gene_columns if gene not in train_frame.columns]
        if missing or not self.gene_columns:
            raise ValueError("유전자 열 계약이 올바르지 않습니다.")
        selected: list[tuple[str, str]] = []
        for gene in self.gene_columns:
            observed = set().union(
                *(_cell_semantics(cell) for cell in train_frame[gene].array)
            )
            selected.extend(
                (gene, semantic)
                for semantic in RANGE_SEMANTIC_TYPES
                if semantic in observed
            )
        if not selected:
            raise ValueError("outer-train에 range stop/no-change 사건이 없습니다.")
        pairs = tuple(selected)
        names = tuple(f"gene__{gene}__{semantic}_any" for gene, semantic in pairs)
        return FittedRangeSemanticGeneFamily(
            descriptor=FeatureFamilyDescriptor(
                name="range_stop_no_change_gene_indicator",
                version=self.version,
                fit_scope="fold_train",
                feature_names=names,
            ),
            selected_gene_semantics=pairs,
        )
