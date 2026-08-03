from __future__ import annotations

import numpy as np
import pytest

from open_cancer.tree_shap_audit import (
    accumulate_contribution_chunk,
    feature_family,
    stratified_validation_sample,
)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("sample__total_variant_count", "sample_aggregate"),
        ("hotspot__BRAF_600", "fixed_hotspot"),
        ("pathway__RTK_RAS__missense_gene_count", "fixed_pathway"),
        ("sample__pathway_rtk_ras__missense_gene_count", "fixed_pathway"),
        ("TP53__mutated", "gene_mutated"),
        ("TP53__max_residue_position", "gene_max_residue_position"),
        ("unknown", "other"),
    ],
)
def test_feature_family(name: str, expected: str) -> None:
    assert feature_family(name) == expected


def test_stratified_validation_sample_is_deterministic_and_fold_limited() -> None:
    target = np.asarray([0] * 8 + [1] * 8 + [2] * 2)
    validation = np.asarray([1, 2, 3, 4, 8, 9, 10, 11, 16, 17])
    first = stratified_validation_sample(
        validation, target, fold=2, class_count=3, max_per_class=2, seed=42
    )
    second = stratified_validation_sample(
        validation, target, fold=2, class_count=3, max_per_class=2, seed=42
    )
    assert np.array_equal(first, second)
    assert set(first).issubset(set(validation))
    assert np.bincount(target[first], minlength=3).tolist() == [2, 2, 2]


def test_accumulate_contribution_chunk_excludes_bias_and_uses_true_class() -> None:
    contributions = np.asarray(
        [
            [[1.0, -2.0, 99.0], [3.0, 4.0, 88.0]],
            [[-5.0, 6.0, 77.0], [7.0, -8.0, 66.0]],
        ]
    )
    global_sum, class_sum, class_rows = accumulate_contribution_chunk(
        contributions, np.asarray([0, 1]), class_count=2
    )
    assert global_sum.tolist() == [16.0, 20.0]
    assert class_sum.tolist() == [[1.0, 2.0], [7.0, 8.0]]
    assert class_rows.tolist() == [1, 1]


def test_accumulate_contribution_chunk_rejects_invalid_shape() -> None:
    with pytest.raises(ValueError, match="shape"):
        accumulate_contribution_chunk(
            np.zeros((2, 3)), np.asarray([0, 1]), class_count=2
        )
