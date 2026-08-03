from __future__ import annotations

import numpy as np
from scipy import sparse

from open_cancer.fold_feature_selection import RareMutationPresencePruner


def test_rare_pruner_removes_only_rare_mutation_presence_columns() -> None:
    features = sparse.csr_matrix(
        np.asarray(
            [
                [1, 1, 0, 0],
                [1, 0, 1, 0],
                [1, 0, 0, 1],
                [0, 0, 0, 1],
            ],
            dtype=np.float32,
        )
    )
    names = ("A__mutated", "B__mutated", "B__missense", "C__mutated")
    result = RareMutationPresencePruner(min_positive_count=2).select(
        features, np.zeros(4, dtype=np.int32), names, fold=3
    )

    assert result.selected_indices == (0, 2, 3)
    assert result.metadata["dropped_feature_names"] == ["B__mutated"]
    assert result.metadata["dropped_prevalence"] == {"B": 1}
