"""Pathway-level aggregation features (Issue #167 catalog pilot).

Gene membership below is a hard-coded snapshot from
`data/external/gene_pathway_mapping.csv` (Issue #167 / #168), itself derived
from Sanchez-Vega et al. 2018 Cell Table S3 (Supplementary Table S3,
doi:10.1016/j.cell.2018.03.035). The source workbook is licensed CC
BY-NC-ND and gitignored, so this literal tuple -- not a runtime read of the
external file -- is the reproducible source of truth, matching the existing
`EXTENDED_HOTSPOTS` convention in `hotspot_features.py`.

Cell Cycle pathway, 15 genes, 100% covered by the competition's 4,384-gene
panel, no gene overlap with the TP53 pathway sheet.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from open_cancer.mutation_features import classify_mutation_token

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
