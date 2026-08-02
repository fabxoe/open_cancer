from __future__ import annotations

import numpy as np
from scipy import sparse

from open_cancer.correlation_pair_features import (
    append_pair_categorical_features,
    pair_feature_names,
)


def test_pair_features_encode_three_mutation_states() -> None:
    features = sparse.csr_matrix(
        np.asarray(
            [
                [1, 0, 1],
                [0, 1, 1],
                [1, 1, 0],
                [0, 0, 0],
            ],
            dtype=np.float32,
        )
    )
    names = ("A__mutated", "B__mutated", "C__missense")
    pairs = [{"left_gene": "A", "right_gene": "B"}]

    transformed = append_pair_categorical_features(features, names, pairs).toarray()

    assert pair_feature_names(pairs) == (
        "correlation_pair__A__B__only_left",
        "correlation_pair__A__B__only_right",
        "correlation_pair__A__B__both_mutated",
    )
    np.testing.assert_array_equal(
        transformed[:, -3:],
        np.asarray([[1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 0]], dtype=np.float32),
    )


def test_pair_features_return_original_matrix_for_empty_pairs() -> None:
    features = sparse.eye(3, format="csr", dtype=np.float32)
    assert append_pair_categorical_features(features, ("A__mutated",) * 3, []) is features
