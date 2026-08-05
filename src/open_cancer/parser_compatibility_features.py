"""Parser-v4 projection into the historical five lexical feature families."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.canonical_mutation_events import parse_canonical_gene_cell
from open_cancer.feature_family import FeatureFamilyDescriptor
from open_cancer.mutation_features import MUTATION_TYPES
from open_cancer.mutation_parser_contract import RoutedProteinMutation


PARSER_COMPATIBILITY_FEATURE_VERSION = "1.0.0"


def compatibility_family(routed: RoutedProteinMutation) -> str:
    if routed.route == "substitution":
        return {
            "missense": "missense",
            "no_change": "synonymous",
            "nonsense": "nonsense",
        }.get(routed.event_type, "complex")
    if routed.route == "frameshift":
        return "frameshift"
    return "complex"


def parser_compatibility_feature_names(
    gene_columns: tuple[str, ...],
) -> tuple[str, ...]:
    return (
        *(f"sample__{family}_count" for family in MUTATION_TYPES),
        *(
            f"{gene}__{family}"
            for gene in gene_columns
            for family in MUTATION_TYPES
        ),
    )


@dataclass(frozen=True)
class FittedParserCompatibilityFamily:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]

    @property
    def base_feature_names_to_drop(self) -> tuple[str, ...]:
        return self.descriptor.feature_names

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")
        family_index = {name: index for index, name in enumerate(MUTATION_TYPES)}
        sample_width = len(MUTATION_TYPES)
        gene_width = len(MUTATION_TYPES)
        sample_counts = np.zeros((len(frame), sample_width), dtype=np.float32)
        rows: list[int] = []
        columns: list[int] = []
        values: list[float] = []
        for gene_index, gene in enumerate(self.gene_columns):
            gene_values = frame[gene].to_numpy(dtype=object, copy=False)
            for row_index, cell in enumerate(gene_values):
                parsed = parse_canonical_gene_cell(cell)
                if not parsed.events:
                    continue
                observed: set[str] = set()
                for event in parsed.events:
                    family = compatibility_family(event)
                    sample_counts[row_index, family_index[family]] += 1.0
                    observed.add(family)
                for family in observed:
                    rows.append(row_index)
                    columns.append(
                        sample_width + gene_index * gene_width + family_index[family]
                    )
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
class ParserCompatibilityFamily:
    gene_columns: tuple[str, ...]
    version: str = PARSER_COMPATIBILITY_FEATURE_VERSION

    def fit(
        self, train_frame: pd.DataFrame, target: pd.Series | None = None
    ) -> FittedParserCompatibilityFamily:
        del target
        if not self.gene_columns:
            raise ValueError("유전자 열이 하나 이상 필요합니다.")
        missing = [gene for gene in self.gene_columns if gene not in train_frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")
        return FittedParserCompatibilityFamily(
            descriptor=FeatureFamilyDescriptor(
                name="parser_v4_legacy_five_family_compatibility",
                version=self.version,
                fit_scope="stateless",
                feature_names=parser_compatibility_feature_names(self.gene_columns),
            ),
            gene_columns=self.gene_columns,
        )

