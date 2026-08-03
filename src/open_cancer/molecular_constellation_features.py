"""Stateless cancer-lineage molecular constellation features."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FeatureFamilyDescriptor, KnowledgeProvenance


class MolecularConstellationError(ValueError):
    """Raised when a lineage-module definition violates its fixed contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MolecularConstellationError(message)


def _is_mutated(cell: Any) -> bool:
    return isinstance(cell, str) and bool(cell.strip()) and cell.strip() != "WT"


def load_molecular_modules(path: str | Path) -> tuple[dict[str, dict[str, tuple[str, ...]]], dict[str, Any]]:
    """Load fixed core/partner modules and reject malformed or duplicate genes."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    source = document.get("modules")
    _require(isinstance(source, dict) and source, "고정 molecular module이 필요합니다.")
    modules: dict[str, dict[str, tuple[str, ...]]] = {}
    for name, definition in source.items():
        _require(isinstance(name, str) and name, "module 이름이 올바르지 않습니다.")
        _require(isinstance(definition, dict), f"{name}: module 정의가 필요합니다.")
        core = tuple(str(gene).strip() for gene in definition.get("core_genes", ()))
        partners = tuple(str(gene).strip() for gene in definition.get("partner_genes", ()))
        _require(core and partners, f"{name}: core와 partner gene이 모두 필요합니다.")
        _require(all(core + partners), f"{name}: 빈 gene 이름이 있습니다.")
        _require(len(core) == len(set(core)), f"{name}: core gene이 중복됩니다.")
        _require(len(partners) == len(set(partners)), f"{name}: partner gene이 중복됩니다.")
        _require(not set(core).intersection(partners), f"{name}: core/partner가 겹칩니다.")
        modules[name] = {"core": core, "partners": partners}
    return modules, document


@dataclass(frozen=True)
class FittedMolecularConstellationFamily:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    modules: dict[str, dict[str, tuple[str, ...]]]
    intersections: dict[str, dict[str, tuple[str, ...]]]

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        _require(not missing, f"입력에 유전자 열이 없습니다: {missing[:5]}")
        output = np.zeros((len(frame), len(self.modules) * 3), dtype=np.float32)
        for module_index, module_name in enumerate(self.modules):
            intersected = self.intersections[module_name]
            core = intersected["core"]
            partners = intersected["partners"]
            all_genes = core + partners
            offset = module_index * 3
            for row_index, row in enumerate(
                frame.loc[:, list(all_genes)].itertuples(index=False, name=None)
            ):
                states = tuple(_is_mutated(cell) for cell in row)
                mutated_count = sum(states)
                core_hit = any(states[: len(core)])
                partner_hit = any(states[len(core) :])
                output[row_index, offset] = mutated_count
                output[row_index, offset + 1] = float(mutated_count >= 2)
                output[row_index, offset + 2] = float(core_hit and partner_hit)
        return sparse.csr_matrix(output)


@dataclass(frozen=True)
class MolecularConstellationFamily:
    gene_columns: tuple[str, ...]
    knowledge_path: Path
    version: str = "1.0.0"

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedMolecularConstellationFamily:
        del target
        missing = [gene for gene in self.gene_columns if gene not in train_frame.columns]
        _require(not missing and self.gene_columns, "유전자 열 계약이 올바르지 않습니다.")
        modules, document = load_molecular_modules(self.knowledge_path)
        available = set(self.gene_columns)
        intersections = {
            name: {
                group: tuple(gene for gene in genes if gene in available)
                for group, genes in definition.items()
            }
            for name, definition in modules.items()
        }
        incomplete = [
            name
            for name, definition in intersections.items()
            if not definition["core"] or not definition["partners"]
        ]
        _require(not incomplete, f"panel에서 core/partner가 사라진 module입니다: {incomplete}")
        feature_names = tuple(
            feature
            for name in modules
            for feature in (
                f"sample__lineage_{name}__mutated_gene_count",
                f"sample__lineage_{name}__multi_gene_indicator",
                f"sample__lineage_{name}__core_partner_indicator",
            )
        )
        provenance = KnowledgeProvenance.from_file(
            self.knowledge_path,
            source=str(document["source"]),
            version=str(document["version"]),
            license=str(document["license"]),
            uri=str(document["source_url"]),
        )
        return FittedMolecularConstellationFamily(
            descriptor=FeatureFamilyDescriptor(
                name="molecular_constellation",
                version=self.version,
                fit_scope="stateless",
                feature_names=feature_names,
                external_knowledge=(provenance,),
            ),
            gene_columns=self.gene_columns,
            modules=modules,
            intersections=intersections,
        )
