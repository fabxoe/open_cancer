from __future__ import annotations

import numpy as np
import pytest

from open_cancer.checkpoint_selection import (
    CheckpointSelectionError,
    audit_xgboost_validation_iterations,
    predict_xgboost_at_iteration,
    select_macro_f1_iteration,
)
from open_cancer.constants import CLASS_LABELS


class FakeBooster:
    def __init__(self, rounds: int) -> None:
        self.rounds = rounds

    def num_boosted_rounds(self) -> int:
        return self.rounds


class FakeXGBoostModel:
    def __init__(self, probabilities: list[np.ndarray], best_iteration: int) -> None:
        self.probabilities = probabilities
        self.best_iteration = best_iteration
        self.requested_ranges: list[tuple[int, int]] = []

    def get_booster(self) -> FakeBooster:
        return FakeBooster(len(self.probabilities))

    def predict_proba(self, matrix, *, iteration_range: tuple[int, int]) -> np.ndarray:
        del matrix
        self.requested_ranges.append(iteration_range)
        return self.probabilities[iteration_range[1] - 1]


def probability_matrix(predictions: list[int], confidence: float) -> np.ndarray:
    other = (1.0 - confidence) / (len(CLASS_LABELS) - 1)
    output = np.full((len(predictions), len(CLASS_LABELS)), other, dtype=np.float64)
    output[np.arange(len(predictions)), predictions] = confidence
    return output


def test_macro_f1_selection_uses_deterministic_tie_break() -> None:
    selected = select_macro_f1_iteration(
        [
            {"iteration": 4, "macro_f1": 0.5, "log_loss": 1.2},
            {"iteration": 2, "macro_f1": 0.5, "log_loss": 1.1},
            {"iteration": 1, "macro_f1": 0.5, "log_loss": 1.1},
            {"iteration": 3, "macro_f1": 0.4, "log_loss": 0.8},
        ]
    )
    assert selected["iteration"] == 1


def test_validation_audit_can_disagree_with_mlogloss_checkpoint() -> None:
    targets = np.arange(len(CLASS_LABELS), dtype=np.int64)
    wrong_predictions = np.roll(targets, 1)
    one_error = targets.copy()
    one_error[-1] = 0
    model = FakeXGBoostModel(
        [
            probability_matrix(wrong_predictions.tolist(), 0.55),
            probability_matrix(one_error.tolist(), 0.95),
            probability_matrix(targets.tolist(), 0.60),
        ],
        best_iteration=1,
    )

    result = audit_xgboost_validation_iterations(
        model,
        np.ones((len(targets), 2), dtype=np.float32),
        targets,
    )

    assert result["selection_scope"] == "outer_fold_validation_only"
    assert result["training_metric_best"]["iteration"] == 1
    assert result["macro_f1_best"]["iteration"] == 2
    assert result["macro_f1_best"]["macro_f1"] == pytest.approx(1.0)
    assert result["macro_f1_delta"] > 0
    assert model.requested_ranges == [(0, 1), (0, 2), (0, 3)]


def test_explicit_candidate_range_still_audits_training_best() -> None:
    targets = np.arange(len(CLASS_LABELS), dtype=np.int64)
    probabilities = probability_matrix(targets.tolist(), 0.7)
    model = FakeXGBoostModel([probabilities, probabilities, probabilities], best_iteration=1)

    result = audit_xgboost_validation_iterations(
        model,
        np.ones((len(targets), 1), dtype=np.float32),
        targets,
        candidate_iterations=[0, 2],
    )

    assert [record["iteration"] for record in result["curve"]] == [0, 2]
    assert result["training_metric_best"]["iteration"] == 1
    assert model.requested_ranges == [(0, 1), (0, 3), (0, 2)]


def test_prediction_rejects_wrong_class_shape() -> None:
    model = FakeXGBoostModel([np.ones((2, 2), dtype=np.float64)], best_iteration=0)
    with pytest.raises(CheckpointSelectionError, match="클래스 수"):
        predict_xgboost_at_iteration(model, np.ones((2, 1)), 0)


def test_audit_rejects_out_of_range_candidate() -> None:
    targets = np.arange(len(CLASS_LABELS), dtype=np.int64)
    model = FakeXGBoostModel([probability_matrix(targets.tolist(), 0.7)], best_iteration=0)
    with pytest.raises(CheckpointSelectionError, match="범위"):
        audit_xgboost_validation_iterations(
            model,
            np.ones((len(targets), 1)),
            targets,
            candidate_iterations=[1],
        )


def test_real_xgboost_iteration_audit_contract() -> None:
    import xgboost as xgb

    rng = np.random.default_rng(42)
    targets = np.tile(np.arange(len(CLASS_LABELS), dtype=np.int64), 3)
    features = rng.normal(size=(len(targets), 8)).astype(np.float32)
    model = xgb.XGBClassifier(
        objective="multi:softprob",
        num_class=len(CLASS_LABELS),
        n_estimators=4,
        max_depth=2,
        learning_rate=0.1,
        eval_metric="mlogloss",
        early_stopping_rounds=2,
        tree_method="hist",
        n_jobs=1,
        random_state=42,
    )
    model.fit(features, targets, eval_set=[(features, targets)], verbose=False)

    audit = audit_xgboost_validation_iterations(model, features, targets)
    selected = int(audit["macro_f1_best"]["iteration"])
    probabilities = predict_xgboost_at_iteration(model, features, selected)

    assert audit["trained_rounds"] == model.get_booster().num_boosted_rounds()
    assert len(audit["curve"]) == audit["trained_rounds"]
    assert probabilities.shape == (len(targets), len(CLASS_LABELS))
    assert np.allclose(probabilities.sum(axis=1), 1.0)
