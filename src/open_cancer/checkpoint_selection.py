"""Leakage-safe validation auditing for XGBoost checkpoint iterations."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from sklearn.metrics import f1_score, log_loss

from open_cancer.constants import CLASS_LABELS


class CheckpointSelectionError(ValueError):
    """Raised when an iteration audit violates the checkpoint contract."""


class XGBoostIterationModel(Protocol):
    """Minimal XGBoost classifier surface needed by the auditor."""

    best_iteration: int

    def get_booster(self) -> Any: ...

    def predict_proba(self, matrix: Any, *, iteration_range: tuple[int, int]) -> np.ndarray: ...


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckpointSelectionError(message)


def predict_xgboost_at_iteration(
    model: XGBoostIterationModel,
    matrix: Any,
    iteration: int,
    *,
    class_count: int = len(CLASS_LABELS),
) -> np.ndarray:
    """Predict with trees through one zero-based boosting iteration."""
    _require(isinstance(iteration, int) and iteration >= 0, "iteration은 0 이상의 정수여야 합니다.")
    probabilities = np.asarray(
        model.predict_proba(matrix, iteration_range=(0, iteration + 1)),
        dtype=np.float64,
    )
    _require(probabilities.ndim == 2, "XGBoost 확률은 2차원이어야 합니다.")
    _require(
        probabilities.shape[1] == class_count,
        "XGBoost 확률의 클래스 수가 지정된 모델 클래스 순서와 다릅니다.",
    )
    _require(np.isfinite(probabilities).all(), "XGBoost 확률에 NaN 또는 무한대가 있습니다.")
    _require((probabilities >= 0).all(), "XGBoost 확률에 음수가 있습니다.")
    row_sums = probabilities.sum(axis=1, keepdims=True)
    _require((row_sums > 0).all(), "XGBoost 확률 행의 합이 0입니다.")
    return probabilities / row_sums


def save_xgboost_iteration_checkpoint(
    model: XGBoostIterationModel,
    path: Path,
    iteration: int,
) -> None:
    """Save a replayable booster truncated at one selected iteration."""
    trained_rounds = int(model.get_booster().num_boosted_rounds())
    _require(
        0 <= iteration < trained_rounds,
        "저장할 iteration이 학습된 boosting round 범위를 벗어났습니다.",
    )
    booster = model.get_booster()[: iteration + 1]
    booster.set_attr(best_iteration=str(iteration))
    path.parent.mkdir(parents=True, exist_ok=True)
    booster.save_model(path)


def select_macro_f1_iteration(records: Sequence[dict[str, float | int]]) -> dict[str, float | int]:
    """Select by Macro F1, then lower Log Loss, then earlier iteration."""
    _require(len(records) > 0, "iteration 감사 기록이 비어 있습니다.")
    required = {"iteration", "macro_f1", "log_loss"}
    for record in records:
        _require(required <= record.keys(), "iteration 감사 기록의 필수 필드가 없습니다.")
        _require(int(record["iteration"]) >= 0, "iteration은 0 이상이어야 합니다.")
        _require(
            np.isfinite(float(record["macro_f1"])) and np.isfinite(float(record["log_loss"])),
            "iteration 감사 지표는 유한해야 합니다.",
        )
    return dict(
        min(
            records,
            key=lambda row: (
                -float(row["macro_f1"]),
                float(row["log_loss"]),
                int(row["iteration"]),
            ),
        )
    )


def rolling_median_macro_f1_candidates(
    records: Sequence[dict[str, float | int]],
    *,
    window_size: int,
    min_iteration: int,
) -> list[dict[str, float | int]]:
    """Build complete trailing validation Macro-F1 median candidates.

    The selected checkpoint is the final iteration of the winning window.  A
    complete, consecutive iteration curve is required so a sparse candidate
    list cannot silently change the meaning of the rolling window.
    """
    _require(window_size > 0, "rolling window 크기는 1 이상이어야 합니다.")
    _require(min_iteration >= 0, "최소 iteration은 0 이상이어야 합니다.")
    _require(len(records) > 0, "iteration 감사 기록이 비어 있습니다.")
    required = {"iteration", "macro_f1", "log_loss"}
    ordered = sorted(records, key=lambda row: int(row["iteration"]))
    iterations: list[int] = []
    for record in ordered:
        _require(required <= record.keys(), "iteration 감사 기록의 필수 필드가 없습니다.")
        iteration = int(record["iteration"])
        macro_f1 = float(record["macro_f1"])
        loss = float(record["log_loss"])
        _require(iteration >= 0, "iteration은 0 이상이어야 합니다.")
        _require(
            np.isfinite(macro_f1) and np.isfinite(loss),
            "iteration 감사 지표는 유한해야 합니다.",
        )
        iterations.append(iteration)
    _require(
        len(set(iterations)) == len(iterations),
        "rolling median iteration 감사 기록에 중복 iteration이 있습니다.",
    )
    _require(
        iterations == list(range(iterations[0], iterations[-1] + 1)),
        "rolling median은 연속된 전체 iteration 감사 기록이 필요합니다.",
    )

    candidates: list[dict[str, float | int]] = []
    for index, record in enumerate(ordered):
        iteration = int(record["iteration"])
        if iteration < min_iteration or index + 1 < window_size:
            continue
        window = ordered[index + 1 - window_size : index + 1]
        candidates.append(
            {
                **record,
                "rolling_median_macro_f1": float(
                    np.median([float(row["macro_f1"]) for row in window])
                ),
                "window_start_iteration": int(window[0]["iteration"]),
                "window_end_iteration": iteration,
                "window_size": window_size,
            }
        )
    _require(
        len(candidates) > 0,
        "최소 iteration 이후 완성된 rolling median 후보가 없습니다.",
    )
    return candidates


def select_rolling_median_macro_f1_iteration(
    records: Sequence[dict[str, float | int]],
    *,
    window_size: int,
    min_iteration: int,
) -> dict[str, float | int]:
    """Select the earliest peak of a trailing validation Macro-F1 median."""
    candidates = rolling_median_macro_f1_candidates(
        records,
        window_size=window_size,
        min_iteration=min_iteration,
    )
    return dict(
        min(
            candidates,
            key=lambda row: (
                -float(row["rolling_median_macro_f1"]),
                int(row["iteration"]),
            ),
        )
    )


def audit_xgboost_validation_iterations(
    model: XGBoostIterationModel,
    validation_features: Any,
    validation_targets: np.ndarray,
    *,
    candidate_iterations: Iterable[int] | None = None,
    selection_policy: str = "macro_f1_validation",
    rolling_window_size: int | None = None,
    minimum_iteration: int | None = None,
    model_class_count: int = len(CLASS_LABELS),
    evaluation_targets: np.ndarray | None = None,
    prediction_evaluation_indices: np.ndarray | None = None,
    evaluation_class_count: int | None = None,
) -> dict[str, Any]:
    """Compare validation Macro-F1 and training-metric checkpoint choices.

    Only validation features and labels are accepted. Test features and Public LB
    values are deliberately absent from this API so they cannot influence the
    checkpoint choice.
    """
    targets = np.asarray(validation_targets, dtype=np.int64)
    _require(targets.ndim == 1, "validation target은 1차원이어야 합니다.")
    _require(len(targets) == validation_features.shape[0], "validation feature/target 행이 다릅니다.")
    _require(len(targets) > 0, "validation fold가 비어 있습니다.")
    _require(
        ((targets >= 0) & (targets < model_class_count)).all(),
        "validation target이 지정된 모델 클래스 범위를 벗어났습니다.",
    )
    score_targets = targets
    score_class_count = model_class_count
    prediction_mapping: np.ndarray | None = None
    if evaluation_targets is not None or prediction_evaluation_indices is not None:
        _require(
            evaluation_targets is not None
            and prediction_evaluation_indices is not None
            and evaluation_class_count is not None,
            "대체 평가 공간에는 target, prediction mapping, class count가 모두 필요합니다.",
        )
        score_targets = np.asarray(evaluation_targets, dtype=np.int64)
        prediction_mapping = np.asarray(prediction_evaluation_indices, dtype=np.int64)
        score_class_count = int(evaluation_class_count)
        _require(score_targets.shape == targets.shape, "대체 평가 target 형상이 다릅니다.")
        _require(
            prediction_mapping.shape == (model_class_count,),
            "모델→평가 클래스 mapping 길이가 다릅니다.",
        )
        _require(
            ((score_targets >= 0) & (score_targets < score_class_count)).all(),
            "대체 평가 target이 평가 클래스 범위를 벗어났습니다.",
        )
        _require(
            ((prediction_mapping >= 0) & (prediction_mapping < score_class_count)).all(),
            "모델→평가 클래스 mapping 값이 평가 클래스 범위를 벗어났습니다.",
        )

    trained_rounds = int(model.get_booster().num_boosted_rounds())
    _require(trained_rounds > 0, "학습된 boosting round가 없습니다.")
    if candidate_iterations is None:
        iterations = tuple(range(trained_rounds))
    else:
        iterations = tuple(sorted(set(int(value) for value in candidate_iterations)))
        _require(len(iterations) > 0, "candidate iteration이 비어 있습니다.")
        _require(
            iterations[0] >= 0 and iterations[-1] < trained_rounds,
            "candidate iteration이 학습된 boosting round 범위를 벗어났습니다.",
        )

    records: list[dict[str, float | int]] = []
    for iteration in iterations:
        probabilities = predict_xgboost_at_iteration(
            model, validation_features, iteration, class_count=model_class_count
        )
        model_predictions = probabilities.argmax(axis=1)
        predictions = (
            prediction_mapping[model_predictions]
            if prediction_mapping is not None
            else model_predictions
        )
        records.append(
            {
                "iteration": iteration,
                "macro_f1": float(
                    f1_score(
                        score_targets,
                        predictions,
                        labels=np.arange(score_class_count),
                        average="macro",
                        zero_division=0,
                    )
                ),
                "log_loss": float(
                    log_loss(targets, probabilities, labels=np.arange(model_class_count))
                ),
            }
        )

    macro_best = select_macro_f1_iteration(records)
    _require(
        selection_policy
        in {"macro_f1_validation", "macro_f1_rolling_median_validation"},
        f"지원하지 않는 checkpoint selection policy: {selection_policy}",
    )
    rolling_median_best: dict[str, float | int] | None = None
    if selection_policy == "macro_f1_rolling_median_validation":
        _require(
            rolling_window_size is not None and minimum_iteration is not None,
            "rolling median 정책에는 window와 최소 iteration이 필요합니다.",
        )
        rolling_median_history = rolling_median_macro_f1_candidates(
            records,
            window_size=rolling_window_size,
            min_iteration=minimum_iteration,
        )
        rolling_median_best = dict(
            min(
                rolling_median_history,
                key=lambda row: (
                    -float(row["rolling_median_macro_f1"]),
                    int(row["iteration"]),
                ),
            )
        )
        selected_checkpoint = rolling_median_best
        tie_break = ["rolling_median_macro_f1_desc", "iteration_asc"]
    else:
        selected_checkpoint = macro_best
        tie_break = ["macro_f1_desc", "log_loss_asc", "iteration_asc"]
    training_best_iteration = int(model.best_iteration)
    _require(
        0 <= training_best_iteration < trained_rounds,
        "training metric best_iteration이 학습 범위를 벗어났습니다.",
    )
    by_iteration = {int(record["iteration"]): record for record in records}
    if training_best_iteration not in by_iteration:
        probabilities = predict_xgboost_at_iteration(
            model,
            validation_features,
            training_best_iteration,
            class_count=model_class_count,
        )
        training_model_predictions = probabilities.argmax(axis=1)
        training_predictions = (
            prediction_mapping[training_model_predictions]
            if prediction_mapping is not None
            else training_model_predictions
        )
        training_record: dict[str, float | int] = {
            "iteration": training_best_iteration,
            "macro_f1": float(
                f1_score(
                    score_targets,
                    training_predictions,
                    labels=np.arange(score_class_count),
                    average="macro",
                    zero_division=0,
                )
            ),
            "log_loss": float(
                log_loss(targets, probabilities, labels=np.arange(model_class_count))
            ),
        }
    else:
        training_record = dict(by_iteration[training_best_iteration])

    result = {
        "selection_scope": "outer_fold_validation_only",
        "selection_policy": selection_policy,
        "primary_metric": "macro_f1",
        "training_metric": "mlogloss",
        "model_class_count": model_class_count,
        "evaluation_class_count": score_class_count,
        "evaluation_uses_prediction_mapping": prediction_mapping is not None,
        "trained_rounds": trained_rounds,
        "tie_break": tie_break,
        "training_metric_best": training_record,
        "macro_f1_best": macro_best,
        "selected_checkpoint": selected_checkpoint,
        "macro_f1_delta": float(selected_checkpoint["macro_f1"])
        - float(training_record["macro_f1"]),
        "curve": records,
    }
    if rolling_median_best is not None:
        result["rolling_median_contract"] = {
            "window_size": rolling_window_size,
            "minimum_iteration": minimum_iteration,
            "window_alignment": "trailing_inclusive",
            "selected_iteration_is_window_end": True,
            "fallback": "fail",
        }
        result["rolling_median_best"] = rolling_median_best
        result["rolling_median_history"] = rolling_median_history
    return result
