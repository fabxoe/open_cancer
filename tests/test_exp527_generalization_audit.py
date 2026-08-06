from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "analyze_exp527_generalization",
    ROOT / "scripts" / "analyze_exp527_generalization.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_entropy_and_prediction_summary_are_finite() -> None:
    probability = np.asarray([[0.8, 0.2], [0.5, 0.5]], dtype=np.float64)
    values = MODULE.entropy(probability)
    summary = MODULE.prediction_summary(probability)

    assert np.isfinite(values).all()
    assert values[0] < values[1]
    assert summary["mean_max_probability"] == 0.65
    assert summary["mean_margin"] == pytest.approx(0.3)


def test_profile_distribution_sorts_by_absolute_standardized_shift() -> None:
    train = np.vstack(
        [np.linspace(0.1 + offset, 0.6 + offset, 26) for offset in (0.0, 0.1, 0.2, 0.3)]
    ).astype(np.float32)
    test = train.copy()
    test[:, 7] += 1.0

    result = MODULE.profile_distribution(train, test)

    assert result.iloc[0]["profile_class"] == MODULE.CLASS_LABELS[7]
    assert result.iloc[0]["mean_delta_test_minus_train"] > 0
    assert len(result) == len(MODULE.CLASS_LABELS)
