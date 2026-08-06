from __future__ import annotations

import numpy as np
import pytest
from scipy import sparse

from open_cancer.semantic_compression import (
    FoldSafeSemanticCompressor,
    SemanticCompressionError,
    infer_column_kind,
    infer_semantic_family,
    is_semantic_core,
    is_semantic_gene_event,
)


def _fixture() -> tuple[sparse.csr_matrix, tuple[str, ...]]:
    names = (
        "sample__native_v3_missense_token_count",
        "sample__native_v3_frameshift_token_count",
        "gene__TP53__native_v3_nonsense_any",
        "gene__EGFR__native_v3_missense_any",
        "gene__KRAS__native_v3_missense_any",
        "gene__APC__native_v3_frameshift_any",
        "gene__PTEN__native_v3_frameshift_any",
        "gene__BRCA1__native_v3_range_stop_any",
        "gene__BRCA2__native_v3_range_no_change_any",
        "gene__VHL__native_v3_no_change_any",
    )
    values = np.asarray(
        [
            [3, 0, 1, 1, 0, 0, 0, 0, 0, 0],
            [2, 1, 1, 1, 0, 1, 0, 0, 0, 0],
            [1, 2, 1, 0, 1, 1, 0, 0, 0, 0],
            [4, 0, 1, 1, 1, 0, 0, 0, 0, 0],
            [2, 2, 1, 0, 1, 1, 1, 0, 0, 0],
            [1, 1, 1, 1, 0, 0, 1, 1, 0, 0],
            [3, 0, 1, 1, 1, 0, 0, 1, 0, 0],
            [1, 3, 1, 0, 1, 1, 1, 0, 1, 0],
            [2, 1, 1, 1, 0, 0, 1, 0, 1, 0],
            [3, 0, 1, 1, 1, 0, 0, 0, 1, 1],
            [1, 2, 1, 0, 1, 1, 1, 0, 0, 1],
            [2, 1, 1, 1, 0, 0, 0, 1, 0, 1],
        ],
        dtype=np.float32,
    )
    return sparse.csr_matrix(values), names


def test_infers_native_v3_family_and_column_kind() -> None:
    assert (
        infer_semantic_family("gene__TP53__native_v3_range_stop_any")
        == "native_v3_range_stop"
    )
    assert (
        infer_semantic_family("sample__native_v3_frameshift_token_count")
        == "native_v3_frameshift"
    )
    assert infer_column_kind("gene__TP53__native_v3_nonsense_any") == "binary"
    assert (
        infer_column_kind("sample__native_v3_nonsense_token_count")
        == "continuous"
    )
    assert is_semantic_core("sample__mutated_gene_count")
    assert is_semantic_core("sample__native_v3_nonsense_token_count")
    assert is_semantic_gene_event("gene__TP53__native_v3_nonsense_any")
    assert not is_semantic_gene_event("TP53__mutated")


def test_selection_is_deterministic_nested_and_core_first() -> None:
    matrix, names = _fixture()
    compressor = FoldSafeSemanticCompressor(
        target_dimensions=(4, 6, 8), min_support=1, inner_splits=3, seed=42
    )
    first = compressor.fit(matrix, names, fold=0)
    second = compressor.fit(matrix, names, fold=0)

    assert np.array_equal(first.selected_indices(8), second.selected_indices(8))
    assert first.manifest(8).to_dict() == second.manifest(8).to_dict()
    assert first.selected_indices(4).tolist() == first.selected_indices(8)[:4].tolist()
    assert first.selected_indices(6).tolist() == first.selected_indices(8)[:6].tolist()
    assert first.selected_indices(4)[:2].tolist() == [0, 1]


def test_transform_replays_outer_train_mask_on_other_rows() -> None:
    matrix, names = _fixture()
    fitted = FoldSafeSemanticCompressor(
        target_dimensions=(6,), min_support=1, inner_splits=3
    ).fit(matrix[:9], names, fold=2)
    validation = fitted.transform(matrix[9:], dimension=6)

    assert validation.shape == (3, 6)
    assert np.array_equal(
        validation.toarray(),
        matrix[9:, fitted.selected_indices(6)].toarray(),
    )


def test_selector_has_no_target_validation_or_test_input() -> None:
    matrix, names = _fixture()
    fitted = FoldSafeSemanticCompressor(
        target_dimensions=(6,), min_support=1, inner_splits=3
    ).fit(matrix[:8], names, fold=1)

    validation_a = matrix[8:].copy()
    validation_b = sparse.csr_matrix(np.ones_like(validation_a.toarray()) * 99)
    assert np.array_equal(
        fitted.selected_indices(6), fitted.selected_indices(6)
    )
    assert fitted.transform(validation_a, dimension=6).shape == (4, 6)
    assert fitted.transform(validation_b, dimension=6).shape == (4, 6)
    assert fitted.manifest(6).to_dict()["selection_policy"] == {
        "target_used": False,
        "validation_used": False,
        "test_used": False,
        "ranking": [
            "semantic_core_first",
            "stable_fold_count_desc",
            "mean_inner_rank_asc",
            "minimum_inner_support_desc",
            "outer_support_desc",
            "family_asc",
            "feature_name_asc",
        ],
    }


def test_saint_dataset_preserves_types_names_and_finite_values() -> None:
    matrix, names = _fixture()
    fitted = FoldSafeSemanticCompressor(
        target_dimensions=(6,), min_support=1, inner_splits=3
    ).fit(matrix, names, fold=0)
    dataset = fitted.build_saint_dataset(matrix, dimension=6)

    assert dataset.values.shape == (12, 6)
    assert dataset.values.dtype == np.float32
    assert np.isfinite(dataset.values).all()
    assert dataset.continuous_indices == (0, 1)
    assert dataset.binary_indices == (2, 3, 4, 5)
    assert dataset.estimated_dense_bytes == 12 * 6 * 4
    assert dataset.feature_names == tuple(
        record.name for record in fitted.ranked_features[:6]
    )


def test_dense_memory_limit_is_enforced() -> None:
    matrix, names = _fixture()
    fitted = FoldSafeSemanticCompressor(
        target_dimensions=(6,), min_support=1, inner_splits=3
    ).fit(matrix, names, fold=0)
    with pytest.raises(SemanticCompressionError, match="예상 크기"):
        fitted.build_saint_dataset(matrix, dimension=6, max_dense_bytes=1)


def test_duplicate_names_and_insufficient_features_are_rejected() -> None:
    matrix, names = _fixture()
    compressor = FoldSafeSemanticCompressor(
        target_dimensions=(8,), min_support=20, inner_splits=3
    )
    with pytest.raises(SemanticCompressionError, match="최대 목표 차원"):
        compressor.fit(matrix, names, fold=0)

    duplicate_names = (*names[:-1], names[-2])
    with pytest.raises(SemanticCompressionError, match="중복"):
        FoldSafeSemanticCompressor(
            target_dimensions=(4,), min_support=1, inner_splits=3
        ).fit(matrix, duplicate_names, fold=0)


def test_transform_rejects_mismatched_input_schema_width() -> None:
    matrix, names = _fixture()
    fitted = FoldSafeSemanticCompressor(
        target_dimensions=(4,), min_support=1, inner_splits=3
    ).fit(matrix, names, fold=0)
    with pytest.raises(SemanticCompressionError, match="dimension"):
        fitted.transform(matrix[:, :-1], dimension=4)


def test_compatibility_gene_columns_never_enter_semantic_selection() -> None:
    matrix, names = _fixture()
    compatibility = sparse.csr_matrix(np.ones((matrix.shape[0], 2), dtype=np.float32))
    expanded = sparse.hstack([compatibility, matrix], format="csr")
    expanded_names = ("TP53__mutated", "TP53__missing", *names)
    fitted = FoldSafeSemanticCompressor(
        target_dimensions=(6,), min_support=1, inner_splits=3
    ).fit(expanded, expanded_names, fold=0)

    selected_names = [record.name for record in fitted.ranked_features[:6]]
    assert "TP53__mutated" not in selected_names
    assert "TP53__missing" not in selected_names
