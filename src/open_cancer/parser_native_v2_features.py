"""Support-gated parser-v4 native semantic representation.

The parser contract understands more event families than the model may safely
learn from this small competition train set.  This adapter therefore keeps two
separate views:

* one exclusive primary semantic family for every non-WT token, retained for
  QC and provenance; and
* a frozen set of model-active consequences that passed the train/canonical
  fold support audit.

Raw mutation-presence features remain outside this family and are never
removed.  Test prevalence, labels and leaderboard results are not consulted.
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
from open_cancer.protein_duplication_semantics import classify_protein_duplication


PARSER_NATIVE_V2_FEATURE_VERSION = "2.0.0"
PARSER_NATIVE_V2_TOKEN_COUNT_FEATURE_VERSION = "2.1.0"
DEFAULT_V2_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "configs"
    / "parser_v4_native_feature_schema_v2.yaml"
)
DEFAULT_V2_TOKEN_COUNT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "configs"
    / "parser_v4_native_feature_schema_v2_token_count.yaml"
)

SampleAggregation = Literal["affected_gene_count", "token_count"]

ModelConsequence = Literal[
    "missense",
    "no_change",
    "nonsense",
    "frameshift",
    "range_replacement",
]

MODEL_ACTIVE_V2_CONSEQUENCES: tuple[ModelConsequence, ...] = (
    "missense",
    "no_change",
    "nonsense",
    "frameshift",
    "range_replacement",
)


def native_v2_primary_family(
    routed: RoutedProteinMutation, *, gene_symbol: str
) -> str:
    """Return one exclusive semantic family for audit and provenance."""

    if routed.route == "substitution":
        return f"substitution:{routed.event_type}"
    if routed.route == "frameshift":
        return "frameshift"
    if routed.route == "deletion":
        return "deletion"
    if routed.route == "delins":
        return "delins"
    if routed.route == "insertion":
        duplication = classify_protein_duplication(
            gene_symbol, routed.raw_token, annotations=()
        )
        if duplication.semantic_event_type == "tandem_duplication":
            return "duplication_candidate"
        return "insertion"
    if routed.route == "range_replacement":
        if routed.payload.get("protein_no_change") is True:
            return "range_no_change"
        if routed.payload.get("contains_stop") is True:
            return "range_stop"
        return "range_replacement"
    return "unresolved"


def native_v2_model_consequence(
    routed: RoutedProteinMutation,
) -> ModelConsequence | None:
    """Project only families that passed the frozen train/fold support gate."""

    if routed.route == "substitution" and routed.event_type in {
        "missense",
        "no_change",
        "nonsense",
    }:
        return routed.event_type  # type: ignore[return-value]
    if routed.route == "frameshift" and routed.parse_status != "unresolved":
        return "frameshift"
    if (
        routed.route == "range_replacement"
        and routed.event_type == "range_replacement"
        and routed.payload.get("contains_stop") is not True
        and routed.payload.get("protein_no_change") is not True
    ):
        return "range_replacement"
    return None


@dataclass(frozen=True)
class NativeV2GeneCellSemantics:
    model_consequences: frozenset[ModelConsequence]
    model_consequence_counts: tuple[tuple[ModelConsequence, int], ...]
    primary_family_counts: tuple[tuple[str, int], ...]
    token_count: int

    @property
    def mutated(self) -> bool:
        return self.token_count > 0


def parse_native_v2_gene_cell(
    gene_symbol: str, cell: object
) -> NativeV2GeneCellSemantics:
    """Parse a gene cell once without dropping QC-only semantic events."""

    if not isinstance(cell, str) or not cell.strip() or cell.strip().upper() == "WT":
        return NativeV2GeneCellSemantics(frozenset(), (), (), 0)
    consequences: set[ModelConsequence] = set()
    consequence_counts: dict[ModelConsequence, int] = {}
    primary_counts: dict[str, int] = {}
    canonical = parse_canonical_gene_cell(cell)
    for routed in canonical.events:
        primary = native_v2_primary_family(routed, gene_symbol=gene_symbol)
        primary_counts[primary] = primary_counts.get(primary, 0) + 1
        consequence = native_v2_model_consequence(routed)
        if consequence is not None:
            consequences.add(consequence)
            consequence_counts[consequence] = consequence_counts.get(consequence, 0) + 1
    source_token_count = sum(
        1 for token in cell.split() if token.strip() and token.upper() != "WT"
    )
    if len(canonical.events) != source_token_count:
        raise AssertionError("parser v4 token preservation contract failed")
    return NativeV2GeneCellSemantics(
        model_consequences=frozenset(consequences),
        model_consequence_counts=tuple(sorted(consequence_counts.items())),
        primary_family_counts=tuple(sorted(primary_counts.items())),
        token_count=len(canonical.events),
    )


def parser_native_v2_feature_names(
    gene_columns: tuple[str, ...],
    *,
    sample_aggregation: SampleAggregation = "affected_gene_count",
) -> tuple[str, ...]:
    sample_suffix = (
        "gene_count" if sample_aggregation == "affected_gene_count" else "token_count"
    )
    sample_names = tuple(
        f"sample__native_v2_{name}_{sample_suffix}"
        for name in MODEL_ACTIVE_V2_CONSEQUENCES
    )
    gene_names = tuple(
        f"gene__{gene}__native_v2_{consequence}_any"
        for gene in gene_columns
        for consequence in MODEL_ACTIVE_V2_CONSEQUENCES
    )
    return (*sample_names, *gene_names)


@dataclass(frozen=True)
class FittedParserNativeV2SemanticFamily:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    schema_sha256: str
    sample_aggregation: SampleAggregation = "affected_gene_count"

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")
        consequence_index = {
            value: index for index, value in enumerate(MODEL_ACTIVE_V2_CONSEQUENCES)
        }
        width = len(MODEL_ACTIVE_V2_CONSEQUENCES)
        rows: list[int] = []
        columns: list[int] = []
        values: list[float] = []
        sample_counts = np.zeros((len(frame), width), dtype=np.float32)

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
                parsed = parse_native_v2_gene_cell(
                    gene, gene_values[row_index]
                )
                consequence_counts = dict(parsed.model_consequence_counts)
                for consequence in parsed.model_consequences:
                    index = consequence_index[consequence]
                    if self.sample_aggregation == "affected_gene_count":
                        sample_counts[row_index, index] += 1.0
                    else:
                        sample_counts[row_index, index] += float(
                            consequence_counts[consequence]
                        )
                    rows.append(int(row_index))
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
class ParserNativeV2SemanticFamily:
    gene_columns: tuple[str, ...]
    schema_path: Path = DEFAULT_V2_SCHEMA_PATH
    version: str = PARSER_NATIVE_V2_FEATURE_VERSION

    def fit(
        self, train_frame: pd.DataFrame, target: pd.Series | None = None
    ) -> FittedParserNativeV2SemanticFamily:
        del target
        if not self.gene_columns:
            raise ValueError("유전자 열이 하나 이상 필요합니다.")
        missing = [gene for gene in self.gene_columns if gene not in train_frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")
        if not self.schema_path.is_file():
            raise FileNotFoundError(self.schema_path)
        return FittedParserNativeV2SemanticFamily(
            descriptor=FeatureFamilyDescriptor(
                name="parser_v4_native_semantic_v2",
                version=self.version,
                fit_scope="stateless",
                feature_names=parser_native_v2_feature_names(self.gene_columns),
            ),
            gene_columns=self.gene_columns,
            schema_sha256=sha256_file(self.schema_path),
            sample_aggregation="affected_gene_count",
        )


@dataclass(frozen=True)
class ParserNativeV2TokenCountFamily:
    """Native-v2 semantics with token-count sample summaries.

    Gene-level presence and semantic routing are identical to native_v2.  Only
    the five sample summary columns count active mutation tokens instead of
    affected genes, isolating the aggregation choice discovered in Issue #462.
    """

    gene_columns: tuple[str, ...]
    schema_path: Path = DEFAULT_V2_TOKEN_COUNT_SCHEMA_PATH
    version: str = PARSER_NATIVE_V2_TOKEN_COUNT_FEATURE_VERSION

    def fit(
        self, train_frame: pd.DataFrame, target: pd.Series | None = None
    ) -> FittedParserNativeV2SemanticFamily:
        del target
        if not self.gene_columns:
            raise ValueError("유전자 열이 하나 이상 필요합니다.")
        missing = [gene for gene in self.gene_columns if gene not in train_frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")
        if not self.schema_path.is_file():
            raise FileNotFoundError(self.schema_path)
        return FittedParserNativeV2SemanticFamily(
            descriptor=FeatureFamilyDescriptor(
                name="parser_v4_native_semantic_v2_token_count",
                version=self.version,
                fit_scope="stateless",
                feature_names=parser_native_v2_feature_names(
                    self.gene_columns, sample_aggregation="token_count"
                ),
            ),
            gene_columns=self.gene_columns,
            schema_sha256=sha256_file(self.schema_path),
            sample_aggregation="token_count",
        )


def native_v2_semantic_contract_record(
    fitted: FittedParserNativeV2SemanticFamily,
) -> dict[str, Any]:
    return {
        "family": fitted.descriptor.name,
        "version": fitted.descriptor.version,
        "fit_scope": fitted.descriptor.fit_scope,
        "schema_sha256": fitted.schema_sha256,
        "output_dimension": fitted.descriptor.output_dimension,
        "feature_names_sha256": fitted.descriptor.feature_names_sha256,
        "model_active_consequences": list(MODEL_ACTIVE_V2_CONSEQUENCES),
        "mutation_presence_policy": "preserve_existing_base_feature",
        "qc_primary_family_policy": "exclusive_and_raw_preserved_outside_matrix",
        "gene_aggregation": "consequence_presence",
        "sample_aggregation": fitted.sample_aggregation,
    }
