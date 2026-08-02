"""Pathway-level aggregation features (Issue #167 catalog pilot).

Two layers of the same gene list coexist deliberately:

- `CELL_CYCLE_GENES` is a hard-coded literal (a snapshot of
  `data/external/gene_pathway_mapping.csv`, Issue #167/#168), matching the
  existing `EXTENDED_HOTSPOTS` convention in `hotspot_features.py`. The
  `compute_*_flag` functions use it directly and are what EXP-170/#173's
  recorded OOF/metrics were built from.
- `CellCyclePathwayFamily` (the Feature Factory-registered family used by
  official runners) instead loads gene/role membership at fit-time from the
  small committed `knowledge/tcga_pancanatlas_table_s3_cell_cycle_v1.json`
  file, which carries full `KnowledgeProvenance` (source citation, license,
  original workbook SHA-256, DOI). `test_cell_cycle_gene_list_matches_
  committed_knowledge_file` and `test_cell_cycle_family_matches_direct_
  compute_function` in `tests/test_pathway_aggregation_features.py` lock the
  two layers together so they cannot silently drift apart.

Both ultimately trace back to Sanchez-Vega et al. 2018 Cell Table S3
(Supplementary Table S3, doi:10.1016/j.cell.2018.03.035). The source
workbook is licensed CC BY-NC-ND and gitignored; neither layer reads it at
runtime.

Cell Cycle pathway, 15 genes, 100% covered by the competition's 4,384-gene
panel, no gene overlap with the TP53 pathway sheet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FeatureFamilyDescriptor, KnowledgeProvenance
from open_cancer.mutation_features import classify_mutation_token


class PathwayAggregationError(ValueError):
    """Raised when a pathway aggregation family or its knowledge file is invalid."""


CELL_CYCLE_GENES: tuple[str, ...] = (
    "CDKN1A",
    "CDKN1B",
    "CDKN2A",
    "CDKN2B",
    "CDKN2C",
    "RB1",
    "CCND1",
    "CCND2",
    "CCND3",
    "CCNE1",
    "CDK2",
    "CDK4",
    "CDK6",
    "E2F1",
    "E2F3",
)


def compute_any_nonsilent_flag(
    frame: pd.DataFrame, genes: tuple[str, ...]
) -> np.ndarray:
    """1.0 if any of `genes` carries a nonsilent (non-WT, non-synonymous) token.

    `frame` must contain raw gene-cell strings (WT / blank / space-separated
    mutation tokens), keyed by gene symbol columns.
    """

    missing = [gene for gene in genes if gene not in frame.columns]
    if missing:
        raise ValueError(f"패널에 없는 유전자입니다: {missing}")
    values = frame.loc[:, list(genes)].to_numpy(dtype=object)
    flags = np.zeros(values.shape[0], dtype=np.float32)
    for row in range(values.shape[0]):
        for cell in values[row]:
            if not cell or cell == "WT":
                continue
            for token in cell.split():
                if token == "WT":
                    continue
                if classify_mutation_token(token) != "synonymous":
                    flags[row] = 1.0
                    break
            if flags[row]:
                break
    return flags


def load_cell_cycle_knowledge(path: Path) -> dict[str, str]:
    """Load the {gene: og_tsg} mapping from the committed Table S3 knowledge file."""

    document = json.loads(path.read_text(encoding="utf-8"))
    genes = document.get("genes")
    if not isinstance(genes, dict) or not genes:
        raise PathwayAggregationError(f"'genes' 매핑이 없습니다: {path}")
    invalid = {gene: role for gene, role in genes.items() if role not in {"OG", "TSG"}}
    if invalid:
        raise PathwayAggregationError(f"og_tsg 값이 OG/TSG가 아닙니다: {invalid}")
    return genes


@dataclass(frozen=True)
class FittedCellCyclePathwayFamily:
    """A fitted, single-column Cell Cycle pathway aggregation feature."""

    descriptor: FeatureFamilyDescriptor
    genes: tuple[str, ...]
    kind: str  # "any_nonsilent"; Issue #173 adds "truncating_in_tsg"

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        if self.kind != "any_nonsilent":
            raise PathwayAggregationError(f"지원하지 않는 kind입니다: {self.kind}")
        flags = compute_any_nonsilent_flag(frame, self.genes)
        return sparse.csr_matrix(flags[:, None])


@dataclass(frozen=True)
class CellCyclePathwayFamily:
    """Factory for the Cell Cycle pathway aggregation features (Issue #167/#170).

    Gene membership and OG/TSG labels are loaded from a small committed
    knowledge file (a derived gene-symbol/role summary, not a redistribution
    of the licensed source workbook), giving each fitted feature a traceable
    `KnowledgeProvenance` record.
    """

    knowledge_path: Path
    kind: str  # "any_nonsilent"; Issue #173 adds "truncating_in_tsg"
    version: str = "1.0.0"

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedCellCyclePathwayFamily:
        del target
        if self.kind != "any_nonsilent":
            raise PathwayAggregationError(f"지원하지 않는 kind입니다: {self.kind}")
        document = json.loads(self.knowledge_path.read_text(encoding="utf-8"))
        genes_with_roles = load_cell_cycle_knowledge(self.knowledge_path)
        genes = tuple(genes_with_roles.keys())
        name = "cellcycle_any_nonsilent"
        missing = [gene for gene in genes if gene not in train_frame.columns]
        if missing:
            raise PathwayAggregationError(f"패널에 없는 유전자입니다: {missing}")
        provenance = KnowledgeProvenance.from_file(
            self.knowledge_path,
            source=str(document["source"]),
            version=str(document["version"]),
            license=str(document["license"]),
            uri=f"https://doi.org/{document['article_doi']}",
        )
        return FittedCellCyclePathwayFamily(
            descriptor=FeatureFamilyDescriptor(
                name=name,
                version=self.version,
                fit_scope="stateless",
                feature_names=(f"pathway__{name}",),
                external_knowledge=(provenance,),
            ),
            genes=genes,
            kind=self.kind,
        )


def cell_cycle_any_nonsilent_family(knowledge_path: Path) -> CellCyclePathwayFamily:
    return CellCyclePathwayFamily(knowledge_path=knowledge_path, kind="any_nonsilent")
