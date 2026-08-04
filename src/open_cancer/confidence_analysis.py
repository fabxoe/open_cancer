"""OOF-only pmax confidence analysis for multiclass cancer predictions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from sklearn.metrics import accuracy_score, f1_score, precision_score


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def evaluate_pmax_thresholds(
    *,
    targets: np.ndarray,
    probabilities: np.ndarray,
    class_labels: Sequence[str],
    thresholds: Sequence[float],
) -> dict[str, Any]:
    """Evaluate fixed confidence thresholds without selecting or fitting a model."""
    y = np.asarray(targets, dtype=np.int64)
    proba = np.asarray(probabilities, dtype=np.float64)
    labels = tuple(class_labels)
    _require(y.ndim == 1, "targets는 1차원이어야 합니다.")
    _require(
        proba.shape == (len(y), len(labels)),
        "probability shape가 (samples, classes)와 다릅니다.",
    )
    _require(np.isfinite(proba).all(), "probability에 NaN 또는 무한대가 있습니다.")
    _require(((proba >= 0.0) & (proba <= 1.0)).all(), "probability 범위가 잘못되었습니다.")
    _require(np.allclose(proba.sum(axis=1), 1.0, atol=1e-6), "probability 행 합이 1이 아닙니다.")
    _require(set(np.unique(y)).issubset(set(range(len(labels)))), "target class index가 잘못되었습니다.")

    ordered_thresholds = tuple(float(value) for value in thresholds)
    _require(
        ordered_thresholds == tuple(sorted(set(ordered_thresholds))),
        "threshold는 중복 없이 오름차순이어야 합니다.",
    )
    _require(
        all(0.0 <= value <= 1.0 for value in ordered_thresholds),
        "threshold 범위는 [0, 1]이어야 합니다.",
    )

    predictions = proba.argmax(axis=1)
    pmax = proba.max(axis=1)
    rows: list[dict[str, Any]] = []
    for threshold in ordered_thresholds:
        selected = pmax >= threshold
        count = int(selected.sum())
        row: dict[str, Any] = {
            "threshold": threshold,
            "sample_count": count,
            "coverage": float(count / len(y)),
            "true_class_support": {
                label: int(((y == index) & selected).sum())
                for index, label in enumerate(labels)
            },
            "predicted_class_support": {
                label: int(((predictions == index) & selected).sum())
                for index, label in enumerate(labels)
            },
        }
        if count == 0:
            row.update(
                {
                    "macro_f1": None,
                    "weighted_f1": None,
                    "macro_precision": None,
                    "accuracy": None,
                }
            )
        else:
            row.update(
                {
                    "macro_f1": float(
                        f1_score(y[selected], predictions[selected], average="macro", zero_division=0)
                    ),
                    "weighted_f1": float(
                        f1_score(y[selected], predictions[selected], average="weighted", zero_division=0)
                    ),
                    "macro_precision": float(
                        precision_score(
                            y[selected], predictions[selected], average="macro", zero_division=0
                        )
                    ),
                    "accuracy": float(accuracy_score(y[selected], predictions[selected])),
                }
            )
        rows.append(row)
    return {
        "definition": "pmax=max predicted class probability from canonical OOF predictions",
        "selection_scope": "analysis_only",
        "used_for_model_selection": False,
        "used_for_submission_filtering": False,
        "sample_count": len(y),
        "thresholds": rows,
    }
