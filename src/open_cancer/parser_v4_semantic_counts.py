"""Patient-level token counts from the lossless parser-v4 semantic contract."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.canonical_mutation_events import parse_canonical_gene_cell
from open_cancer.feature_family import FeatureFamilyDescriptor
from open_cancer.parser_native_v2_features import native_v2_primary_family
from open_cancer.sparse_gene_cells import extract_non_wt_gene_cells


PARSER_V4_SEMANTIC_COUNT_VERSION = "1.0.0"

SEMANTIC_COUNT_NAMES = (
    "total_token_count",
    "missense_count",
    "no_change_count",
    "nonsense_count",
    "start_codon_affected_count",
    "unknown_reference_substitution_count",
    "nonstandard_stop_reference_count",
    "frameshift_count",
    "deletion_count",
    "delins_count",
    "insertion_count",
    "duplication_candidate_count",
    "range_replacement_count",
    "range_stop_count",
    "range_no_change_count",
    "unresolved_count",
    "complete_parse_count",
    "partial_parse_count",
)

FEATURE_NAMES = tuple(f"sample__parser_v4_{name}" for name in SEMANTIC_COUNT_NAMES)
_INDEX = {name: index for index, name in enumerate(SEMANTIC_COUNT_NAMES)}


def _increment_event(row: np.ndarray, event, *, gene_symbol: str) -> None:
    row[_INDEX["total_token_count"]] += 1.0
    if event.parse_status == "complete":
        row[_INDEX["complete_parse_count"]] += 1.0
    elif event.parse_status == "partial":
        row[_INDEX["partial_parse_count"]] += 1.0
    elif event.parse_status == "unresolved":
        row[_INDEX["unresolved_count"]] += 1.0

    if event.route == "substitution":
        mapping = {
            "missense": "missense_count",
            "no_change": "no_change_count",
            "nonsense": "nonsense_count",
            "start_codon_affected": "start_codon_affected_count",
            "unknown_reference_substitution": "unknown_reference_substitution_count",
            "nonstandard_stop_reference": "nonstandard_stop_reference_count",
        }
        name = mapping.get(event.event_type)
        if name is None:
            row[_INDEX["unresolved_count"]] += 1.0
        else:
            row[_INDEX[name]] += 1.0
        return
    if event.route == "frameshift":
        row[_INDEX["frameshift_count"]] += 1.0
        return
    if event.route == "deletion":
        row[_INDEX["deletion_count"]] += 1.0
        return
    if event.route == "delins":
        row[_INDEX["delins_count"]] += 1.0
        if event.event_type == "nonsense":
            row[_INDEX["nonsense_count"]] += 1.0
        return
    if event.route == "insertion":
        primary = native_v2_primary_family(event, gene_symbol=gene_symbol)
        if primary == "duplication_candidate":
            row[_INDEX["duplication_candidate_count"]] += 1.0
        else:
            row[_INDEX["insertion_count"]] += 1.0
        return
    if event.route == "range_replacement":
        if event.payload.get("protein_no_change") is True:
            row[_INDEX["range_no_change_count"]] += 1.0
        elif event.payload.get("contains_stop") is True:
            row[_INDEX["range_stop_count"]] += 1.0
        else:
            row[_INDEX["range_replacement_count"]] += 1.0
        return
    if event.parse_status != "unresolved":
        row[_INDEX["unresolved_count"]] += 1.0


@dataclass(frozen=True)
class FittedParserV4SemanticCountFamily:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")
        matrix = np.zeros((len(frame), len(FEATURE_NAMES)), dtype=np.float32)
        cells = extract_non_wt_gene_cells(frame, self.gene_columns)
        for row_index, gene_index, cell in zip(
            cells.row_indices, cells.gene_indices, cells.values
        ):
            parsed = parse_canonical_gene_cell(cell)
            gene = self.gene_columns[int(gene_index)]
            for event in parsed.events:
                _increment_event(matrix[int(row_index)], event, gene_symbol=gene)
        return sparse.csr_matrix(matrix)


@dataclass(frozen=True)
class ParserV4SemanticCountFamily:
    gene_columns: tuple[str, ...]
    version: str = PARSER_V4_SEMANTIC_COUNT_VERSION

    def fit(self, train_frame: pd.DataFrame, target: pd.Series | None = None):
        del target
        if not self.gene_columns:
            raise ValueError("유전자 열이 하나 이상 필요합니다.")
        return FittedParserV4SemanticCountFamily(
            descriptor=FeatureFamilyDescriptor(
                name="parser_v4_patient_semantic_counts",
                version=self.version,
                fit_scope="stateless",
                feature_names=FEATURE_NAMES,
            ),
            gene_columns=self.gene_columns,
        )
