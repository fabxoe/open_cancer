from __future__ import annotations

import numpy as np
from scipy import sparse

from open_cancer.fold_feature_selection import ElasticNetStabilitySelector


def test_elastic_net_selector_keeps_complete_gene_blocks_and_global_features() -> None:
    targets = np.repeat(np.arange(3, dtype=np.int32), 20)
    features = np.zeros((60, 8), dtype=np.float64)
    features[:, 0] = targets == 0
    features[:, 1] = targets == 0
    features[:, 2] = targets == 1
    features[:, 3] = targets == 1
    features[:, 4] = targets == 2
    features[:, 5] = targets == 2
    features[:, 6] = 1.0
    features[:, 7] = targets == 0
    names = (
        "A__mutated",
        "A__missense",
        "B__mutated",
        "B__missense",
        "C__mutated",
        "C__missense",
        "sample__mutated_gene_count",
        "hotspot__A_1",
    )
    selector = ElasticNetStabilitySelector(
        c_values=(0.1, 1.0),
        l1_ratio=0.5,
        inner_splits=3,
        subsample_fraction=0.75,
        repetitions=2,
        min_frequency=1,
        min_genes=2,
        max_genes=2,
        seed=42,
        max_iter=200,
        n_jobs=2,
    )

    first = selector.select(sparse.csr_matrix(features), targets, names, fold=0)
    second = selector.select(sparse.csr_matrix(features), targets, names, fold=0)

    assert first.selected_indices == second.selected_indices
    selected_names = {names[index] for index in first.selected_indices}
    selected_genes = first.metadata["selected_gene_names"]
    assert len(selected_genes) == 2
    for gene in selected_genes:
        assert f"{gene}__mutated" in selected_names
        assert f"{gene}__missense" in selected_names
    assert "sample__mutated_gene_count" in selected_names
    assert "hotspot__A_1" in selected_names
    assert first.metadata["selected_feature_count"] == len(first.selected_indices)
