"""Target-independent diagnostics for raw gene mutation-presence columns."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.fold_feature_selection import FoldFeatureSelection, PhiJaccardGreedyPruner


def raw_mutation_presence(frame: pd.DataFrame) -> tuple[sparse.csr_matrix, tuple[str, ...]]:
    """Return one binary ``GENE__mutated`` column per raw gene.

    The diagnostic deliberately does not inspect ``SUBCLASS``.  Empty strings
    and ``WT`` both mean no recorded mutation, matching the project's baseline
    mutation-presence convention.
    """
    gene_columns = tuple(column for column in frame.columns if column not in {"ID", "SUBCLASS"})
    if not gene_columns:
        raise ValueError("유전자 열이 없습니다.")
    values = frame.loc[:, gene_columns].to_numpy(dtype=object)
    presence = ((values != "") & (values != "WT")).astype(np.int8, copy=False)
    return sparse.csr_matrix(presence), tuple(f"{gene}__mutated" for gene in gene_columns)


def phi_jaccard_audit(
    features: sparse.csr_matrix,
    feature_names: tuple[str, ...],
    *,
    phi_min: float,
    jaccard_min: float,
    min_joint_count: int,
) -> FoldFeatureSelection:
    """Run the same deterministic pair policy used by the official ladder.

    C0 is a whole-train diagnostic only.  Its zero target vector is ignored by
    the target-independent selector and exists solely to satisfy the common
    fold-selector protocol.
    """
    selector = PhiJaccardGreedyPruner(
        phi_min=phi_min,
        jaccard_min=jaccard_min,
        min_joint_count=min_joint_count,
    )
    return selector.select(
        features,
        np.zeros(features.shape[0], dtype=np.int8),
        feature_names,
        fold=-1,
    )
