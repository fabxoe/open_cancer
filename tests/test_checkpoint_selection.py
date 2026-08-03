from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from open_cancer.checkpoint_selection import (
    CheckpointSelectionError,
    audit_xgboost_validation_iterations,
    predict_xgboost_at_iteration,
    save_xgboost_iteration_checkpoint,
    select_macro_f1_iteration,
    select_rolling_median_macro_f1_iteration,
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


def test_rolling_median_selection_uses_window_end_and_earlier_tie() -> None:
    records = [
        {"iteration": iteration, "macro_f1": 0.1, "log_loss": 2.0}
        for iteration in range(8)
    ]
    for iteration in (1, 2, 3, 5, 6, 7):
        records[iteration]["macro_f1"] = 0.8

    selected = select_rolling_median_macro_f1_iteration(
        records,
        window_size=3,
        min_iteration=3,
    )

    assert selected["iteration"] == 3
    assert selected["window_start_iteration"] == 1
    assert selected["window_end_iteration"] == 3
    assert selected["rolling_median_macro_f1"] == pytest.approx(0.8)


def test_rolling_median_selection_rejects_missing_candidate_without_fallback() -> None:
    records = [
        {"iteration": iteration, "macro_f1": 0.2, "log_loss": 2.0}
        for iteration in range(10)
    ]
    with pytest.raises(CheckpointSelectionError, match="후보가 없습니다"):
        select_rolling_median_macro_f1_iteration(
            records,
            window_size=5,
            min_iteration=100,
        )


def test_rolling_median_selection_requires_consecutive_curve() -> None:
    records = [
        {"iteration": 0, "macro_f1": 0.2, "log_loss": 2.0},
        {"iteration": 2, "macro_f1": 0.3, "log_loss": 1.9},
    ]
    with pytest.raises(CheckpointSelectionError, match="연속된 전체"):
        select_rolling_median_macro_f1_iteration(
            records,
            window_size=2,
            min_iteration=0,
        )


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


def test_validation_audit_records_complete_rolling_median_history() -> None:
    targets = np.arange(len(CLASS_LABELS), dtype=np.int64)
    probabilities = probability_matrix(targets.tolist(), 0.7)
    model = FakeXGBoostModel([probabilities] * 6, best_iteration=2)

    result = audit_xgboost_validation_iterations(
        model,
        np.ones((len(targets), 1), dtype=np.float32),
        targets,
        selection_policy="macro_f1_rolling_median_validation",
        rolling_window_size=3,
        minimum_iteration=3,
    )

    assert result["selection_policy"] == "macro_f1_rolling_median_validation"
    assert [row["iteration"] for row in result["rolling_median_history"]] == [3, 4, 5]
    assert result["selected_checkpoint"]["iteration"] == 3
    assert result["rolling_median_contract"]["fallback"] == "fail"


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


def test_real_xgboost_iteration_audit_contract(tmp_path) -> None:
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
    checkpoint = tmp_path / "selected.json"
    save_xgboost_iteration_checkpoint(model, checkpoint, selected)
    restored = xgb.XGBClassifier()
    restored.load_model(checkpoint)
    restored_probabilities = restored.predict_proba(features)

    assert audit["trained_rounds"] == model.get_booster().num_boosted_rounds()
    assert len(audit["curve"]) == audit["trained_rounds"]
    assert probabilities.shape == (len(targets), len(CLASS_LABELS))
    assert np.allclose(probabilities.sum(axis=1), 1.0)
    assert np.allclose(restored_probabilities, probabilities, atol=1e-7, rtol=1e-7)


def test_exp223_changes_only_checkpoint_policy_from_exp096() -> None:
    root = Path(__file__).resolve().parents[1]
    baseline = yaml.safe_load(
        (root / "configs/exp096_fixed_pathway_burden.yaml").read_text(encoding="utf-8")
    )
    candidate = yaml.safe_load(
        (root / "configs/exp223_pathway_macro_f1_checkpoint.yaml").read_text(
            encoding="utf-8"
        )
    )

    for key in (
        "seed",
        "split",
        "features",
        "hotspots",
        "external_knowledge",
        "abc_families",
        "model",
    ):
        assert candidate[key] == baseline[key]
    assert candidate["training"]["balanced_sample_weight"] is True
    assert candidate["training"]["checkpoint_selection"] == "macro_f1_validation"


def test_exp279_changes_only_checkpoint_policy_from_exp219() -> None:
    root = Path(__file__).resolve().parents[1]
    baseline = yaml.safe_load(
        (root / "configs/exp219_macro_f1_checkpoint_selection.yaml").read_text(
            encoding="utf-8"
        )
    )
    candidate = yaml.safe_load(
        (root / "configs/exp279_checkpoint_rolling_median.yaml").read_text(
            encoding="utf-8"
        )
    )

    for key in ("seed", "split", "features", "hotspots", "model"):
        assert candidate[key] == baseline[key]
    assert candidate["experiment_id"] == "EXP-279"
    assert candidate["issue_number"] == 279
    assert candidate["parent_experiment"] == "EXP-219"
    assert candidate["training"]["checkpoint_selection"] == (
        "macro_f1_rolling_median_validation"
    )
    assert candidate["training"]["checkpoint_rolling_window"] == 21
    assert candidate["training"]["checkpoint_min_iteration"] == 100
    assert candidate["training"]["checkpoint_no_candidate_policy"] == "fail"
    for key in ("balanced_sample_weight", "missing_policy", "feature_types"):
        assert candidate["training"][key] == baseline["training"][key]


def test_exp279_runner_is_one_to_one() -> None:
    root = Path(__file__).resolve().parents[1]
    runner = (
        root / "scripts" / "run_exp279_checkpoint_rolling_median.py"
    ).read_text(encoding="utf-8")
    assert "exp279_checkpoint_rolling_median.yaml" in runner
    assert "run_exp279_checkpoint_rolling_median.py" in runner
