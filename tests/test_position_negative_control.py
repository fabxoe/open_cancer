import numpy as np
from scipy import sparse

from open_cancer.position_negative_control import permute_position_values


FEATURE_NAMES = [
    "G1__mutated",
    "G1__missense",
    "G1__synonymous",
    "G1__nonsense",
    "G1__frameshift",
    "G1__complex",
    "G1__max_residue_position",
]


def test_permutation_preserves_support_and_mutation_type_strata() -> None:
    matrix = sparse.csr_matrix(
        np.asarray(
            [
                [1, 1, 0, 0, 0, 0, 10],
                [1, 1, 0, 0, 0, 0, 20],
                [1, 1, 0, 0, 0, 0, 30],
                [1, 0, 0, 1, 0, 0, 90],
                [0, 0, 0, 0, 0, 0, 0],
            ],
            dtype=np.float32,
        )
    )

    permuted, report = permute_position_values(
        matrix, FEATURE_NAMES, seed=42
    )
    before = matrix.toarray()
    after = permuted.toarray()

    np.testing.assert_array_equal(before[:, :6], after[:, :6])
    np.testing.assert_array_equal(before[:, 6] > 0, after[:, 6] > 0)
    assert sorted(before[:3, 6]) == sorted(after[:3, 6])
    assert after[3, 6] == 90
    assert after[4, 6] == 0
    assert report["values_in_shuffle_eligible_groups"] == 3
    assert report["support_mismatches"] == 0


def test_permutation_is_deterministic_for_same_seed() -> None:
    values = np.arange(1, 13, dtype=np.float32)
    matrix = sparse.csr_matrix(
        np.column_stack(
            [
                np.ones(12),
                np.ones(12),
                np.zeros((12, 4)),
                values,
            ]
        )
    )

    first, first_report = permute_position_values(
        matrix, FEATURE_NAMES, seed=314
    )
    second, second_report = permute_position_values(
        matrix, FEATURE_NAMES, seed=314
    )

    np.testing.assert_array_equal(first.toarray(), second.toarray())
    assert first_report == second_report


def test_rejects_matrix_feature_name_mismatch() -> None:
    matrix = sparse.csr_matrix(np.zeros((2, 3), dtype=np.float32))

    try:
        permute_position_values(matrix, FEATURE_NAMES, seed=42)
    except ValueError as exc:
        assert "열 수" in str(exc)
    else:
        raise AssertionError("열 수 불일치는 실패해야 합니다.")
