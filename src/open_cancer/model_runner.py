"""Shared model adapters and canonical cross-validation engine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol, Sequence

import numpy as np
from scipy import sparse
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, log_loss
from sklearn.preprocessing import MaxAbsScaler
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.constants import CLASS_LABELS
from open_cancer.model_artifacts import (
    build_oof_probability_frame,
    build_test_probability_frame,
)


class ModelRunnerError(ValueError):
    """Raised when a model or matrix violates the common runner contract."""


class OptionalModelDependencyError(ImportError):
    """Raised when an experiment-only model library is not installed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ModelRunnerError(message)


class ModelAdapter(Protocol):
    file_suffix: str

    def fit(self, x_train, y_train, x_valid, y_valid, sample_weight) -> None: ...
    def predict_proba(self, matrix) -> np.ndarray: ...
    def save(self, path: Path) -> None: ...


class LogisticRegressionAdapter:
    file_suffix = ".joblib"

    def __init__(self, parameters: dict[str, Any], seed: int) -> None:
        scale = parameters.pop("scale", "none")
        _require(scale in {"none", "max_abs"}, f"지원하지 않는 Logistic scaling: {scale}")
        self.scaler = MaxAbsScaler() if scale == "max_abs" else None
        defaults = {"solver": "saga", "C": 1.0, "max_iter": 2000}
        self.model = LogisticRegression(random_state=seed, **{**defaults, **parameters})

    def fit(self, x_train, y_train, x_valid, y_valid, sample_weight) -> None:
        del x_valid, y_valid
        if self.scaler is not None:
            x_train = self.scaler.fit_transform(x_train)
        self.model.fit(x_train, y_train, sample_weight=sample_weight)

    def predict_proba(self, matrix) -> np.ndarray:
        if self.scaler is not None:
            matrix = self.scaler.transform(matrix)
        raw = self.model.predict_proba(matrix)
        output = np.zeros((matrix.shape[0], len(CLASS_LABELS)), dtype=np.float64)
        output[:, self.model.classes_.astype(int)] = raw
        return output

    def save(self, path: Path) -> None:
        import joblib

        joblib.dump({"model": self.model, "scaler": self.scaler}, path)

    @property
    def best_iteration(self) -> None:
        return None


class XGBoostAdapter:
    file_suffix = ".json"

    def __init__(self, parameters: dict[str, Any], seed: int) -> None:
        import xgboost as xgb

        defaults = {
            "objective": "multi:softprob",
            "num_class": len(CLASS_LABELS),
            "random_state": seed,
        }
        self.model = xgb.XGBClassifier(**{**defaults, **parameters})

    def fit(self, x_train, y_train, x_valid, y_valid, sample_weight) -> None:
        self.model.fit(
            x_train,
            y_train,
            sample_weight=sample_weight,
            eval_set=[(x_valid, y_valid)],
            verbose=False,
        )

    def predict_proba(self, matrix) -> np.ndarray:
        return self.model.predict_proba(matrix)

    def save(self, path: Path) -> None:
        self.model.save_model(path)

    @property
    def best_iteration(self) -> int | None:
        try:
            return int(self.model.best_iteration)
        except (AttributeError, ValueError):
            return None


class LightGBMAdapter:
    file_suffix = ".txt"

    def __init__(self, parameters: dict[str, Any], seed: int) -> None:
        try:
            import lightgbm as lgb
        except ImportError as error:
            raise OptionalModelDependencyError(
                "LightGBM 실험 전 `uv sync --frozen --group experiment`를 실행하세요."
            ) from error
        self.lgb = lgb
        self.early_stopping_rounds = int(parameters.pop("early_stopping_rounds", 50))
        defaults = {
            "objective": "multiclass",
            "num_class": len(CLASS_LABELS),
            "random_state": seed,
        }
        self.model = lgb.LGBMClassifier(**{**defaults, **parameters})

    def fit(self, x_train, y_train, x_valid, y_valid, sample_weight) -> None:
        self.model.fit(
            x_train,
            y_train,
            sample_weight=sample_weight,
            eval_X=x_valid,
            eval_y=y_valid,
            callbacks=[self.lgb.early_stopping(self.early_stopping_rounds, verbose=False)],
        )

    def predict_proba(self, matrix) -> np.ndarray:
        return self.model.predict_proba(matrix)

    def save(self, path: Path) -> None:
        self.model.booster_.save_model(str(path))

    @property
    def best_iteration(self) -> int | None:
        value = getattr(self.model, "best_iteration_", None)
        return None if value is None else int(value)


class CatBoostAdapter:
    file_suffix = ".cbm"

    def __init__(self, parameters: dict[str, Any], seed: int) -> None:
        try:
            from catboost import CatBoostClassifier
        except ImportError as error:
            raise OptionalModelDependencyError(
                "CatBoost 실험 전 `uv sync --frozen --group experiment`를 실행하세요."
            ) from error
        self.early_stopping_rounds = int(parameters.pop("early_stopping_rounds", 50))
        defaults = {"loss_function": "MultiClass", "random_seed": seed, "verbose": False}
        self.model = CatBoostClassifier(**{**defaults, **parameters})

    def fit(self, x_train, y_train, x_valid, y_valid, sample_weight) -> None:
        self.model.fit(
            x_train,
            y_train,
            sample_weight=sample_weight,
            eval_set=(x_valid, y_valid),
            early_stopping_rounds=self.early_stopping_rounds,
            verbose=False,
        )

    def predict_proba(self, matrix) -> np.ndarray:
        return self.model.predict_proba(matrix)

    def save(self, path: Path) -> None:
        self.model.save_model(str(path))

    @property
    def best_iteration(self) -> int | None:
        value = int(self.model.get_best_iteration())
        return None if value < 0 else value


def create_model_adapter(name: str, parameters: dict[str, Any], seed: int) -> ModelAdapter:
    """Create one adapter without importing optional libraries unnecessarily."""
    factories = {
        "logistic_regression": LogisticRegressionAdapter,
        "xgboost": XGBoostAdapter,
        "lightgbm": LightGBMAdapter,
        "catboost": CatBoostAdapter,
    }
    _require(name in factories, f"지원하지 않는 모델입니다: {name}")
    return factories[name](dict(parameters), seed)


@dataclass(frozen=True)
class CrossValidationOutput:
    oof_probabilities: np.ndarray
    test_probabilities: np.ndarray
    fold_metrics: tuple[dict[str, Any], ...]
    model_paths: tuple[Path, ...]


@dataclass(frozen=True)
class WrittenCrossValidationArtifacts:
    oof_probabilities: Path
    test_probabilities: Path
    metrics: Path


def write_cross_validation_artifacts(
    *,
    output: CrossValidationOutput,
    train_ids: Sequence[str],
    true_labels: Sequence[str],
    folds: Sequence[int],
    test_ids: Sequence[str],
    output_dir: Path,
) -> WrittenCrossValidationArtifacts:
    """Write canonical probability CSVs and score records from one completed run."""
    oof_frame = build_oof_probability_frame(
        ids=train_ids,
        true_labels=true_labels,
        folds=folds,
        probabilities=output.oof_probabilities,
    )
    test_frame = build_test_probability_frame(
        ids=test_ids,
        probabilities=output.test_probabilities,
    )
    true_indices = np.asarray([CLASS_LABELS.index(label) for label in true_labels])
    predicted_indices = output.oof_probabilities.argmax(axis=1)
    metrics_document = {
        "metric": "macro_f1",
        "oof_macro_f1": float(f1_score(true_indices, predicted_indices, average="macro")),
        "oof_accuracy": float(accuracy_score(true_indices, predicted_indices)),
        "oof_log_loss": float(
            log_loss(
                true_indices,
                output.oof_probabilities,
                labels=np.arange(len(CLASS_LABELS)),
            )
        ),
        "folds": list(output.fold_metrics),
        "class_order": list(CLASS_LABELS),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    oof_path = output_dir / "oof_predictions.csv"
    test_path = output_dir / "test_probabilities.csv"
    metrics_path = output_dir / "metrics.json"
    oof_frame.to_csv(oof_path, index=False)
    test_frame.to_csv(test_path, index=False)
    metrics_path.write_text(
        json.dumps(metrics_document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return WrittenCrossValidationArtifacts(oof_path, test_path, metrics_path)


def _validate_probabilities(values: np.ndarray, rows: int) -> np.ndarray:
    matrix = np.asarray(values, dtype=np.float64)
    _require(matrix.shape == (rows, len(CLASS_LABELS)), "모델 확률 shape가 (rows, 26)이 아닙니다.")
    _require(np.isfinite(matrix).all(), "모델 확률에 NaN 또는 무한대가 있습니다.")
    _require(((matrix >= 0) & (matrix <= 1)).all(), "모델 확률 범위가 [0, 1]이 아닙니다.")
    row_sums = matrix.sum(axis=1, keepdims=True)
    _require((row_sums > 0).all(), "모델 확률 행의 합이 0입니다.")
    matrix = matrix / row_sums
    return matrix


def run_canonical_cv(
    *,
    train_features: sparse.csr_matrix,
    test_features: sparse.csr_matrix,
    targets: np.ndarray,
    folds: np.ndarray,
    adapter_factory: Callable[[int], ModelAdapter],
    model_dir: Path,
    balanced_sample_weight: bool = True,
) -> CrossValidationOutput:
    """Train five aligned folds and return canonical OOF/test probabilities."""
    _require(train_features.shape[0] == len(targets) == len(folds), "train 행 계약 불일치")
    _require(train_features.shape[1] == test_features.shape[1], "train/test feature 차원 불일치")
    _require(set(np.unique(folds)) == set(range(5)), "canonical fold는 0..4여야 합니다.")
    _require(set(np.unique(targets)) == set(range(len(CLASS_LABELS))), "고정 26개 class index가 필요합니다.")
    model_dir.mkdir(parents=True, exist_ok=True)
    oof = np.full((len(targets), len(CLASS_LABELS)), np.nan, dtype=np.float64)
    test = np.zeros((test_features.shape[0], len(CLASS_LABELS)), dtype=np.float64)
    fold_metrics = []
    paths = []
    for fold in range(5):
        valid = folds == fold
        train = ~valid
        adapter = adapter_factory(fold)
        weights = (
            compute_sample_weight(class_weight="balanced", y=targets[train])
            if balanced_sample_weight
            else None
        )
        adapter.fit(
            train_features[train],
            targets[train],
            train_features[valid],
            targets[valid],
            weights,
        )
        valid_probability = _validate_probabilities(
            adapter.predict_proba(train_features[valid]),
            int(valid.sum()),
        )
        test_probability = _validate_probabilities(adapter.predict_proba(test_features), test_features.shape[0])
        oof[valid] = valid_probability
        test += test_probability / 5
        prediction = valid_probability.argmax(axis=1)
        fold_metrics.append(
            {
                "fold": fold,
                "macro_f1": float(f1_score(targets[valid], prediction, average="macro")),
                "accuracy": float(accuracy_score(targets[valid], prediction)),
                "log_loss": float(
                    log_loss(
                        targets[valid],
                        valid_probability,
                        labels=np.arange(len(CLASS_LABELS)),
                    )
                ),
                "best_iteration": getattr(adapter, "best_iteration", None),
            }
        )
        path = model_dir / f"fold_{fold:02d}{adapter.file_suffix}"
        adapter.save(path)
        paths.append(path)
    _require(not np.isnan(oof).any(), "OOF 확률이 완성되지 않았습니다.")
    return CrossValidationOutput(oof, test, tuple(fold_metrics), tuple(paths))
