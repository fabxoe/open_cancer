"""HGVS-informed parser-v4 native semantic representation v3.

V3 keeps the token-count aggregation selected after the EXP-456/469 audit and
exposes the three distinct meanings carried by the competition's compact range
notation.  Parser correctness and raw provenance are preserved independently
from whether a model later benefits from these columns.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.canonical_mutation_events import parse_canonical_gene_cell
from open_cancer.feature_family import FeatureFamilyDescriptor
from open_cancer.hashing import sha256_file
from open_cancer.mutation_parser_contract import RoutedProteinMutation
from open_cancer.parser_native_v2_features import native_v2_primary_family
from open_cancer.sparse_gene_cells import extract_non_wt_gene_cells


PARSER_NATIVE_V3_FEATURE_VERSION = "3.0.0"
DEFAULT_V3_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "configs"
    / "parser_v4_native_feature_schema_v3_semantic_range.yaml"
)

ModelConsequenceV3 = Literal[
    "missense",
    "no_change",
    "nonsense",
    "frameshift",
    "range_replacement",
    "range_stop",
    "range_no_change",
]

MODEL_ACTIVE_V3_CONSEQUENCES: tuple[ModelConsequenceV3, ...] = (
    "missense",
    "no_change",
    "nonsense",
    "frameshift",
    "range_replacement",
    "range_stop",
    "range_no_change",
)


def native_v3_model_consequence(
    routed: RoutedProteinMutation,
) -> ModelConsequenceV3 | None:
    """Return the model consequence without collapsing range semantics."""

    if routed.route == "substitution" and routed.event_type in {
        "missense",
        "no_change",
        "nonsense",
    }:
        return routed.event_type  # type: ignore[return-value]
    if routed.route == "frameshift" and routed.parse_status != "unresolved":
        return "frameshift"
    if routed.route == "range_replacement":
        if routed.payload.get("protein_no_change") is True:
            return "range_no_change"
        if routed.payload.get("contains_stop") is True:
            return "range_stop"
        if routed.event_type == "range_replacement":
            return "range_replacement"
    return None


@dataclass(frozen=True)
class NativeV3GeneCellSemantics:
    model_consequences: frozenset[ModelConsequenceV3]
    model_consequence_counts: tuple[tuple[ModelConsequenceV3, int], ...]
    primary_family_counts: tuple[tuple[str, int], ...]
    token_count: int

    @property
    def mutated(self) -> bool:
        return self.token_count > 0


def parse_native_v3_gene_cell(
    gene_symbol: str, cell: object
) -> NativeV3GeneCellSemantics:
    """Parse every token once and retain both model and QC semantic views."""

    if not isinstance(cell, str) or not cell.strip() or cell.strip().upper() == "WT":
        return NativeV3GeneCellSemantics(frozenset(), (), (), 0)
    consequences: set[ModelConsequenceV3] = set()
    consequence_counts: dict[ModelConsequenceV3, int] = {}
    primary_counts: dict[str, int] = {}
    canonical = parse_canonical_gene_cell(cell)
    for routed in canonical.events:
        primary = native_v2_primary_family(routed, gene_symbol=gene_symbol)
        primary_counts[primary] = primary_counts.get(primary, 0) + 1
        consequence = native_v3_model_consequence(routed)
        if consequence is not None:
            consequences.add(consequence)
            consequence_counts[consequence] = consequence_counts.get(consequence, 0) + 1
    source_token_count = sum(
        1 for token in cell.split() if token.strip() and token.upper() != "WT"
    )
    if len(canonical.events) != source_token_count:
        raise AssertionError("parser v4 token preservation contract failed")
    return NativeV3GeneCellSemantics(
        model_consequences=frozenset(consequences),
        model_consequence_counts=tuple(sorted(consequence_counts.items())),
        primary_family_counts=tuple(sorted(primary_counts.items())),
        token_count=len(canonical.events),
    )


def parser_native_v3_feature_names(
    gene_columns: tuple[str, ...],
) -> tuple[str, ...]:
    sample_names = tuple(
        f"sample__native_v3_{name}_token_count"
        for name in MODEL_ACTIVE_V3_CONSEQUENCES
    )
    gene_names = tuple(
        f"gene__{gene}__native_v3_{consequence}_any"
        for gene in gene_columns
        for consequence in MODEL_ACTIVE_V3_CONSEQUENCES
    )
    return (*sample_names, *gene_names)


@dataclass(frozen=True)
class FittedParserNativeV3SemanticRangeFamily:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    schema_sha256: str

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")
        consequence_index = {
            value: index for index, value in enumerate(MODEL_ACTIVE_V3_CONSEQUENCES)
        }
        width = len(MODEL_ACTIVE_V3_CONSEQUENCES)
        rows: list[int] = []
        columns: list[int] = []
        values: list[float] = []
        sample_counts = np.zeros((len(frame), width), dtype=np.float32)

        cells = extract_non_wt_gene_cells(frame, self.gene_columns)
        for row_index_raw, gene_index_raw, cell in zip(
            cells.row_indices, cells.gene_indices, cells.values
        ):
            row_index = int(row_index_raw)
            gene_index = int(gene_index_raw)
            gene = self.gene_columns[gene_index]
            parsed = parse_native_v3_gene_cell(gene, cell)
            consequence_counts = dict(parsed.model_consequence_counts)
            for consequence in parsed.model_consequences:
                index = consequence_index[consequence]
                sample_counts[row_index, index] += float(
                    consequence_counts[consequence]
                )
                rows.append(row_index)
                columns.append(width + gene_index * width + index)
                values.append(1.0)

        sample_rows, sample_columns = np.nonzero(sample_counts)
        rows.extend(sample_rows.tolist())
        columns.extend(sample_columns.tolist())
        values.extend(sample_counts[sample_rows, sample_columns].tolist())
        return sparse.csr_matrix(
            (np.asarray(values, dtype=np.float32), (rows, columns)),
            shape=(len(frame), self.descriptor.output_dimension),
            dtype=np.float32,
        )


@dataclass(frozen=True)
class ParserNativeV3SemanticRangeFamily:
    gene_columns: tuple[str, ...]
    schema_path: Path = DEFAULT_V3_SCHEMA_PATH
    version: str = PARSER_NATIVE_V3_FEATURE_VERSION

    def fit(
        self, train_frame: pd.DataFrame, target: pd.Series | None = None
    ) -> FittedParserNativeV3SemanticRangeFamily:
        del target
        if not self.gene_columns:
            raise ValueError("유전자 열이 하나 이상 필요합니다.")
        missing = [gene for gene in self.gene_columns if gene not in train_frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")
        if not self.schema_path.is_file():
            raise FileNotFoundError(self.schema_path)
        return FittedParserNativeV3SemanticRangeFamily(
            descriptor=FeatureFamilyDescriptor(
                name="parser_v4_native_semantic_v3_range",
                version=self.version,
                fit_scope="stateless",
                feature_names=parser_native_v3_feature_names(self.gene_columns),
            ),
            gene_columns=self.gene_columns,
            schema_sha256=sha256_file(self.schema_path),
        )


def native_v3_semantic_contract_record(
    fitted: FittedParserNativeV3SemanticRangeFamily,
) -> dict[str, Any]:
    return {
        "family": fitted.descriptor.name,
        "version": fitted.descriptor.version,
        "fit_scope": fitted.descriptor.fit_scope,
        "schema_sha256": fitted.schema_sha256,
        "output_dimension": fitted.descriptor.output_dimension,
        "feature_names_sha256": fitted.descriptor.feature_names_sha256,
        "model_active_consequences": list(MODEL_ACTIVE_V3_CONSEQUENCES),
        "range_semantics": {
            "ordinary": "range_replacement",
            "contains_stop": "range_stop",
            "protein_no_change": "range_no_change",
            "mutually_exclusive": True,
        },
        "gene_aggregation": "consequence_presence",
        "sample_aggregation": "token_count",
        "mutation_presence_policy": "preserve_existing_base_feature",
        "raw_provenance_policy": "preserve_outside_model_matrix",
    }
