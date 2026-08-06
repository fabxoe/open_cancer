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
from open_cancer.fold_feature_selection import (
    FoldFeatureSelection,
    FoldFeatureSelector,
    write_fold_feature_selection,
)
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


class FoldTrainResampler(Protocol):
    """Resample only the training rows for one outer CV fold."""

    def __call__(
        self,
        features: sparse.csr_matrix,
        targets: np.ndarray,
        fold: int,
    ) -> tuple[sparse.csr_matrix, np.ndarray, dict[str, Any]]: ...


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


class OneVsRestXGBoostAdapter:
    """Train one binary XGBoost classifier per fixed cancer class."""

    file_suffix = ".joblib"

    def __init__(self, parameters: dict[str, Any], seed: int) -> None:
        import xgboost as xgb

        self.xgb = xgb
        self.seed = seed
        self.binary_balanced_sample_weight = bool(
            parameters.pop("binary_balanced_sample_weight", True)
        )
        self.parameters = {
            "objective": "binary:logistic",
            "random_state": seed,
            **parameters,
        }
        self.models: list[Any] = []

    def fit(self, x_train, y_train, x_valid, y_valid, sample_weight) -> None:
        _require(
            sample_weight is None or not self.binary_balanced_sample_weight,
            "OvR binary weight와 공용 multiclass weight를 동시에 적용할 수 없습니다.",
        )
        self.models = []
        for class_index in range(len(CLASS_LABELS)):
            binary_train = (y_train == class_index).astype(np.int32)
            binary_valid = (y_valid == class_index).astype(np.int32)
            weights = (
                compute_sample_weight(class_weight="balanced", y=binary_train)
                if self.binary_balanced_sample_weight
                else sample_weight
            )
            model = self.xgb.XGBClassifier(**self.parameters)
            model.fit(
                x_train,
                binary_train,
                sample_weight=weights,
                eval_set=[(x_valid, binary_valid)],
                verbose=False,
            )
            self.models.append(model)

    def predict_proba(self, matrix) -> np.ndarray:
        _require(len(self.models) == len(CLASS_LABELS), "OvR binary model 26개가 필요합니다.")
        return np.column_stack(
            [model.predict_proba(matrix)[:, 1] for model in self.models]
        )

    def save(self, path: Path) -> None:
        import joblib

        joblib.dump({"models": self.models}, path)

    @property
    def best_iteration(self) -> int | None:
        iterations = []
        for model in self.models:
            try:
                iterations.append(int(model.best_iteration))
            except (AttributeError, ValueError):
                continue
        return max(iterations) if iterations else None


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
        self.checkpoint_selection = str(
            parameters.pop("checkpoint_selection", "log_loss_validation")
        )
        _require(
            self.checkpoint_selection
            in {"log_loss_validation", "macro_f1_validation"},
            "지원하지 않는 LightGBM checkpoint 선택 정책입니다: "
            f"{self.checkpoint_selection}",
        )
        defaults = {
            "objective": "multiclass",
            "num_class": len(CLASS_LABELS),
            "random_state": seed,
        }
        if self.checkpoint_selection == "macro_f1_validation":
            # Disable LightGBM's default multi_logloss so early stopping sees
            # only the competition-aligned custom metric below.
            defaults["metric"] = "None"
        self.model = lgb.LGBMClassifier(**{**defaults, **parameters})

    def fit(self, x_train, y_train, x_valid, y_valid, sample_weight) -> None:
        fit_options: dict[str, Any] = {}
        if self.checkpoint_selection == "macro_f1_validation":
            fit_options["eval_metric"] = lightgbm_macro_f1_metric
        self.model.fit(
            x_train,
            y_train,
            sample_weight=sample_weight,
            eval_X=x_valid,
            eval_y=y_valid,
            callbacks=[
                self.lgb.early_stopping(
                    self.early_stopping_rounds,
                    first_metric_only=self.checkpoint_selection
                    == "macro_f1_validation",
                    verbose=False,
                )
            ],
            **fit_options,
        )

    def predict_proba(self, matrix) -> np.ndarray:
        return self.model.predict_proba(matrix)

    def save(self, path: Path) -> None:
        self.model.booster_.save_model(str(path))

    @property
    def best_iteration(self) -> int | None:
        value = getattr(self.model, "best_iteration_", None)
        return None if value is None else int(value)


def lightgbm_macro_f1_metric(
    targets: np.ndarray,
    probabilities: np.ndarray,
) -> tuple[str, float, bool]:
    """Competition-aligned LightGBM validation metric (higher is better)."""

    target_array = np.asarray(targets, dtype=np.int32)
    probability_array = np.asarray(probabilities)
    if probability_array.ndim == 1:
        _require(
            probability_array.size % target_array.size == 0,
            "LightGBM 예측 확률을 행 단위로 복원할 수 없습니다.",
        )
        probability_array = probability_array.reshape(target_array.size, -1)
    _require(
        probability_array.shape
        == (target_array.size, len(CLASS_LABELS)),
        "LightGBM Macro F1 확률 shape가 26-class 계약과 다릅니다.",
    )
    predictions = probability_array.argmax(axis=1)
    return (
        "macro_f1",
        float(f1_score(target_array, predictions, average="macro", zero_division=0)),
        True,
    )


class RandomForestAdapter:
    """Bagged decision-tree ensemble, structurally distinct from boosting adapters."""

    file_suffix = ".joblib"

    def __init__(self, parameters: dict[str, Any], seed: int) -> None:
        from sklearn.ensemble import RandomForestClassifier

        defaults = {"n_estimators": 500, "n_jobs": 8}
        self.model = RandomForestClassifier(random_state=seed, **{**defaults, **parameters})

    def fit(self, x_train, y_train, x_valid, y_valid, sample_weight) -> None:
        del x_valid, y_valid
        self.model.fit(x_train, y_train, sample_weight=sample_weight)

    def predict_proba(self, matrix) -> np.ndarray:
        raw = self.model.predict_proba(matrix)
        output = np.zeros((matrix.shape[0], len(CLASS_LABELS)), dtype=np.float64)
        output[:, self.model.classes_.astype(int)] = raw
        return output

    def save(self, path: Path) -> None:
        import joblib

        joblib.dump(self.model, path)

    @property
    def best_iteration(self) -> None:
        return None


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
        "ovr_xgboost": OneVsRestXGBoostAdapter,
        "lightgbm": LightGBMAdapter,
        "catboost": CatBoostAdapter,
        "random_forest": RandomForestAdapter,
    }
    _require(name in factories, f"지원하지 않는 모델입니다: {name}")
    return factories[name](dict(parameters), seed)


@dataclass(frozen=True)
class CrossValidationOutput:
    oof_probabilities: np.ndarray
    test_probabilities: np.ndarray
    fold_metrics: tuple[dict[str, Any], ...]
    model_paths: tuple[Path, ...]
    feature_selection_paths: tuple[Path | None, ...]


def _validated_fold_selection_indices(
    selection: FoldFeatureSelection,
    *,
    feature_count: int,
) -> np.ndarray:
    """Validate one selector mask before it reaches model training."""
    selected_indices = np.asarray(selection.selected_indices, dtype=np.int64)
    _require(len(selected_indices) > 0, "fold feature selector가 빈 feature mask를 반환했습니다.")
    _require(
        np.array_equal(selected_indices, np.unique(selected_indices))
        and np.array_equal(selected_indices, np.sort(selected_indices))
        and selected_indices[0] >= 0
        and selected_indices[-1] < feature_count,
        "fold feature selector의 index 계약이 잘못되었습니다.",
    )
    return selected_indices


def fit_fold_feature_selections(
    *,
    train_features: sparse.csr_matrix,
    targets: np.ndarray,
    folds: np.ndarray,
    feature_names: Sequence[str],
    fold_feature_selector: FoldFeatureSelector,
) -> tuple[FoldFeatureSelection, ...]:
    """Fit all fold-local masks before any model training begins."""
    _require(train_features.shape[1] == len(feature_names), "feature 이름 수가 matrix와 다릅니다.")
    _require(set(np.unique(folds)) == set(range(5)), "canonical fold는 0..4여야 합니다.")
    selections: list[FoldFeatureSelection] = []
    for fold in range(5):
        selection = fold_feature_selector.select(
            train_features[folds != fold],
            targets[folds != fold],
            feature_names,
            fold,
        )
        _validated_fold_selection_indices(selection, feature_count=train_features.shape[1])
        selections.append(selection)
    return tuple(selections)


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
    fold_train_resampler: FoldTrainResampler | None = None,
    feature_names: Sequence[str] | None = None,
    fold_feature_selector: FoldFeatureSelector | None = None,
    prepared_fold_feature_selections: Sequence[FoldFeatureSelection] | None = None,
) -> CrossValidationOutput:
    """Train five aligned folds and return canonical OOF/test probabilities.

    A feature selector fits on raw outer-training rows only, then the exact
    selected mask is applied to train, validation, and test.  A resampler runs
    afterwards and receives only selected outer-training rows.  Neither may
    inspect validation or test rows during fitting. Resampling and
    class-balanced sample weights are mutually exclusive so minority examples
    are not double-counted.
    """
    _require(train_features.shape[0] == len(targets) == len(folds), "train 행 계약 불일치")
    _require(train_features.shape[1] == test_features.shape[1], "train/test feature 차원 불일치")
    _require(
        fold_feature_selector is None
        or (feature_names is not None and len(feature_names) == train_features.shape[1]),
        "fold feature selector에는 전체 feature 이름과 동일한 순서가 필요합니다.",
    )
    _require(
        prepared_fold_feature_selections is None
        or (feature_names is not None and len(feature_names) == train_features.shape[1]),
        "사전 계산한 feature selection에는 전체 feature 이름과 동일한 순서가 필요합니다.",
    )
    _require(
        not (fold_feature_selector is not None and prepared_fold_feature_selections is not None),
        "selector를 실행하거나 사전 계산한 selection을 전달해야 합니다. 둘을 함께 전달할 수 없습니다.",
    )
    _require(
        prepared_fold_feature_selections is None or len(prepared_fold_feature_selections) == 5,
        "사전 계산한 feature selection은 canonical 5개 fold가 필요합니다.",
    )
    _require(set(np.unique(folds)) == set(range(5)), "canonical fold는 0..4여야 합니다.")
    _require(set(np.unique(targets)) == set(range(len(CLASS_LABELS))), "고정 26개 class index가 필요합니다.")
    _require(
        not (balanced_sample_weight and fold_train_resampler is not None),
        "resampling과 balanced_sample_weight를 동시에 적용할 수 없습니다.",
    )
    model_dir.mkdir(parents=True, exist_ok=True)
    oof = np.full((len(targets), len(CLASS_LABELS)), np.nan, dtype=np.float64)
    test = np.zeros((test_features.shape[0], len(CLASS_LABELS)), dtype=np.float64)
    fold_metrics = []
    paths = []
    selection_paths: list[Path | None] = []
    for fold in range(5):
        valid = folds == fold
        train = ~valid
        adapter = adapter_factory(fold)
        fit_features = train_features[train]
        fit_targets = targets[train]
        valid_features = train_features[valid]
        selected_test_features = test_features
        selection: FoldFeatureSelection | None = None
        selection_path: Path | None = None
        if prepared_fold_feature_selections is not None:
            selection = prepared_fold_feature_selections[fold]
        elif fold_feature_selector is not None:
            selection = fold_feature_selector.select(
                fit_features,
                fit_targets,
                feature_names or (),
                fold,
            )
        if selection is not None:
            selected_indices = _validated_fold_selection_indices(
                selection,
                feature_count=train_features.shape[1],
            )
            fit_features = fit_features[:, selected_indices]
            valid_features = valid_features[:, selected_indices]
            selected_test_features = test_features[:, selected_indices]
            selection_path = write_fold_feature_selection(
                selection=selection,
                feature_names=feature_names or (),
                path=model_dir / f"fold_{fold:02d}_feature_selection.json",
            )
        resampling: dict[str, Any] | None = None
        if fold_train_resampler is not None:
            fit_features, fit_targets, resampling = fold_train_resampler(
                fit_features,
                fit_targets,
                fold,
            )
            _require(
                sparse.isspmatrix_csr(fit_features),
                "resampling 결과 feature는 CSR sparse matrix여야 합니다.",
            )
            _require(
                fit_features.shape[1] == valid_features.shape[1]
                and fit_features.shape[0] == len(fit_targets),
                "resampling 결과 feature/target 계약 불일치",
            )
        weights = (
            compute_sample_weight(class_weight="balanced", y=fit_targets)
            if balanced_sample_weight
            else None
        )
        adapter.fit(
            fit_features,
            fit_targets,
            valid_features,
            targets[valid],
            weights,
        )
        valid_probability = _validate_probabilities(
            adapter.predict_proba(valid_features),
            int(valid.sum()),
        )
        test_probability = _validate_probabilities(
            adapter.predict_proba(selected_test_features), test_features.shape[0]
        )
        oof[valid] = valid_probability
        test += test_probability / 5
        prediction = valid_probability.argmax(axis=1)
        fold_metric = {
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
        if resampling is not None:
            fold_metric["resampling"] = resampling
        if selection is not None:
            fold_metric["feature_selection"] = selection.metadata
        fold_metrics.append(fold_metric)
        path = model_dir / f"fold_{fold:02d}{adapter.file_suffix}"
        adapter.save(path)
        paths.append(path)
        selection_paths.append(selection_path)
    _require(not np.isnan(oof).any(), "OOF 확률이 완성되지 않았습니다.")
    return CrossValidationOutput(oof, test, tuple(fold_metrics), tuple(paths), tuple(selection_paths))
