"""Stateless fixed observable cancer-marker mutation proxy features."""

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


class ObservableMarkerFeatureError(ValueError):
    """Raised when the frozen marker-proxy catalog or input violates its contract."""


OUTPUT_KINDS = (
    "any_mutated",
    "any_nonsynonymous",
    "any_lof",
    "multi_gene_mutated",
)
NONSYNONYMOUS_TYPES = frozenset({"missense", "nonsense", "frameshift", "complex"})
LOF_TYPES = frozenset({"nonsense", "frameshift"})


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ObservableMarkerFeatureError(message)


def _tokens(cell: Any) -> tuple[str, ...]:
    if not isinstance(cell, str) or not cell.strip() or cell.strip() == "WT":
        return ()
    return tuple(token for token in cell.split() if token and token != "WT")


def load_observable_marker_panels(
    path: str | Path,
) -> tuple[dict[str, tuple[str, ...]], dict[str, Any]]:
    """Load and validate the versioned, target-independent marker panels."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    _require(document.get("feature_policy", {}).get("target_used") is False, "target_used는 false여야 합니다.")
    _require(
        document.get("feature_policy", {}).get("public_leaderboard_used") is False,
        "public_leaderboard_used는 false여야 합니다.",
    )
    source = document.get("panels")
    _require(isinstance(source, dict) and source, "고정 marker panel이 필요합니다.")
    panels: dict[str, tuple[str, ...]] = {}
    for name, definition in source.items():
        _require(isinstance(name, str) and name.endswith("_proxy"), f"proxy 이름이 올바르지 않습니다: {name}")
        _require(isinstance(definition, dict), f"{name}: panel 정의가 필요합니다.")
        genes = tuple(str(gene).strip() for gene in definition.get("genes", ()))
        _require(genes and all(genes), f"{name}: gene 목록이 필요합니다.")
        _require(len(genes) == len(set(genes)), f"{name}: gene이 중복됩니다.")
        interpretation = str(definition.get("interpretation", "")).lower()
        _require("proxy" in interpretation, f"{name}: proxy 해석 한계가 필요합니다.")
        panels[name] = genes
    return panels, document


@dataclass(frozen=True)
class FittedObservableMarkerFamily:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    catalog_panels: dict[str, tuple[str, ...]]
    intersections: dict[str, tuple[str, ...]]
    missing_catalog_genes: tuple[str, ...]

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        _require(not missing, f"입력에 유전자 열이 없습니다: {missing[:5]}")
        output = np.zeros(
            (len(frame), len(self.intersections) * len(OUTPUT_KINDS)),
            dtype=np.float32,
        )
        used_genes = tuple(
            sorted({gene for genes in self.intersections.values() for gene in genes})
        )
        any_by_gene: dict[str, np.ndarray] = {}
        nonsynonymous_by_gene: dict[str, np.ndarray] = {}
        lof_by_gene: dict[str, np.ndarray] = {}
        for gene in used_genes:
            any_values = np.zeros(len(frame), dtype=bool)
            nonsynonymous_values = np.zeros(len(frame), dtype=bool)
            lof_values = np.zeros(len(frame), dtype=bool)
            for row_index, cell in enumerate(frame[gene].to_numpy(copy=False)):
                mutation_types = {
                    parse_mutation_token(token).mutation_type for token in _tokens(cell)
                }
                any_values[row_index] = bool(mutation_types)
                nonsynonymous_values[row_index] = bool(mutation_types & NONSYNONYMOUS_TYPES)
                lof_values[row_index] = bool(mutation_types & LOF_TYPES)
            any_by_gene[gene] = any_values
            nonsynonymous_by_gene[gene] = nonsynonymous_values
            lof_by_gene[gene] = lof_values

        for panel_index, genes in enumerate(self.intersections.values()):
            mutated_count = sum(
                (any_by_gene[gene].astype(np.int16) for gene in genes),
                start=np.zeros(len(frame), dtype=np.int16),
            )
            offset = panel_index * len(OUTPUT_KINDS)
            output[:, offset] = mutated_count > 0
            output[:, offset + 1] = np.logical_or.reduce(
                [nonsynonymous_by_gene[gene] for gene in genes]
            )
            output[:, offset + 2] = np.logical_or.reduce([lof_by_gene[gene] for gene in genes])
            output[:, offset + 3] = mutated_count >= 2
        return sparse.csr_matrix(output)


@dataclass(frozen=True)
class ObservableMarkerFamily:
    gene_columns: tuple[str, ...]
    knowledge_path: Path
    version: str = "1.0.0"

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedObservableMarkerFamily:
        del target
        _require(bool(self.gene_columns), "유전자 열 계약이 비어 있습니다.")
        missing = [gene for gene in self.gene_columns if gene not in train_frame.columns]
        _require(not missing, f"입력에 유전자 열이 없습니다: {missing[:5]}")
        panels, document = load_observable_marker_panels(self.knowledge_path)
        available = set(self.gene_columns)
        intersections = {
            name: tuple(gene for gene in genes if gene in available)
            for name, genes in panels.items()
        }
        empty_panels = [name for name, genes in intersections.items() if not genes]
        _require(not empty_panels, f"competition panel과 교집합이 없는 marker panel: {empty_panels}")
        missing_catalog_genes = tuple(sorted(
            {gene for genes in panels.values() for gene in genes if gene not in available}
        ))
        feature_names = tuple(
            f"sample__observable_marker_{panel}__{kind}"
            for panel in panels
            for kind in OUTPUT_KINDS
        )
        provenance = KnowledgeProvenance.from_file(
            self.knowledge_path,
            source=str(document["source"]),
            version=str(document["version"]),
            license=str(document["license"]),
            uri=str(document["source_url"]),
        )
        return FittedObservableMarkerFamily(
            descriptor=FeatureFamilyDescriptor(
                name="fixed_observable_cancer_marker_proxies",
                version=self.version,
                fit_scope="stateless",
                feature_names=feature_names,
                external_knowledge=(provenance,),
            ),
            gene_columns=self.gene_columns,
            catalog_panels=panels,
            intersections=intersections,
            missing_catalog_genes=missing_catalog_genes,
        )


def observable_marker_family(
    gene_columns: tuple[str, ...], knowledge_path: Path
) -> ObservableMarkerFamily:
    return ObservableMarkerFamily(gene_columns, knowledge_path)
