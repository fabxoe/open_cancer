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

# The TSG-labeled subset of CELL_CYCLE_GENES (og_tsg == "TSG" in the
# catalog). Used by Issue #173 (P_lof_in_tsg_cellcycle).
CELL_CYCLE_TSG_GENES: tuple[str, ...] = (
    "CDKN1A",
    "CDKN1B",
    "CDKN2A",
    "CDKN2B",
    "CDKN2C",
    "RB1",
)

_TRUNCATING_TYPES = frozenset({"nonsense", "frameshift"})


def _compute_token_flag(
    frame: pd.DataFrame,
    genes: tuple[str, ...],
    matches: "callable[[str], bool]",
) -> np.ndarray:
    """1.0 if any token in any of `genes` satisfies `matches(mutation_type)`.

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
                if matches(classify_mutation_token(token)):
                    flags[row] = 1.0
                    break
            if flags[row]:
                break
    return flags


def compute_any_nonsilent_flag(
    frame: pd.DataFrame, genes: tuple[str, ...]
) -> np.ndarray:
    """1.0 if any of `genes` carries a nonsilent (non-WT, non-synonymous) token."""

    return _compute_token_flag(frame, genes, matches=lambda kind: kind != "synonymous")


def compute_truncating_flag(frame: pd.DataFrame, genes: tuple[str, ...]) -> np.ndarray:
    """1.0 if any of `genes` carries a truncating (nonsense or frameshift) token.

    Missense is intentionally excluded (LoF-specific signal for TSGs), and
    synonymous is excluded by definition of `_TRUNCATING_TYPES`.
    """

    return _compute_token_flag(frame, genes, matches=lambda kind: kind in _TRUNCATING_TYPES)
