"""LightGBM focal-loss helpers used by controlled exploratory comparisons."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np


def reshape_multiclass_scores(
    values: np.ndarray, *, rows: int, classes: int
) -> np.ndarray:
    """Accept LightGBM's legacy flat or current 2-D multiclass layout."""

    array = np.asarray(values, dtype=np.float64)
    if array.shape == (rows, classes):
        return array
    if array.size != rows * classes:
        raise ValueError(
            f"LightGBM score shape가 {rows}x{classes} 계약과 다릅니다: {array.shape}"
        )
    return array.reshape(rows, classes, order="F")


def restore_multiclass_layout(
    values: np.ndarray, *, original: np.ndarray
) -> np.ndarray:
    """Return gradients/Hessians in the layout received from LightGBM."""

    original_array = np.asarray(original)
    if original_array.ndim == 2:
        return values
    return values.reshape(-1, order="F")


def make_sigmoid_focal_objective(
    *, alpha: float, gamma: float, num_class: int
) -> Callable:
    """Build the one-vs-rest sigmoid focal objective used by the 2024 notebook.

    The original notebook differentiates this loss numerically with
    ``scipy.misc.derivative``.  This implementation uses the analytic first and
    second derivatives, preserving the same alpha/gamma definition without the
    removed SciPy API.
    """

    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha는 0과 1 사이여야 합니다.")
    if gamma < 0.0:
        raise ValueError("gamma는 0 이상이어야 합니다.")

    def objective(predictions: np.ndarray, dataset):
        labels = np.asarray(dataset.get_label(), dtype=np.int32)
        scores = reshape_multiclass_scores(
            predictions, rows=labels.size, classes=num_class
        )
        targets = np.eye(num_class, dtype=np.float64)[labels]
        probabilities = 1.0 / (1.0 + np.exp(-np.clip(scores, -40.0, 40.0)))
        signed_target = 2.0 * targets - 1.0
        probability_true = np.where(targets == 1.0, probabilities, 1.0 - probabilities)
        probability_true = np.clip(probability_true, 1e-12, 1.0 - 1e-12)
        alpha_true = np.where(targets == 1.0, alpha, 1.0 - alpha)
        one_minus = 1.0 - probability_true

        dloss_dtrue = alpha_true * (
            gamma
            * np.power(one_minus, max(gamma - 1.0, 0.0))
            * np.log(probability_true)
            - np.power(one_minus, gamma) / probability_true
        )
        if gamma == 0.0:
            second_first_term = np.zeros_like(probability_true)
        elif gamma == 1.0:
            second_first_term = np.zeros_like(probability_true)
        else:
            second_first_term = (
                -gamma
                * (gamma - 1.0)
                * np.power(one_minus, gamma - 2.0)
                * np.log(probability_true)
            )
        d2loss_dtrue2 = alpha_true * (
            second_first_term
            + 2.0
            * gamma
            * np.power(one_minus, max(gamma - 1.0, 0.0))
            / probability_true
            + np.power(one_minus, gamma) / np.square(probability_true)
        )

        sigmoid_grad = probabilities * (1.0 - probabilities)
        dtrue_dscore = signed_target * sigmoid_grad
        d2true_dscore2 = signed_target * sigmoid_grad * (1.0 - 2.0 * probabilities)
        gradient = dloss_dtrue * dtrue_dscore
        hessian = (
            d2loss_dtrue2 * np.square(dtrue_dscore)
            + dloss_dtrue * d2true_dscore2
        )
        hessian = np.maximum(hessian, 1e-8)
        return (
            restore_multiclass_layout(gradient, original=predictions),
            restore_multiclass_layout(hessian, original=predictions),
        )

    return objective


def softmax(values: np.ndarray) -> np.ndarray:
    shifted = np.asarray(values, dtype=np.float64)
    shifted = shifted - shifted.max(axis=1, keepdims=True)
    exponentiated = np.exp(shifted)
    return exponentiated / exponentiated.sum(axis=1, keepdims=True)
