from __future__ import annotations

import numpy as np
import pandas as pd

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.portfolio_audit import (
    audit_test_probability,
    expected_calibration_error,
    pairwise_metrics,
)


def test_expected_calibration_error_is_zero_for_perfect_confidence() -> None:
    probabilities = np.zeros((2, len(CLASS_LABELS)), dtype=float)
    probabilities[0, 0] = 1.0
    probabilities[1, 1] = 1.0
    assert expected_calibration_error(probabilities, np.array([0, 1])) == 0.0


def test_pairwise_metrics_detect_identical_predictions(tmp_path) -> None:
    from open_cancer.portfolio_audit import load_and_audit_oof

    rows = []
    for index in range(6201):
        true = CLASS_LABELS[index % len(CLASS_LABELS)]
        row = {
            "ID": f"T{index}",
            "SUBCLASS_TRUE": true,
            "SUBCLASS_PRED": true,
            "FOLD": index % 5,
        }
        row.update({column: 0.0 for column in PROBABILITY_COLUMNS})
        row[f"PROBA_{true}"] = 1.0
        rows.append(row)
    path = tmp_path / "oof.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    left = load_and_audit_oof("LEFT", path)
    right = load_and_audit_oof("RIGHT", path)
    metrics = pairwise_metrics(left, right)
    assert metrics["label_agreement"] == 1.0
    assert metrics["correctness_pearson"] == 1.0
    assert metrics["probability_pearson"] == 1.0


def test_test_probability_contract_records_shape_and_hash(tmp_path) -> None:
    frame = pd.DataFrame({"ID": [f"S{index}" for index in range(2546)]})
    for column in PROBABILITY_COLUMNS:
        frame[column] = 0.0
    frame[PROBABILITY_COLUMNS[0]] = 1.0
    path = tmp_path / "test.csv"
    frame.to_csv(path, index=False)
    ids, record = audit_test_probability("TEST", path)
    assert len(ids) == 2546
    assert record["shape"] == [2546, 26]
    assert len(record["sha256"]) == 64
