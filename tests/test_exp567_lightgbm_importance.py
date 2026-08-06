import numpy as np
from scipy import sparse

from open_cancer.tree_shap_audit import feature_family


def _load_helpers():
    import sys
    from pathlib import Path

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    from audit_exp567_lightgbm_feature_importance import (  # noqa: PLC0415
        audit_family,
        permute_sparse_family,
    )

    return audit_family, permute_sparse_family


def test_audit_family_separates_class_cosine_from_sample_aggregate():
    audit_family, _ = _load_helpers()
    assert audit_family("sample__parser_v4_class_profile_cosine__BRCA") == "class_cosine"
    assert audit_family("sample__mutated_gene_count") == feature_family(
        "sample__mutated_gene_count"
    )


def test_sparse_family_permutation_moves_only_selected_columns():
    _, permute_sparse_family = _load_helpers()
    matrix = sparse.csr_matrix(
        np.asarray([[1, 10, 100], [2, 20, 200], [3, 30, 300]], dtype=np.float32)
    )
    actual = permute_sparse_family(
        matrix, np.asarray([0, 2]), np.asarray([2, 0, 1])
    ).toarray()
    expected = np.asarray(
        [[3, 10, 300], [1, 20, 100], [2, 30, 200]], dtype=np.float32
    )
    np.testing.assert_array_equal(actual, expected)


def test_sparse_family_permutation_rejects_invalid_row_order():
    _, permute_sparse_family = _load_helpers()
    matrix = sparse.eye(3, format="csr")
    try:
        permute_sparse_family(matrix, np.asarray([0]), np.asarray([0, 0, 2]))
    except ValueError as error:
        assert "every row exactly once" in str(error)
    else:
        raise AssertionError("invalid permutation must fail")
