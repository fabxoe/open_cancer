from __future__ import annotations

import numpy as np
from scipy import sparse

from open_cancer.fold_feature_selection import MrmrMutationPresenceSelector


def test_mrmr_prefers_nonredundant_signal_and_keeps_complete_gene_blocks() -> None:
    targets = np.repeat(np.arange(3, dtype=np.int32), 30)
    features = np.zeros((90, 8), dtype=np.float64)
    features[:, 0] = targets == 0
    features[:, 1] = targets == 0
    features[:, 2] = targets == 0  # duplicate of A: relevant but redundant
    features[:, 3] = targets == 1
    features[:, 4] = targets == 1
    features[:, 5] = targets == 2
    features[:, 6] = 1.0
    features[:, 7] = targets == 0
    names = (
        "A__mutated",
        "A__missense",
        "A_DUP__mutated",
        "B__mutated",
        "B__missense",
        "C__mutated",
        "sample__mutated_gene_count",
        "hotspot__A_1",
    )
    selector = MrmrMutationPresenceSelector(min_positive_count=5, selected_gene_count=2)

    first = selector.select(sparse.csr_matrix(features), targets, names, fold=0)
    second = selector.select(sparse.csr_matrix(features), targets, names, fold=0)

    assert first.selected_indices == second.selected_indices
    assert first.metadata["selected_gene_names"] == ["A", "B"]
    selected_names = {names[index] for index in first.selected_indices}
    assert "A__mutated" in selected_names
    assert "A__missense" in selected_names
    assert "B__mutated" in selected_names
    assert "B__missense" in selected_names
    assert "A_DUP__mutated" not in selected_names
    assert "sample__mutated_gene_count" in selected_names
    assert "hotspot__A_1" in selected_names
