from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from scipy import sparse

from open_cancer.constants import CLASS_LABELS
from open_cancer.model_runner import (
    ModelRunnerError,
    _validate_probabilities,
    create_model_adapter,
    run_canonical_cv,
    write_cross_validation_artifacts,
)


class DummyAdapter:
    file_suffix = ".txt"

    def fit(self, x_train, y_train, x_valid, y_valid, sample_weight) -> None:
        del x_train, y_train, x_valid, y_valid, sample_weight

    def predict_proba(self, matrix) -> np.ndarray:
        return np.full(
            (matrix.shape[0], len(CLASS_LABELS)),
            1 / len(CLASS_LABELS),
            dtype=np.float64,
        )

    def save(self, path: Path) -> None:
        path.write_text("dummy\n", encoding="utf-8")


def test_common_runner_produces_canonical_shapes(tmp_path) -> None:
    targets = np.tile(np.arange(len(CLASS_LABELS)), 5)
    folds = np.repeat(np.arange(5), len(CLASS_LABELS))
    train = sparse.csr_matrix(np.ones((len(targets), 3), dtype=np.float32))
    test = sparse.csr_matrix(np.ones((7, 3), dtype=np.float32))
    result = run_canonical_cv(
        train_features=train,
        test_features=test,
        targets=targets,
        folds=folds,
        adapter_factory=lambda fold: DummyAdapter(),
        model_dir=tmp_path,
    )
    assert result.oof_probabilities.shape == (130, 26)
    assert result.test_probabilities.shape == (7, 26)
    assert len(result.fold_metrics) == 5
    assert len(result.model_paths) == 5


def test_unknown_model_adapter_is_rejected() -> None:
    with pytest.raises(ModelRunnerError, match="지원하지 않는"):
        create_model_adapter("unknown", {}, 42)


def test_zero_probability_row_is_rejected() -> None:
    values = np.zeros((1, len(CLASS_LABELS)), dtype=np.float64)
    with pytest.raises(ModelRunnerError, match="합이 0"):
        _validate_probabilities(values, 1)


def test_common_runner_writes_canonical_artifacts(tmp_path) -> None:
    targets = np.tile(np.arange(len(CLASS_LABELS)), 5)
    folds = np.repeat(np.arange(5), len(CLASS_LABELS))
    train = sparse.csr_matrix(np.ones((len(targets), 3), dtype=np.float32))
    test = sparse.csr_matrix(np.ones((7, 3), dtype=np.float32))
    result = run_canonical_cv(
        train_features=train,
        test_features=test,
        targets=targets,
        folds=folds,
        adapter_factory=lambda fold: DummyAdapter(),
        model_dir=tmp_path / "models",
    )
    paths = write_cross_validation_artifacts(
        output=result,
        train_ids=[f"TRAIN_{index}" for index in range(len(targets))],
        true_labels=[CLASS_LABELS[index] for index in targets],
        folds=folds,
        test_ids=[f"TEST_{index}" for index in range(7)],
        output_dir=tmp_path / "predictions",
    )
    assert paths.oof_probabilities.is_file()
    assert paths.test_probabilities.is_file()
    assert paths.metrics.is_file()
