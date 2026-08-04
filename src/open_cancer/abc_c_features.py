"""ABC-Stack C families using compact, fixed functional gene groups."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FeatureFamilyDescriptor, KnowledgeProvenance
from open_cancer.mutation_features import (
    MUTATION_TYPES,
    ParsedMutationToken,
    parse_mutation_token,
)

MutationTokenParser = Callable[[str], ParsedMutationToken]

GroupKind = Literal["pathways", "functional_roles"]


class ABCGroupError(ValueError):
    """Raised when a fixed group definition or source frame is invalid."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ABCGroupError(message)


def _tokens(cell: Any) -> tuple[str, ...]:
    if not isinstance(cell, str) or cell == "" or cell == "WT":
        return ()
    return tuple(token for token in cell.split() if token and token != "WT")


def load_fixed_groups(
    path: str | Path,
    *,
    kind: GroupKind,
) -> tuple[dict[str, tuple[str, ...]], dict[str, Any]]:
    """Load deterministic groups and reject duplicates inside each group."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    source = document.get(kind)
    _require(isinstance(source, dict) and source, f"{kind} 고정 그룹이 필요합니다.")
    groups: dict[str, tuple[str, ...]] = {}
    for name, genes in source.items():
        _require(isinstance(name, str) and name, f"{kind} 그룹 이름이 올바르지 않습니다.")
        _require(isinstance(genes, list) and genes, f"{name}: gene 목록이 필요합니다.")
        normalized = tuple(str(gene).strip() for gene in genes)
        _require(all(normalized), f"{name}: 빈 gene 이름이 있습니다.")
        _require(len(normalized) == len(set(normalized)), f"{name}: gene이 중복됩니다.")
        groups[name] = normalized
    return groups, document


@dataclass(frozen=True)
class FittedFixedGroupBurdenFamily:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    groups: dict[str, tuple[str, ...]]
    intersections: dict[str, tuple[str, ...]]
    token_parser: MutationTokenParser = parse_mutation_token

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        _require(not missing, f"입력에 유전자 열이 없습니다: {missing[:5]}")
        output = np.zeros((len(frame), len(self.groups) * 2), dtype=np.float32)
        for group_index, group_name in enumerate(self.groups):
            genes = self.intersections[group_name]
            for row_index, row in enumerate(frame.loc[:, list(genes)].itertuples(index=False, name=None)):
                mutated = 0
                lof = 0
                for cell in row:
                    tokens = _tokens(cell)
                    if not tokens:
                        continue
                    mutated += 1
                    if any(
                        self.token_parser(token).mutation_type
                        in {"nonsense", "frameshift"}
                        for token in tokens
                    ):
                        lof += 1
                output[row_index, group_index * 2] = mutated
                output[row_index, group_index * 2 + 1] = lof
        return sparse.csr_matrix(output)


@dataclass(frozen=True)
class FittedPathwayMutationTypeFamily:
    """Count affected genes by mutation type inside each fixed pathway."""

    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    groups: dict[str, tuple[str, ...]]
    intersections: dict[str, tuple[str, ...]]
    value_mode: Literal["count", "fraction"] = "count"
    token_parser: MutationTokenParser = parse_mutation_token

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        _require(not missing, f"입력에 유전자 열이 없습니다: {missing[:5]}")
        type_index = {
            mutation_type: index for index, mutation_type in enumerate(MUTATION_TYPES)
        }
        output = np.zeros(
            (len(frame), len(self.groups) * len(MUTATION_TYPES)), dtype=np.float32
        )
        for group_index, group_name in enumerate(self.groups):
            genes = self.intersections[group_name]
            offset = group_index * len(MUTATION_TYPES)
            for row_index, row in enumerate(
                frame.loc[:, list(genes)].itertuples(index=False, name=None)
            ):
                mutated_genes = 0
                for cell in row:
                    tokens = _tokens(cell)
                    if not tokens:
                        continue
                    mutated_genes += 1
                    observed_types = {
                        self.token_parser(token).mutation_type for token in tokens
                    }
                    for mutation_type in observed_types:
                        output[row_index, offset + type_index[mutation_type]] += 1
                if self.value_mode == "fraction" and mutated_genes:
                    output[
                        row_index, offset : offset + len(MUTATION_TYPES)
                    ] /= mutated_genes
        return sparse.csr_matrix(output)


@dataclass(frozen=True)
class FixedGroupBurdenFamily:
    """Base implementation for pathway or role mutated/LOF-gene counts."""

    gene_columns: tuple[str, ...]
    knowledge_path: Path
    kind: GroupKind
    version: str = "1.0.0"
    token_parser: MutationTokenParser = parse_mutation_token

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedFixedGroupBurdenFamily:
        del target
        missing = [gene for gene in self.gene_columns if gene not in train_frame.columns]
        _require(not missing and self.gene_columns, "유전자 열 계약이 올바르지 않습니다.")
        groups, document = load_fixed_groups(self.knowledge_path, kind=self.kind)
        available = set(self.gene_columns)
        intersections = {
            name: tuple(gene for gene in genes if gene in available)
            for name, genes in groups.items()
        }
        empty = [name for name, genes in intersections.items() if not genes]
        _require(not empty, f"대회 유전자와 교집합이 없는 그룹입니다: {empty}")
        prefix = "pathway" if self.kind == "pathways" else "role"
        feature_names = tuple(
            feature
            for name in groups
            for feature in (
                f"sample__{prefix}_{name}__mutated_gene_count",
                f"sample__{prefix}_{name}__lof_gene_count",
            )
        )
        provenance = KnowledgeProvenance.from_file(
            self.knowledge_path,
            source=str(document["source"]),
            version=str(document["version"]),
            license=str(document["license"]),
            uri=str(document["source_url"]),
        )
        return FittedFixedGroupBurdenFamily(
            descriptor=FeatureFamilyDescriptor(
                name="fixed_pathway_burden" if self.kind == "pathways" else "functional_role_burden",
                version=self.version,
                fit_scope="stateless",
                feature_names=feature_names,
                external_knowledge=(provenance,),
            ),
            gene_columns=self.gene_columns,
            groups=groups,
            intersections=intersections,
            token_parser=self.token_parser,
        )


@dataclass(frozen=True)
class PathwayMutationTypeFamily:
    """Stateless fixed-pathway mutation-type affected-gene counts."""

    gene_columns: tuple[str, ...]
    knowledge_path: Path
    value_mode: Literal["count", "fraction"] = "count"
    version: str = "1.0.0"
    token_parser: MutationTokenParser = parse_mutation_token

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedPathwayMutationTypeFamily:
        del target
        missing = [gene for gene in self.gene_columns if gene not in train_frame.columns]
        _require(not missing and self.gene_columns, "유전자 열 계약이 올바르지 않습니다.")
        groups, document = load_fixed_groups(self.knowledge_path, kind="pathways")
        available = set(self.gene_columns)
        intersections = {
            name: tuple(gene for gene in genes if gene in available)
            for name, genes in groups.items()
        }
        empty = [name for name, genes in intersections.items() if not genes]
        _require(not empty, f"대회 유전자와 교집합이 없는 pathway입니다: {empty}")
        suffix = "gene_count" if self.value_mode == "count" else "gene_fraction"
        feature_names = tuple(
            f"sample__pathway_{name}__{mutation_type}_{suffix}"
            for name in groups
            for mutation_type in MUTATION_TYPES
        )
        provenance = KnowledgeProvenance.from_file(
            self.knowledge_path,
            source=str(document["source"]),
            version=str(document["version"]),
            license=str(document["license"]),
            uri=str(document["source_url"]),
        )
        return FittedPathwayMutationTypeFamily(
            descriptor=FeatureFamilyDescriptor(
                name=(
                    "pathway_mutation_type_composition"
                    if self.value_mode == "count"
                    else "pathway_mutation_type_fraction"
                ),
                version=self.version,
                fit_scope="stateless",
                feature_names=feature_names,
                external_knowledge=(provenance,),
            ),
            gene_columns=self.gene_columns,
            groups=groups,
            intersections=intersections,
            value_mode=self.value_mode,
            token_parser=self.token_parser,
        )


def fixed_pathway_burden_family(
    gene_columns: tuple[str, ...],
    knowledge_path: Path,
    *,
    token_parser: MutationTokenParser = parse_mutation_token,
    version: str = "1.0.0",
) -> FixedGroupBurdenFamily:
    return FixedGroupBurdenFamily(
        gene_columns, knowledge_path, "pathways", version, token_parser
    )


def functional_role_burden_family(
    gene_columns: tuple[str, ...], knowledge_path: Path
) -> FixedGroupBurdenFamily:
    return FixedGroupBurdenFamily(gene_columns, knowledge_path, "functional_roles")


def pathway_mutation_type_family(
    gene_columns: tuple[str, ...],
    knowledge_path: Path,
    *,
    token_parser: MutationTokenParser = parse_mutation_token,
    version: str = "1.0.0",
) -> PathwayMutationTypeFamily:
    return PathwayMutationTypeFamily(
        gene_columns, knowledge_path, "count", version, token_parser
    )


def pathway_mutation_type_fraction_family(
    gene_columns: tuple[str, ...], knowledge_path: Path
) -> PathwayMutationTypeFamily:
    return PathwayMutationTypeFamily(
        gene_columns, knowledge_path, value_mode="fraction"
    )
