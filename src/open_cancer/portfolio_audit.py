"""Deterministic OOF portfolio metrics for ABC-Stack model selection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import accuracy_score, f1_score, log_loss

from open_cancer.constants import (
    CLASS_LABELS,
    EXPECTED_TEST_ROWS,
    EXPECTED_TRAIN_ROWS,
    PROBABILITY_COLUMNS,
)
from open_cancer.hashing import sha256_file


class PortfolioAuditError(ValueError):
    """Raised when an OOF artifact violates the shared prediction contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PortfolioAuditError(message)


def _safe_pearson(left: np.ndarray, right: np.ndarray) -> float:
    """Return a defined Pearson value for identical constant vectors."""
    if np.array_equal(left, right):
        return 1.0
    if np.std(left) == 0 or np.std(right) == 0:
        return 0.0
    return float(np.corrcoef(left, right)[0, 1])


@dataclass(frozen=True)
class AuditedOOF:
    experiment_id: str
    path: Path
    frame: pd.DataFrame
    probabilities: np.ndarray
    true_labels: np.ndarray
    predicted_labels: np.ndarray
    correct: np.ndarray
    metrics: dict[str, Any]


def expected_calibration_error(
    probabilities: np.ndarray,
    true_indices: np.ndarray,
    *,
    bins: int = 15,
) -> float:
    """Return top-label ECE with fixed equal-width confidence bins."""
    confidence = probabilities.max(axis=1)
    predicted = probabilities.argmax(axis=1)
    correct = predicted == true_indices
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = len(probabilities)
    ece = 0.0
    for index in range(bins):
        lower, upper = edges[index], edges[index + 1]
        mask = (confidence >= lower) & (
            confidence <= upper if index == bins - 1 else confidence < upper
        )
        if mask.any():
            ece += float(mask.mean()) * abs(
                float(correct[mask].mean()) - float(confidence[mask].mean())
            )
    _require(total > 0, "ECE를 계산할 OOF 행이 없습니다.")
    return float(ece)


def load_and_audit_oof(experiment_id: str, path: Path) -> AuditedOOF:
    """Load one canonical OOF file and recompute its core metrics."""
    frame = pd.read_csv(path)
    metadata = ["ID", "SUBCLASS_TRUE", "SUBCLASS_PRED", "FOLD"]
    expected_columns = metadata + list(PROBABILITY_COLUMNS)
    _require(list(frame.columns) == expected_columns, f"{experiment_id}: OOF 열 순서 불일치")
    _require(len(frame) == EXPECTED_TRAIN_ROWS, f"{experiment_id}: OOF 행 수 불일치")
    _require(not frame["ID"].duplicated().any(), f"{experiment_id}: ID 중복")
    _require(frame["FOLD"].isin(range(5)).all(), f"{experiment_id}: fold 범위 불일치")
    _require(set(frame["SUBCLASS_TRUE"]) <= set(CLASS_LABELS), f"{experiment_id}: 정답 클래스 불일치")
    probabilities = frame.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)
    _require(np.isfinite(probabilities).all(), f"{experiment_id}: 확률에 NaN/Inf 존재")
    _require(((probabilities >= 0) & (probabilities <= 1)).all(), f"{experiment_id}: 확률 범위 불일치")
    _require(
        np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-5, rtol=1e-5),
        f"{experiment_id}: 확률 행 합 불일치",
    )
    probabilities = probabilities / probabilities.sum(axis=1, keepdims=True)
    predicted_indices = probabilities.argmax(axis=1)
    predicted_labels = np.asarray(CLASS_LABELS)[predicted_indices]
    _require(
        np.array_equal(predicted_labels, frame["SUBCLASS_PRED"].to_numpy()),
        f"{experiment_id}: 저장 라벨과 확률 argmax 불일치",
    )
    true_labels = frame["SUBCLASS_TRUE"].to_numpy()
    true_indices = pd.Categorical(true_labels, categories=CLASS_LABELS).codes
    fold_scores = []
    for fold in range(5):
        mask = frame["FOLD"].eq(fold).to_numpy()
        fold_scores.append(
            float(f1_score(true_labels[mask], predicted_labels[mask], average="macro"))
        )
    entropy = -(probabilities * np.log(np.clip(probabilities, 1e-15, 1.0))).sum(axis=1)
    per_class = {
        label: float(
            f1_score(
                true_labels == label,
                predicted_labels == label,
                zero_division=0,
            )
        )
        for label in CLASS_LABELS
    }
    metrics = {
        "macro_f1": float(f1_score(true_labels, predicted_labels, average="macro")),
        "fold_scores": fold_scores,
        "fold_mean": float(np.mean(fold_scores)),
        "fold_std": float(np.std(fold_scores)),
        "accuracy": float(accuracy_score(true_labels, predicted_labels)),
        "log_loss": float(log_loss(true_indices, probabilities, labels=np.arange(len(CLASS_LABELS)))),
        "mean_confidence": float(probabilities.max(axis=1).mean()),
        "mean_entropy": float(entropy.mean()),
        "ece_15": expected_calibration_error(probabilities, true_indices, bins=15),
        "per_class_f1": per_class,
    }
    return AuditedOOF(
        experiment_id=experiment_id,
        path=path,
        frame=frame,
        probabilities=probabilities,
        true_labels=true_labels,
        predicted_labels=predicted_labels,
        correct=predicted_labels == true_labels,
        metrics=metrics,
    )


def audit_test_probability(
    experiment_id: str,
    path: Path,
    *,
    reference_ids: pd.Series | None = None,
) -> tuple[pd.Series, dict[str, Any]]:
    """Validate one test-probability artifact without using its distribution."""
    frame = pd.read_csv(path)
    _require(
        list(frame.columns) == ["ID", *PROBABILITY_COLUMNS],
        f"{experiment_id}: test 확률 열 순서 불일치",
    )
    _require(len(frame) == EXPECTED_TEST_ROWS, f"{experiment_id}: test 확률 행 수 불일치")
    _require(not frame["ID"].duplicated().any(), f"{experiment_id}: test ID 중복")
    if reference_ids is not None:
        _require(frame["ID"].equals(reference_ids), f"{experiment_id}: test ID 순서 불일치")
    probabilities = frame.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)
    _require(np.isfinite(probabilities).all(), f"{experiment_id}: test 확률 NaN/Inf 존재")
    _require(((probabilities >= 0) & (probabilities <= 1)).all(), f"{experiment_id}: test 확률 범위 불일치")
    _require(
        np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-5, rtol=1e-5),
        f"{experiment_id}: test 확률 행 합 불일치",
    )
    return frame["ID"], {
        "path": str(path),
        "sha256": sha256_file(path),
        "shape": [len(frame), len(PROBABILITY_COLUMNS)],
        "id_order_verified": reference_ids is not None,
        "probability_contract_verified": True,
    }


def assert_aligned(reference: AuditedOOF, candidate: AuditedOOF) -> None:
    """Require identical ID, truth, and fold metadata."""
    columns = ["ID", "SUBCLASS_TRUE", "FOLD"]
    _require(
        reference.frame.loc[:, columns].equals(candidate.frame.loc[:, columns]),
        f"{candidate.experiment_id}: 기준 OOF와 ID·정답·fold 불일치",
    )


def pairwise_metrics(left: AuditedOOF, right: AuditedOOF) -> dict[str, float]:
    """Measure prediction and probability similarity for aligned OOF files."""
    assert_aligned(left, right)
    left_correct = left.correct.astype(np.float64)
    right_correct = right.correct.astype(np.float64)
    return {
        "label_agreement": float(np.mean(left.predicted_labels == right.predicted_labels)),
        "label_disagreement": float(np.mean(left.predicted_labels != right.predicted_labels)),
        "error_state_agreement": float(np.mean(left.correct == right.correct)),
        "correctness_pearson": _safe_pearson(left_correct, right_correct),
        "probability_pearson": _safe_pearson(
            left.probabilities.ravel(), right.probabilities.ravel()
        ),
        "probability_spearman": float(
            spearmanr(left.probabilities.ravel(), right.probabilities.ravel()).statistic
        ),
    }


def audit_record(model: AuditedOOF, baseline: AuditedOOF) -> dict[str, Any]:
    """Return one serializable model record with fixed quality/diversity gates."""
    pair = pairwise_metrics(baseline, model)
    delta = model.metrics["macro_f1"] - baseline.metrics["macro_f1"]
    log_loss_delta = model.metrics["log_loss"] - baseline.metrics["log_loss"]
    quality_gate = delta >= -0.004 and log_loss_delta <= 0.01
    wildcard_gate = (
        delta >= -0.010
        and pair["label_disagreement"] >= 0.12
        and log_loss_delta <= 0.01
    )
    diversity_gate = (
        pair["correctness_pearson"] <= 0.92
        or pair["label_disagreement"] >= 0.10
    )
    per_class_delta = {
        label: model.metrics["per_class_f1"][label]
        - baseline.metrics["per_class_f1"][label]
        for label in CLASS_LABELS
    }
    return {
        "experiment_id": model.experiment_id,
        "oof_path": str(model.path),
        "oof_sha256": sha256_file(model.path),
        "metrics": model.metrics,
        "versus_exp094": {
            "macro_f1_delta": delta,
            "fold_std_delta": model.metrics["fold_std"] - baseline.metrics["fold_std"],
            "log_loss_delta": log_loss_delta,
            **pair,
            "improved_class_count": sum(value > 0 for value in per_class_delta.values()),
            "per_class_f1_delta": per_class_delta,
        },
        "gates": {
            "quality": quality_gate,
            "wildcard": wildcard_gate,
            "diversity": diversity_gate,
            "ensemble_quality_eligible": quality_gate or wildcard_gate,
        },
    }
