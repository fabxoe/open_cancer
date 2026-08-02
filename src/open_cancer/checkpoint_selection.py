"""Leakage-safe validation auditing for XGBoost checkpoint iterations."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
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
) -> np.ndarray:
    """Predict with trees through one zero-based boosting iteration."""
    _require(isinstance(iteration, int) and iteration >= 0, "iteration은 0 이상의 정수여야 합니다.")
    probabilities = np.asarray(
        model.predict_proba(matrix, iteration_range=(0, iteration + 1)),
        dtype=np.float64,
    )
    _require(probabilities.ndim == 2, "XGBoost 확률은 2차원이어야 합니다.")
    _require(
        probabilities.shape[1] == len(CLASS_LABELS),
        "XGBoost 확률의 클래스 수가 고정 26개 순서와 다릅니다.",
    )
    _require(np.isfinite(probabilities).all(), "XGBoost 확률에 NaN 또는 무한대가 있습니다.")
    _require((probabilities >= 0).all(), "XGBoost 확률에 음수가 있습니다.")
    row_sums = probabilities.sum(axis=1, keepdims=True)
    _require((row_sums > 0).all(), "XGBoost 확률 행의 합이 0입니다.")
    return probabilities / row_sums


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


def audit_xgboost_validation_iterations(
    model: XGBoostIterationModel,
    validation_features: Any,
    validation_targets: np.ndarray,
    *,
    candidate_iterations: Iterable[int] | None = None,
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
        ((targets >= 0) & (targets < len(CLASS_LABELS))).all(),
        "validation target이 고정 26개 클래스 범위를 벗어났습니다.",
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
        probabilities = predict_xgboost_at_iteration(model, validation_features, iteration)
        predictions = probabilities.argmax(axis=1)
        records.append(
            {
                "iteration": iteration,
                "macro_f1": float(
                    f1_score(
                        targets,
                        predictions,
                        labels=np.arange(len(CLASS_LABELS)),
                        average="macro",
                        zero_division=0,
                    )
                ),
                "log_loss": float(
                    log_loss(targets, probabilities, labels=np.arange(len(CLASS_LABELS)))
                ),
            }
        )

    macro_best = select_macro_f1_iteration(records)
    training_best_iteration = int(model.best_iteration)
    _require(
        0 <= training_best_iteration < trained_rounds,
        "training metric best_iteration이 학습 범위를 벗어났습니다.",
    )
    by_iteration = {int(record["iteration"]): record for record in records}
    if training_best_iteration not in by_iteration:
        probabilities = predict_xgboost_at_iteration(
            model, validation_features, training_best_iteration
        )
        training_record: dict[str, float | int] = {
            "iteration": training_best_iteration,
            "macro_f1": float(
                f1_score(
                    targets,
                    probabilities.argmax(axis=1),
                    labels=np.arange(len(CLASS_LABELS)),
                    average="macro",
                    zero_division=0,
                )
            ),
            "log_loss": float(
                log_loss(targets, probabilities, labels=np.arange(len(CLASS_LABELS)))
            ),
        }
    else:
        training_record = dict(by_iteration[training_best_iteration])

    return {
        "selection_scope": "outer_fold_validation_only",
        "primary_metric": "macro_f1",
        "training_metric": "mlogloss",
        "trained_rounds": trained_rounds,
        "tie_break": ["macro_f1_desc", "log_loss_asc", "iteration_asc"],
        "training_metric_best": training_record,
        "macro_f1_best": macro_best,
        "macro_f1_delta": float(macro_best["macro_f1"]) - float(training_record["macro_f1"]),
        "curve": records,
    }
