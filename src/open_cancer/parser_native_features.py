"""Unified compact features derived from the parser-v4 canonical event.

This module is deliberately independent of isoform, driver, pathway, target,
and Public-LB information.  It does not replace or mutate the base
``gene__mutated`` features; every non-WT gene cell is represented by at least
one native consequence so mutation presence can be audited by an OR reduction.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FeatureFamilyDescriptor
from open_cancer.hashing import sha256_file
from open_cancer.mutation_parser_contract import RoutedProteinMutation, route_protein_mutation


PARSER_NATIVE_FEATURE_VERSION = "1.0.0"
DEFAULT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "configs"
    / "parser_v4_native_feature_schema_v1.yaml"
)

NativeConsequence = Literal[
    "missense",
    "no_change",
    "nonsense",
    "frameshift",
    "range_replacement",
    "non_simple_or_unresolved",
]

NATIVE_CONSEQUENCES: tuple[NativeConsequence, ...] = (
    "missense",
    "no_change",
    "nonsense",
    "frameshift",
    "range_replacement",
    "non_simple_or_unresolved",
)
PARSE_STATUSES = ("complete", "partial", "unresolved")
FRAMESHIFT_GRAMMARS = (
    "short_ref_position",
    "ref_alt_before_position",
    "ref_position_alt",
)


@lru_cache(maxsize=8_192)
def _route_cached(token: str) -> RoutedProteinMutation:
    return route_protein_mutation(token)


def native_consequence(routed: RoutedProteinMutation) -> NativeConsequence:
    """Project one canonical event into the fixed compact model ontology."""

    if routed.route == "substitution":
        if routed.event_type in {"missense", "no_change", "nonsense"}:
            return routed.event_type  # type: ignore[return-value]
        return "non_simple_or_unresolved"
    if routed.route == "frameshift":
        return "frameshift"
    if routed.route == "range_replacement":
        if routed.payload.get("protein_no_change") is True:
            return "no_change"
        if routed.payload.get("first_stop_offset") == 0:
            return "nonsense"
        return "range_replacement"
    return "non_simple_or_unresolved"


@dataclass(frozen=True)
class NativeGeneCellSemantics:
    """Lossless-enough compact summary of all tokens in one gene cell."""

    consequences: frozenset[NativeConsequence]
    parse_statuses: frozenset[str]
    frameshift_grammars: frozenset[str]
    token_count: int
    qc_route_counts: tuple[tuple[str, int], ...]

    @property
    def mutated(self) -> bool:
        return self.token_count > 0


def parse_native_gene_cell(cell: object) -> NativeGeneCellSemantics:
    """Parse a whitespace-delimited cell once, preserving every non-WT token."""

    if not isinstance(cell, str) or not cell.strip() or cell.strip().upper() == "WT":
        return NativeGeneCellSemantics(frozenset(), frozenset(), frozenset(), 0, ())
    consequences: set[NativeConsequence] = set()
    statuses: set[str] = set()
    grammars: set[str] = set()
    route_counts: dict[str, int] = {}
    token_count = 0
    for raw in cell.split():
        token = raw.strip()
        if not token or token.upper() == "WT":
            continue
        token_count += 1
        routed = _route_cached(token)
        consequences.add(native_consequence(routed))
        status = routed.parse_status
        statuses.add(status if status in PARSE_STATUSES else "unresolved")
        route_counts[routed.route] = route_counts.get(routed.route, 0) + 1
        if routed.route == "frameshift":
            grammar = str(routed.payload.get("grammar", ""))
            if grammar in FRAMESHIFT_GRAMMARS:
                grammars.add(grammar)
    if token_count and not consequences:
        raise AssertionError("non-WT token lost from native semantic projection")
    return NativeGeneCellSemantics(
        consequences=frozenset(consequences),
        parse_statuses=frozenset(statuses),
        frameshift_grammars=frozenset(grammars),
        token_count=token_count,
        qc_route_counts=tuple(sorted(route_counts.items())),
    )


def parser_native_feature_names(gene_columns: tuple[str, ...]) -> tuple[str, ...]:
    sample_names = tuple(
        f"sample__native_{name}_gene_count" for name in NATIVE_CONSEQUENCES
    ) + tuple(
        f"sample__native_parse_{status}_gene_count" for status in PARSE_STATUSES
    ) + tuple(
        f"sample__native_frameshift_{grammar}_gene_count"
        for grammar in FRAMESHIFT_GRAMMARS
    )
    gene_names = tuple(
        f"gene__{gene}__native_{consequence}_any"
        for gene in gene_columns
        for consequence in NATIVE_CONSEQUENCES
    )
    return (*sample_names, *gene_names)


@dataclass(frozen=True)
class FittedParserNativeSemanticFamily:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    schema_sha256: str

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")
        consequence_index = {
            value: index for index, value in enumerate(NATIVE_CONSEQUENCES)
        }
        status_offset = len(NATIVE_CONSEQUENCES)
        status_index = {value: index for index, value in enumerate(PARSE_STATUSES)}
        grammar_offset = status_offset + len(PARSE_STATUSES)
        grammar_index = {
            value: index for index, value in enumerate(FRAMESHIFT_GRAMMARS)
        }
        sample_width = grammar_offset + len(FRAMESHIFT_GRAMMARS)
        gene_width = len(NATIVE_CONSEQUENCES)
        rows: list[int] = []
        columns: list[int] = []
        values: list[float] = []
        sample_counts = np.zeros((len(frame), sample_width), dtype=np.float32)

        # Column-major traversal avoids constructing 4,384 Python objects for
        # every sample.  Vectorized WT filtering means only mutated cells enter
        # the semantic parser, which is essential for this sparse dataset.
        for gene_index, gene in enumerate(self.gene_columns):
            gene_values = frame[gene].to_numpy(dtype=object, copy=False)
            non_wt = np.fromiter(
                (
                    isinstance(cell, str)
                    and bool(cell.strip())
                    and cell.strip().upper() != "WT"
                    for cell in gene_values
                ),
                dtype=bool,
                count=len(frame),
            )
            for row_index in np.flatnonzero(non_wt):
                parsed = parse_native_gene_cell(gene_values[row_index])
                for consequence in parsed.consequences:
                    index = consequence_index[consequence]
                    sample_counts[row_index, index] += 1.0
                    rows.append(int(row_index))
                    columns.append(sample_width + gene_index * gene_width + index)
                    values.append(1.0)
                for status in parsed.parse_statuses:
                    sample_counts[row_index, status_offset + status_index[status]] += 1.0
                for grammar in parsed.frameshift_grammars:
                    sample_counts[
                        row_index, grammar_offset + grammar_index[grammar]
                    ] += 1.0

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
class ParserNativeSemanticFamily:
    """Stateless parser-v4 native adapter for the post-audit baseline."""

    gene_columns: tuple[str, ...]
    schema_path: Path = DEFAULT_SCHEMA_PATH
    version: str = PARSER_NATIVE_FEATURE_VERSION

    def fit(
        self, train_frame: pd.DataFrame, target: pd.Series | None = None
    ) -> FittedParserNativeSemanticFamily:
        del target
        if not self.gene_columns:
            raise ValueError("유전자 열이 하나 이상 필요합니다.")
        missing = [gene for gene in self.gene_columns if gene not in train_frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")
        if not self.schema_path.is_file():
            raise FileNotFoundError(self.schema_path)
        return FittedParserNativeSemanticFamily(
            descriptor=FeatureFamilyDescriptor(
                name="parser_v4_native_semantic",
                version=self.version,
                fit_scope="stateless",
                feature_names=parser_native_feature_names(self.gene_columns),
            ),
            gene_columns=self.gene_columns,
            schema_sha256=sha256_file(self.schema_path),
        )


def native_semantic_contract_record(
    fitted: FittedParserNativeSemanticFamily,
) -> dict[str, Any]:
    """Return the resolved, serializable identity required by model runners."""

    return {
        "family": fitted.descriptor.name,
        "version": fitted.descriptor.version,
        "fit_scope": fitted.descriptor.fit_scope,
        "schema_sha256": fitted.schema_sha256,
        "output_dimension": fitted.descriptor.output_dimension,
        "feature_names_sha256": fitted.descriptor.feature_names_sha256,
        "mutation_presence_policy": "preserve_existing_base_feature",
        "aggregation": "affected_gene_presence",
    }
