"""Stateless literature-fixed cancer-lineage mutation-mechanism proxies."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FeatureFamilyDescriptor, KnowledgeProvenance
from open_cancer.mutation_features import parse_mutation_token


class LineageMechanismError(ValueError):
    """Raised when a lineage-mechanism definition violates its contract."""


GROUPS = ("missense_signal", "lof_signal", "context")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise LineageMechanismError(message)


def _tokens(cell: Any) -> tuple[str, ...]:
    if not isinstance(cell, str) or not cell.strip() or cell.strip() == "WT":
        return ()
    return tuple(token for token in cell.split() if token and token != "WT")


def load_lineage_mechanism_patterns(
    path: str | Path,
) -> tuple[dict[str, dict[str, tuple[str, ...]]], dict[str, Any]]:
    """Load deterministic mechanism groups from a versioned catalog."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    source = document.get("modules")
    _require(isinstance(source, dict) and source, "고정 암종 module이 필요합니다.")
    modules: dict[str, dict[str, tuple[str, ...]]] = {}
    source_keys = {
        "missense_signal": "missense_signal_genes",
        "lof_signal": "lof_signal_genes",
        "context": "context_genes",
    }
    for name, definition in source.items():
        _require(isinstance(name, str) and name, "module 이름이 올바르지 않습니다.")
        _require(isinstance(definition, dict), f"{name}: module 정의가 필요합니다.")
        normalized: dict[str, tuple[str, ...]] = {}
        for group, source_key in source_keys.items():
            genes = tuple(str(gene).strip() for gene in definition.get(source_key, ()))
            _require(genes and all(genes), f"{name}/{group}: gene 목록이 필요합니다.")
            _require(len(genes) == len(set(genes)), f"{name}/{group}: gene이 중복됩니다.")
            normalized[group] = genes
        modules[name] = normalized
    return modules, document


@dataclass(frozen=True)
class FittedLineageMechanismFamily:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    modules: dict[str, dict[str, tuple[str, ...]]]
    intersections: dict[str, dict[str, tuple[str, ...]]]

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        _require(not missing, f"입력에 유전자 열이 없습니다: {missing[:5]}")
        output = np.zeros((len(frame), len(self.modules) * 4), dtype=np.float32)
        used_genes = tuple(
            sorted(
                {
                    gene
                    for definition in self.intersections.values()
                    for genes in definition.values()
                    for gene in genes
                }
            )
        )
        any_by_gene: dict[str, np.ndarray] = {}
        missense_by_gene: dict[str, np.ndarray] = {}
        lof_by_gene: dict[str, np.ndarray] = {}
        for gene in used_genes:
            any_values = np.zeros(len(frame), dtype=np.float32)
            missense_values = np.zeros(len(frame), dtype=np.float32)
            lof_values = np.zeros(len(frame), dtype=np.float32)
            for row_index, cell in enumerate(frame[gene].to_numpy(copy=False)):
                mutation_types = {
                    parse_mutation_token(token).mutation_type
                    for token in _tokens(cell)
                }
                any_values[row_index] = float(bool(mutation_types))
                missense_values[row_index] = float("missense" in mutation_types)
                lof_values[row_index] = float(
                    bool(mutation_types.intersection({"nonsense", "frameshift"}))
                )
            any_by_gene[gene] = any_values
            missense_by_gene[gene] = missense_values
            lof_by_gene[gene] = lof_values

        for module_index, module_name in enumerate(self.modules):
            definition = self.intersections[module_name]
            offset = module_index * 4
            missense_count = sum(
                (missense_by_gene[gene] for gene in definition["missense_signal"]),
                start=np.zeros(len(frame), dtype=np.float32),
            )
            lof_count = sum(
                (lof_by_gene[gene] for gene in definition["lof_signal"]),
                start=np.zeros(len(frame), dtype=np.float32),
            )
            context_count = sum(
                (any_by_gene[gene] for gene in definition["context"]),
                start=np.zeros(len(frame), dtype=np.float32),
            )
            output[:, offset] = missense_count
            output[:, offset + 1] = lof_count
            output[:, offset + 2] = context_count
            output[:, offset + 3] = np.logical_and(
                missense_count > 0, lof_count > 0
            )
        return sparse.csr_matrix(output)


@dataclass(frozen=True)
class LineageMechanismFamily:
    gene_columns: tuple[str, ...]
    knowledge_path: Path
    version: str = "1.0.0"

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedLineageMechanismFamily:
        del target
        missing = [gene for gene in self.gene_columns if gene not in train_frame.columns]
        _require(not missing and self.gene_columns, "유전자 열 계약이 올바르지 않습니다.")
        modules, document = load_lineage_mechanism_patterns(self.knowledge_path)
        available = set(self.gene_columns)
        intersections = {
            name: {
                group: tuple(gene for gene in genes if gene in available)
                for group, genes in definition.items()
            }
            for name, definition in modules.items()
        }
        incomplete = [
            f"{name}/{group}"
            for name, definition in intersections.items()
            for group, genes in definition.items()
            if not genes
        ]
        _require(not incomplete, f"panel 교집합이 없는 module/group입니다: {incomplete}")
        feature_names = tuple(
            feature
            for name in modules
            for feature in (
                f"sample__lineage_mechanism_{name}__missense_gene_count",
                f"sample__lineage_mechanism_{name}__lof_gene_count",
                f"sample__lineage_mechanism_{name}__context_gene_count",
                f"sample__lineage_mechanism_{name}__mixed_indicator",
            )
        )
        provenance = KnowledgeProvenance.from_file(
            self.knowledge_path,
            source=str(document["source"]),
            version=str(document["version"]),
            license=str(document["license"]),
            uri=str(document["source_url"]),
        )
        return FittedLineageMechanismFamily(
            descriptor=FeatureFamilyDescriptor(
                name="lineage_mechanism_patterns",
                version=self.version,
                fit_scope="stateless",
                feature_names=feature_names,
                external_knowledge=(provenance,),
            ),
            gene_columns=self.gene_columns,
            modules=modules,
            intersections=intersections,
        )
