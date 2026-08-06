from __future__ import annotations

import numpy as np
import pytest

from open_cancer.constants import CLASS_LABELS
from open_cancer.model_runner import ModelRunnerError, lightgbm_macro_f1_metric


def test_lightgbm_macro_f1_metric_accepts_multiclass_matrix() -> None:
    targets = np.asarray([0, 1, 2], dtype=np.int32)
    probabilities = np.zeros((3, len(CLASS_LABELS)), dtype=np.float64)
    probabilities[np.arange(3), targets] = 1.0
    name, value, higher_is_better = lightgbm_macro_f1_metric(
        targets, probabilities
    )
    assert name == "macro_f1"
    assert value == 1.0
    assert higher_is_better is True


def test_lightgbm_macro_f1_metric_accepts_flat_input() -> None:
    targets = np.asarray([0, 1], dtype=np.int32)
    probabilities = np.zeros((2, len(CLASS_LABELS)), dtype=np.float64)
    probabilities[np.arange(2), targets] = 1.0
    assert lightgbm_macro_f1_metric(targets, probabilities.ravel())[1] == 1.0


def test_lightgbm_macro_f1_metric_rejects_wrong_shape() -> None:
    with pytest.raises(ModelRunnerError):
        lightgbm_macro_f1_metric(np.asarray([0, 1]), np.zeros((2, 3)))
