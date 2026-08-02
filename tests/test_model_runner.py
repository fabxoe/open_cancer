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
    fit_fold_feature_selections,
    run_canonical_cv,
    write_cross_validation_artifacts,
)
from open_cancer.fold_feature_selection import FoldFeatureSelection
from open_cancer.resampling import FoldLocalSmote


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


class RecordingAdapter(DummyAdapter):
    def __init__(self) -> None:
        self.fit_rows: list[tuple[int, int, int]] = []
        self.valid_matrices: list[sparse.csr_matrix] = []
        self.prediction_matrices: list[sparse.csr_matrix] = []

    def fit(self, x_train, y_train, x_valid, y_valid, sample_weight) -> None:
        self.fit_rows.append((x_train.shape[0], x_valid.shape[0], len(y_valid)))
        self.valid_matrices.append(x_valid.copy())
        assert sample_weight is None

    def predict_proba(self, matrix) -> np.ndarray:
        self.prediction_matrices.append(matrix.copy())
        return super().predict_proba(matrix)


class FirstTwoFeatureSelector:
    def __init__(self) -> None:
        self.fit_shapes: list[tuple[int, int]] = []

    def select(self, features, targets, feature_names, fold) -> FoldFeatureSelection:
        del targets
        self.fit_shapes.append(features.shape)
        return FoldFeatureSelection(
            selected_indices=(0, 1),
            metadata={"selector": "test_selector", "fold": fold, "feature_names": list(feature_names)},
        )


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


def test_logistic_adapter_rejects_unknown_scaling() -> None:
    with pytest.raises(ModelRunnerError, match="Logistic scaling"):
        create_model_adapter("logistic_regression", {"scale": "standard"}, 42)


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


def test_fold_local_smote_only_changes_training_rows(tmp_path) -> None:
    per_fold = np.array([30, 10, 8, 7, 6] + [6] * 21, dtype=int)
    targets = np.concatenate(
        [np.full(count, class_index, dtype=np.int32) for class_index, count in enumerate(per_fold)]
    )
    folds = np.arange(len(targets), dtype=np.int32) % 5
    features = sparse.csr_matrix(np.eye(len(targets), 16, dtype=np.float32))
    test = sparse.csr_matrix(np.ones((9, 16), dtype=np.float32))
    adapters: list[RecordingAdapter] = []

    def adapter_factory(fold: int) -> RecordingAdapter:
        del fold
        adapter = RecordingAdapter()
        adapters.append(adapter)
        return adapter

    result = run_canonical_cv(
        train_features=features,
        test_features=test,
        targets=targets,
        folds=folds,
        adapter_factory=adapter_factory,
        model_dir=tmp_path,
        balanced_sample_weight=False,
        fold_train_resampler=FoldLocalSmote(k_neighbors=2, base_seed=42),
    )

    assert result.oof_probabilities.shape == (len(targets), len(CLASS_LABELS))
    assert result.test_probabilities.shape == (9, len(CLASS_LABELS))
    for fold, adapter in enumerate(adapters):
        fit_rows, valid_rows, y_valid_rows = adapter.fit_rows[0]
        assert valid_rows == int((folds == fold).sum()) == y_valid_rows
        assert fit_rows > len(targets) - valid_rows
        assert (adapter.valid_matrices[0] != features[folds == fold]).nnz == 0
        assert (adapter.prediction_matrices[1] != test).nnz == 0
        audit = result.fold_metrics[fold]["resampling"]
        assert audit["input_rows"] == len(targets) - valid_rows
        assert audit["output_rows"] == fit_rows
        assert audit["random_state"] == 42 + fold


def test_resampling_and_balanced_weight_are_mutually_exclusive(tmp_path) -> None:
    targets = np.tile(np.arange(len(CLASS_LABELS)), 5)
    folds = np.repeat(np.arange(5), len(CLASS_LABELS))
    train = sparse.csr_matrix(np.ones((len(targets), 3), dtype=np.float32))
    with pytest.raises(ModelRunnerError, match="동시에"):
        run_canonical_cv(
            train_features=train,
            test_features=train[:3],
            targets=targets,
            folds=folds,
            adapter_factory=lambda fold: DummyAdapter(),
            model_dir=tmp_path,
            fold_train_resampler=FoldLocalSmote(),
        )


def test_feature_selector_is_fit_on_outer_train_and_mask_is_saved(tmp_path) -> None:
    targets = np.tile(np.arange(len(CLASS_LABELS)), 5)
    folds = np.repeat(np.arange(5), len(CLASS_LABELS))
    train = sparse.csr_matrix(np.ones((len(targets), 4), dtype=np.float32))
    test = sparse.csr_matrix(np.ones((7, 4), dtype=np.float32))
    adapters: list[RecordingAdapter] = []
    selector = FirstTwoFeatureSelector()

    def adapter_factory(fold: int) -> RecordingAdapter:
        del fold
        adapter = RecordingAdapter()
        adapters.append(adapter)
        return adapter

    result = run_canonical_cv(
        train_features=train,
        test_features=test,
        targets=targets,
        folds=folds,
        adapter_factory=adapter_factory,
        model_dir=tmp_path,
        balanced_sample_weight=False,
        feature_names=["A__mutated", "B__mutated", "A__missense", "sample__count"],
        fold_feature_selector=selector,
    )

    assert selector.fit_shapes == [(104, 4)] * 5
    assert [path is not None and path.is_file() for path in result.feature_selection_paths] == [True] * 5
    assert all(adapter.fit_rows[0][0] == 104 for adapter in adapters)
    assert all(adapter.valid_matrices[0].shape[1] == 2 for adapter in adapters)
    assert all(adapter.prediction_matrices[1].shape == (7, 2) for adapter in adapters)
    assert all(metric["feature_selection"]["selector"] == "test_selector" for metric in result.fold_metrics)


def test_prepared_fold_selections_are_fit_before_and_reused_for_all_training(tmp_path) -> None:
    targets = np.tile(np.arange(len(CLASS_LABELS)), 5)
    folds = np.repeat(np.arange(5), len(CLASS_LABELS))
    train = sparse.csr_matrix(np.ones((len(targets), 4), dtype=np.float32))
    test = sparse.csr_matrix(np.ones((7, 4), dtype=np.float32))
    selector = FirstTwoFeatureSelector()
    names = ["A__mutated", "B__mutated", "A__missense", "sample__count"]

    prepared = fit_fold_feature_selections(
        train_features=train,
        targets=targets,
        folds=folds,
        feature_names=names,
        fold_feature_selector=selector,
    )

    assert selector.fit_shapes == [(104, 4)] * 5
    result = run_canonical_cv(
        train_features=train,
        test_features=test,
        targets=targets,
        folds=folds,
        adapter_factory=lambda fold: DummyAdapter(),
        model_dir=tmp_path,
        balanced_sample_weight=False,
        feature_names=names,
        prepared_fold_feature_selections=prepared,
    )

    assert selector.fit_shapes == [(104, 4)] * 5
    assert [path is not None and path.is_file() for path in result.feature_selection_paths] == [True] * 5
