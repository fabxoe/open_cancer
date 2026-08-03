from __future__ import annotations

import numpy as np
from scipy import sparse

from open_cancer.fold_feature_selection import BorutaMutationPresenceSelector


def test_boruta_keeps_confirmed_gene_blocks_and_global_features() -> None:
    targets = np.repeat(np.arange(3, dtype=np.int32), 30)
    features = np.zeros((90, 7), dtype=np.float64)
    features[:, 0] = targets == 0
    features[:, 1] = targets == 0
    features[:, 2] = targets == 1
    features[:, 3] = targets == 1
    features[:, 4] = targets == 2
    features[:, 5] = 1.0
    features[:, 6] = targets == 0
    names = (
        "A__mutated",
        "A__missense",
        "B__mutated",
        "B__missense",
        "C__mutated",
        "sample__mutated_gene_count",
        "hotspot__A_1",
    )
    selector = BorutaMutationPresenceSelector(
        n_estimators=50,
        max_iter=5,
        perc=100,
        seed=42,
        alpha=1.0 - 1e-6,
        n_jobs=1,
    )

    first = selector.select(sparse.csr_matrix(features), targets, names, fold=0)
    second = selector.select(sparse.csr_matrix(features), targets, names, fold=0)

    assert first.selected_indices == second.selected_indices
    selected_names = {names[index] for index in first.selected_indices}
    assert "A" in first.metadata["confirmed_gene_names"]
    assert "A__mutated" in selected_names
    assert "A__missense" in selected_names
    assert "sample__mutated_gene_count" in selected_names
    assert "hotspot__A_1" in selected_names
