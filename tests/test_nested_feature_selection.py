from __future__ import annotations

import numpy as np
from scipy import sparse

from open_cancer.nested_feature_selection import permute_columns


def test_permute_columns_moves_selected_block_together() -> None:
    matrix = sparse.csr_matrix(
        np.asarray(
            [
                [1, 10, 100],
                [2, 20, 200],
                [3, 30, 300],
            ],
            dtype=np.float32,
        )
    )

    result = permute_columns(matrix, [1, 2], np.asarray([2, 0, 1])).toarray()

    np.testing.assert_array_equal(result[:, 0], [1, 2, 3])
    np.testing.assert_array_equal(result[:, 1:], [[30, 300], [10, 100], [20, 200]])
    np.testing.assert_array_equal(
        matrix.toarray(),
        [[1, 10, 100], [2, 20, 200], [3, 30, 300]],
    )


def test_permute_columns_with_empty_selection_returns_copy() -> None:
    matrix = sparse.eye(3, format="csr")

    result = permute_columns(matrix, [], np.asarray([2, 1, 0]))

    assert result is not matrix
    np.testing.assert_array_equal(result.toarray(), matrix.toarray())
