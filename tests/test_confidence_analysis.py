import numpy as np

from open_cancer.confidence_analysis import evaluate_pmax_thresholds
from open_cancer.nested_xgb_search import select_best_trial


def test_pmax_thresholds_report_coverage_and_never_filter_submission() -> None:
    probabilities = np.asarray(
        [
            [0.90, 0.10],
            [0.55, 0.45],
            [0.20, 0.80],
            [0.49, 0.51],
        ],
        dtype=np.float64,
    )
    result = evaluate_pmax_thresholds(
        targets=np.asarray([0, 1, 1, 0]),
        probabilities=probabilities,
        class_labels=["A", "B"],
        thresholds=[0.0, 0.7, 0.9],
    )
    assert result["used_for_model_selection"] is False
    assert result["used_for_submission_filtering"] is False
    assert [row["sample_count"] for row in result["thresholds"]] == [4, 2, 1]
    assert [row["coverage"] for row in result["thresholds"]] == [1.0, 0.5, 0.25]


def test_trial_selection_uses_macro_f1_then_log_loss() -> None:
    trials = [
        {
            "trial": 0,
            "mean_macro_f1": 0.40,
            "mean_log_loss": 1.5,
            "parameters": {"max_depth": 3},
        },
        {
            "trial": 1,
            "mean_macro_f1": 0.42,
            "mean_log_loss": 1.7,
            "parameters": {"max_depth": 5},
        },
        {
            "trial": 2,
            "mean_macro_f1": 0.42,
            "mean_log_loss": 1.6,
            "parameters": {"max_depth": 6},
        },
    ]
    assert select_best_trial(trials)["trial"] == 2

