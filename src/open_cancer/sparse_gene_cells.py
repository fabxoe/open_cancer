"""Vectorized discovery of sparse non-WT gene cells.

The competition matrix is almost entirely ``WT``.  Semantic feature families
must therefore avoid visiting every sample-by-gene cell in Python.  This module
uses NumPy/Pandas to locate candidate cells in bounded column blocks and only
then performs the exact whitespace/case check on the small candidate set.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


DEFAULT_GENE_BLOCK_SIZE = 256


def is_non_wt_cell(value: object) -> bool:
    """Return whether *value* contains at least one source mutation token."""

    return (
        isinstance(value, str)
        and bool(value.strip())
        and value.strip().upper() != "WT"
    )


@dataclass(frozen=True)
class SparseGeneCells:
    """Gene-major coordinates and source strings for non-WT cells."""

    row_indices: np.ndarray
    gene_indices: np.ndarray
    values: tuple[str, ...]

    def __len__(self) -> int:
        return len(self.values)


def extract_non_wt_gene_cells(
    frame: pd.DataFrame,
    gene_columns: tuple[str, ...],
    *,
    block_size: int = DEFAULT_GENE_BLOCK_SIZE,
) -> SparseGeneCells:
    """Extract non-WT coordinates without a Python loop over the dense matrix.

    Blocks bound the temporary object/boolean arrays.  Coordinates retain the
    historical gene-major, then row-major order so downstream sparse assembly
    remains deterministic.
    """

    if block_size <= 0:
        raise ValueError("block_size must be positive")
    missing = [gene for gene in gene_columns if gene not in frame.columns]
    if missing:
        raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")

    row_parts: list[np.ndarray] = []
    gene_parts: list[np.ndarray] = []
    source_values: list[str] = []

    for start in range(0, len(gene_columns), block_size):
        block = gene_columns[start : start + block_size]
        values = frame.loc[:, block].to_numpy(dtype=object, copy=False)

        # Fast exclusions cover the real competition data.  The final exact
        # predicate below preserves behavior for whitespace and mixed-case WT
        # fixtures without applying Python string methods to every dense cell.
        candidates = pd.notna(values) & (values != "") & (values != "WT")
        local_genes, rows = np.nonzero(candidates.T)
        if rows.size == 0:
            continue

        kept_rows: list[int] = []
        kept_genes: list[int] = []
        kept_values: list[str] = []
        for local_gene, row in zip(local_genes.tolist(), rows.tolist()):
            value = values[row, local_gene]
            if is_non_wt_cell(value):
                kept_rows.append(row)
                kept_genes.append(start + local_gene)
                kept_values.append(value)
        if kept_rows:
            row_parts.append(np.asarray(kept_rows, dtype=np.int32))
            gene_parts.append(np.asarray(kept_genes, dtype=np.int32))
            source_values.extend(kept_values)

    if not row_parts:
        return SparseGeneCells(
            np.empty(0, dtype=np.int32),
            np.empty(0, dtype=np.int32),
            (),
        )
    return SparseGeneCells(
        np.concatenate(row_parts),
        np.concatenate(gene_parts),
        tuple(source_values),
    )
