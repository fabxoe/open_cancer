from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics import f1_score

from open_cancer.constants import CLASS_LABELS
from open_cancer.nested_decision_offset import (
    NestedDecisionOffsetError,
    apply_class_offset,
    fit_inner_cross_fitted_probabilities,
    search_class_offsets,
)

N_CLASSES = len(CLASS_LABELS)


def test_apply_class_offset_zero_offset_is_identity() -> None:
    rng = np.random.default_rng(0)
    raw = rng.dirichlet(np.ones(N_CLASSES), size=10)
    adjusted = apply_class_offset(raw, np.zeros(N_CLASSES))
    np.testing.assert_allclose(adjusted, raw, atol=1e-10)


def test_apply_class_offset_boosts_target_class_share() -> None:
    probabilities = np.tile(np.full(N_CLASSES, 1.0 / N_CLASSES), (5, 1))
    offset = np.zeros(N_CLASSES)
    offset[0] = 2.0  # heavily favor class 0
    adjusted = apply_class_offset(probabilities, offset)
    assert (adjusted[:, 0] > adjusted[:, 1]).all()
    np.testing.assert_allclose(adjusted.sum(axis=1), 1.0, atol=1e-10)


def test_apply_class_offset_rejects_wrong_class_count() -> None:
    with pytest.raises(NestedDecisionOffsetError):
        apply_class_offset(np.ones((3, 5)), np.zeros(5))


def test_search_class_offsets_recovers_a_systematically_underpredicted_class() -> None:
    # Two active classes (0 and 5, e.g. DLBC's index): class 0 is predicted
    # well, but true class-5 rows are borderline-misclassified as class 0
    # (p0 just edges out p5). A positive offset on class 5 should flip these
    # close calls and raise class 5's F1 -- and macro F1 with it -- without
    # needing to touch outer validation/test.
    rng = np.random.default_rng(1)
    n_per_class = 60
    targets = np.concatenate([np.zeros(n_per_class), np.full(n_per_class, 5)]).astype(np.int64)

    base = np.full((2 * n_per_class, N_CLASSES), 0.01)
    # True class-0 rows: predicted correctly and confidently.
    base[:n_per_class, 0] = 0.6
    base[:n_per_class, 5] = 0.05
    # True class-5 rows: class 0 just edges out the true class 5.
    base[n_per_class:, 0] = 0.42
    base[n_per_class:, 5] = 0.38
    base = base / base.sum(axis=1, keepdims=True)

    baseline_pred = base.argmax(axis=1)
    baseline_macro_f1 = f1_score(
        targets, baseline_pred, labels=np.arange(N_CLASSES), average="macro", zero_division=0
    )
    assert (baseline_pred[n_per_class:] == 0).all()  # confirm the setup is genuinely borderline

    result = search_class_offsets(base, targets)
    offset = result["offset"]
    # The 2-active-class setup is symmetric: raising offset[5] or lowering
    # offset[0] both flip the borderline rows, and coordinate descent visits
    # class 0 first -- so only assert on the outcome, not which coordinate moved.
    assert offset[5] > 0 or offset[0] < 0

    adjusted = apply_class_offset(base, offset)
    adjusted_pred = adjusted.argmax(axis=1)
    adjusted_macro_f1 = f1_score(
        targets, adjusted_pred, labels=np.arange(N_CLASSES), average="macro", zero_division=0
    )
    assert adjusted_macro_f1 > baseline_macro_f1
    assert int((adjusted_pred[n_per_class:] == 5).sum()) > 0


def test_search_class_offsets_stays_near_zero_on_pure_noise() -> None:
    # No systematic pattern to exploit; regularization should keep the
    # search from chasing noise into large offsets.
    rng = np.random.default_rng(2)
    n = 300
    targets = rng.integers(0, N_CLASSES, size=n)
    probabilities = rng.dirichlet(np.ones(N_CLASSES), size=n)

    result = search_class_offsets(probabilities, targets)
    offset = result["offset"]
    assert np.abs(offset).mean() < 0.5


def test_search_class_offsets_never_reduces_regularized_score() -> None:
    rng = np.random.default_rng(3)
    n = 150
    targets = rng.integers(0, N_CLASSES, size=n)
    probabilities = rng.dirichlet(np.ones(N_CLASSES) * 2.0, size=n)

    result = search_class_offsets(probabilities, targets)
    trace = result["trace"]
    scores = [entry["regularized_score"] for entry in trace]
    assert all(later >= earlier for earlier, later in zip(scores, scores[1:]))


def test_fit_inner_cross_fitted_probabilities_covers_every_row_exactly_once() -> None:
    rng = np.random.default_rng(4)
    n = 90
    targets = rng.integers(0, N_CLASSES, size=n)
    features = rng.normal(size=(n, 3))

    def fake_train_fn(inner_train_idx, inner_holdout_idx):
        # Predict the inner-train empirical class distribution for every
        # held-out row -- deliberately ignores features, just needs the
        # right shape and to never touch the held-out targets.
        counts = np.bincount(targets[inner_train_idx], minlength=N_CLASSES).astype(np.float64)
        counts += 1.0  # avoid exact zeros
        distribution = counts / counts.sum()
        return np.tile(distribution, (len(inner_holdout_idx), 1))

    result = fit_inner_cross_fitted_probabilities(
        features=features, targets=targets, train_fn=fake_train_fn, seed=42
    )
    assert result.probabilities.shape == (n, N_CLASSES)
    np.testing.assert_allclose(result.probabilities.sum(axis=1), 1.0, atol=1e-10)
    assert sorted(np.unique(result.inner_fold_assignment).tolist()) == [0, 1, 2]
    # Every inner fold's held-out rows are disjoint and together cover all n rows.
    counts_per_fold = np.bincount(result.inner_fold_assignment, minlength=3)
    assert counts_per_fold.sum() == n
    assert (counts_per_fold > 0).all()


def test_fit_inner_cross_fitted_probabilities_rejects_bad_shape_from_train_fn() -> None:
    rng = np.random.default_rng(5)
    n = 30
    targets = rng.integers(0, N_CLASSES, size=n)
    features = rng.normal(size=(n, 2))

    def bad_train_fn(inner_train_idx, inner_holdout_idx):
        return np.ones((len(inner_holdout_idx), N_CLASSES - 1))  # wrong class count

    with pytest.raises(NestedDecisionOffsetError):
        fit_inner_cross_fitted_probabilities(
            features=features, targets=targets, train_fn=bad_train_fn, seed=42
        )
