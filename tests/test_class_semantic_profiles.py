from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy import sparse

from open_cancer.class_semantic_profiles import ClassSemanticProfileFamily


CLASSES = ("A", "B", "C")


def test_cosine_profiles_are_fit_from_train_and_keep_fixed_class_order() -> None:
    train = sparse.csr_matrix([[3, 0], [1, 0], [0, 4], [0, 2]], dtype=np.float32)
    fitted = ClassSemanticProfileFamily(CLASSES, method="cosine").fit(
        train, pd.Series(["A", "A", "B", "B"])
    )
    transformed = fitted.transform(sparse.csr_matrix([[5, 0], [0, 7], [0, 0]]))

    assert transformed.shape == (3, 3)
    assert np.allclose(
        transformed.toarray(),
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 0.0]],
    )
    assert fitted.class_support == (2, 2, 0)
    assert fitted.descriptor.fit_scope == "fold_train"
    assert fitted.descriptor.feature_names[-1].endswith("__C")


def test_validation_values_cannot_change_fitted_profiles() -> None:
    train = sparse.csr_matrix([[2, 0], [0, 2]], dtype=np.float32)
    family = ClassSemanticProfileFamily(("A", "B"), method="cosine")
    first = family.fit(train, np.array(["A", "B"]))
    first_scores = first.transform(sparse.csr_matrix([[1000, 0]]))
    second_scores = first.transform(sparse.csr_matrix([[0, 1000]]))

    assert first.profile_sha256 == family.fit(train, np.array(["A", "B"])).profile_sha256
    assert first_scores.toarray()[0].tolist() == pytest.approx([1.0, 0.0])
    assert second_scores.toarray()[0].tolist() == pytest.approx([0.0, 1.0])


def test_smoothed_mean_log_likelihood_is_finite_for_unseen_features() -> None:
    train = sparse.csr_matrix([[4, 0, 0], [0, 4, 0]], dtype=np.float32)
    fitted = ClassSemanticProfileFamily(
        ("A", "B"), method="mean_log_likelihood", alpha=1.0
    ).fit(train, np.array(["A", "B"]))
    scores = fitted.transform(sparse.csr_matrix([[0, 0, 3], [0, 0, 0]])).toarray()

    assert np.isfinite(scores).all()
    assert scores[0, 0] == pytest.approx(scores[0, 1])
    assert scores[1].tolist() == pytest.approx([0.0, 0.0])


def test_profile_input_contract_rejects_negative_or_misaligned_values() -> None:
    family = ClassSemanticProfileFamily(("A", "B"))
    with pytest.raises(ValueError, match="비음수"):
        family.fit(sparse.csr_matrix([[1, -1]]), np.array(["A"]))
    with pytest.raises(ValueError, match="target 길이"):
        family.fit(sparse.csr_matrix([[1, 0]]), np.array(["A", "B"]))


def test_audit_record_is_deterministic_and_contains_support() -> None:
    matrix = sparse.csr_matrix([[1, 2], [2, 1]], dtype=np.float32)
    family = ClassSemanticProfileFamily(("A", "B"), method="cosine")
    left = family.fit(matrix, np.array(["A", "B"])).audit_record()
    right = family.fit(matrix, np.array(["A", "B"])).audit_record()

    assert left == right
    assert left["class_support"] == {"A": 1, "B": 1}
    assert len(str(left["profile_sha256"])) == 64


def test_integer_encoded_target_uses_fixed_class_order() -> None:
    matrix = sparse.csr_matrix([[2, 0], [0, 2]], dtype=np.float32)
    fitted = ClassSemanticProfileFamily(("ACC", "BLCA"), method="cosine").fit(
        matrix, np.array([0, 1], dtype=np.int32)
    )
    assert fitted.class_support == (1, 1)
    assert fitted.descriptor.feature_names[0].endswith("__ACC")
