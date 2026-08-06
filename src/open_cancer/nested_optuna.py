"""Leakage-safe nested Optuna tuning for one outer XGBoost fold."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import xgboost as xgb
from scipy import sparse
from sklearn.model_selection import StratifiedKFold
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.checkpoint_selection import (
    audit_xgboost_validation_iterations,
)
from open_cancer.constants import CLASS_LABELS


DEFAULT_XGBOOST_SEARCH_SPACE: dict[str, list[Any]] = {
    "max_depth": [4, 8],
    "min_child_weight": [1.0, 10.0],
    "subsample": [0.5, 0.9],
    "colsample_bytree": [0.5, 0.9],
    "reg_alpha": [0.0, 1.0],
    "reg_lambda": [0.5, 5.0],
    "learning_rate": [0.02, 0.08, "log"],
}


class TrialLike(Protocol):
    number: int

    def suggest_int(self, name: str, low: int, high: int) -> int: ...

    def suggest_float(
        self, name: str, low: float, high: float, *, log: bool = False
    ) -> float: ...

    def set_user_attr(self, key: str, value: Any) -> None: ...


@dataclass(frozen=True)
class FoldTuningResult:
    parameters: dict[str, Any]
    record: dict[str, Any]
    artifact_paths: tuple[Path, ...]


def validate_xgboost_search_space(
    search_space: dict[str, list[Any]],
) -> dict[str, list[Any]]:
    """Validate and normalize one pre-registered XGBoost search space."""

    expected = {
        "max_depth",
        "min_child_weight",
        "subsample",
        "colsample_bytree",
        "reg_alpha",
        "reg_lambda",
        "learning_rate",
    }
    optional = {"gamma"}
    if set(search_space) - expected - optional or expected - set(search_space):
        raise ValueError("nested Optuna search-space keys do not match the contract")
    normalized: dict[str, list[Any]] = {}
    for name, bounds in search_space.items():
        if not isinstance(bounds, list) or len(bounds) not in {2, 3}:
            raise ValueError(f"invalid search-space bounds for {name}")
        low, high = bounds[:2]
        if float(low) > float(high):
            raise ValueError(f"search-space lower bound exceeds upper bound for {name}")
        if len(bounds) == 3 and bounds[2] != "log":
            raise ValueError(f"unsupported search-space scale for {name}")
        normalized[name] = list(bounds)
    return normalized


def suggest_xgboost_parameters(
    trial: TrialLike,
    search_space: dict[str, list[Any]] | None = None,
) -> dict[str, Any]:
    """Suggest parameters from one explicit, pre-registered search space."""

    space = validate_xgboost_search_space(
        DEFAULT_XGBOOST_SEARCH_SPACE if search_space is None else search_space
    )

    parameters: dict[str, Any] = {
        "max_depth": trial.suggest_int(
            "max_depth", int(space["max_depth"][0]), int(space["max_depth"][1])
        )
    }
    for name in (
        "min_child_weight",
        "subsample",
        "colsample_bytree",
        "reg_alpha",
        "reg_lambda",
        "learning_rate",
        "gamma",
    ):
        if name not in space:
            continue
        bounds = space[name]
        parameters[name] = trial.suggest_float(
            name,
            float(bounds[0]),
            float(bounds[1]),
            log=len(bounds) == 3 and bounds[2] == "log",
        )
    return parameters


def inner_splits(
    target: np.ndarray, *, outer_fold: int, seed: int, n_splits: int = 3
) -> tuple[tuple[np.ndarray, np.ndarray], ...]:
    """Build deterministic stratified splits using outer-train labels only."""

    labels = np.asarray(target, dtype=np.int32)
    if labels.ndim != 1 or labels.size == 0:
        raise ValueError("target must be a non-empty one-dimensional array")
    splitter = StratifiedKFold(
        n_splits=n_splits,
        shuffle=True,
        random_state=seed + outer_fold,
    )
    return tuple(
        (train.astype(np.int64), valid.astype(np.int64))
        for train, valid in splitter.split(np.zeros(labels.size), labels)
    )


def remaining_trial_count(completed: int, requested: int) -> int:
    if requested < 1:
        raise ValueError("requested trial count must be positive")
    return max(0, requested - completed)


class NestedOptunaFoldTuner:
    """Tune XGBoost solely inside each outer fold's training partition."""

    def __init__(
        self,
        *,
        artifact_slug: str,
        root: Path,
        n_trials: int = 30,
        inner_n_splits: int = 3,
        seed: int = 42,
        balanced_sample_weight: bool = True,
        timeout_seconds: int | None = None,
        search_space: dict[str, list[Any]] | None = None,
        tie_break_inner_std: bool = False,
    ) -> None:
        self.artifact_slug = artifact_slug
        self.root = root
        self.n_trials = n_trials
        self.inner_n_splits = inner_n_splits
        self.seed = seed
        self.balanced_sample_weight = balanced_sample_weight
        self.timeout_seconds = timeout_seconds
        self.search_space = validate_xgboost_search_space(
            DEFAULT_XGBOOST_SEARCH_SPACE if search_space is None else search_space
        )
        self.tie_break_inner_std = tie_break_inner_std
        self.study_dir = root / "models" / artifact_slug / "optuna"
        self.report_dir = root / "reports" / artifact_slug
        self.records: list[dict[str, Any]] = []
        self.artifact_paths: list[Path] = []

    def __call__(
        self,
        *,
        fold: int,
        features: sparse.csr_matrix,
        target: np.ndarray,
        base_model_parameters: dict[str, Any],
    ) -> FoldTuningResult:
        try:
            import optuna
        except ImportError as error:
            raise RuntimeError(
                "Optuna 실행 전 `uv sync --frozen --group experiment`가 필요합니다."
            ) from error

        self.study_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        database_path = self.study_dir / f"outer_{fold:02d}.sqlite3"
        summary_path = self.report_dir / f"optuna_outer_{fold:02d}.json"
        study_name = f"{self.artifact_slug}_outer_{fold:02d}"
        sampler = optuna.samplers.TPESampler(seed=self.seed + fold)
        study = optuna.create_study(
            study_name=study_name,
            direction="maximize",
            sampler=sampler,
            storage=f"sqlite:///{database_path}",
            load_if_exists=True,
        )
        splits = inner_splits(
            target,
            outer_fold=fold,
            seed=self.seed,
            n_splits=self.inner_n_splits,
        )

        fixed_parameters = dict(base_model_parameters)

        def objective(trial: Any) -> float:
            candidate = suggest_xgboost_parameters(trial, self.search_space)
            fold_scores: list[float] = []
            selected_iterations: list[int] = []
            for inner_fold, (train_indices, valid_indices) in enumerate(splits):
                y_train = target[train_indices]
                y_valid = target[valid_indices]
                weights = (
                    compute_sample_weight(class_weight="balanced", y=y_train)
                    if self.balanced_sample_weight
                    else None
                )
                parameters = {
                    **fixed_parameters,
                    **candidate,
                    "num_class": len(CLASS_LABELS),
                    "random_state": self.seed + fold * 100 + inner_fold,
                }
                model = xgb.XGBClassifier(**parameters)
                model.fit(
                    features[train_indices],
                    y_train,
                    sample_weight=weights,
                    eval_set=[(features[valid_indices], y_valid)],
                    verbose=False,
                )
                audit = audit_xgboost_validation_iterations(
                    model,
                    features[valid_indices],
                    y_valid,
                    selection_policy="macro_f1_validation",
                )
                fold_scores.append(float(audit["selected_checkpoint"]["macro_f1"]))
                selected_iterations.append(
                    int(audit["selected_checkpoint"]["iteration"])
                )
            trial.set_user_attr("inner_macro_f1", fold_scores)
            trial.set_user_attr("selected_iterations", selected_iterations)
            trial.set_user_attr("inner_macro_f1_std", float(np.std(fold_scores)))
            return float(np.mean(fold_scores))

        # Only COMPLETE trials count toward the pre-registered budget. A Pod can
        # disappear mid-trial and leave a stale RUNNING row in SQLite; counting
        # that row would silently finish with fewer than ``n_trials`` results.
        completed = sum(
            trial.state == optuna.trial.TrialState.COMPLETE
            for trial in study.trials
        )
        remaining = remaining_trial_count(completed, self.n_trials)
        if remaining:
            study.optimize(
                objective,
                n_trials=remaining,
                timeout=self.timeout_seconds,
                gc_after_trial=True,
            )
        completed_trials = [
            trial
            for trial in study.trials
            if trial.state == optuna.trial.TrialState.COMPLETE
        ]
        if not completed_trials:
            raise RuntimeError(f"outer fold {fold} Optuna study has no completed trial")
        if len(completed_trials) < self.n_trials:
            raise RuntimeError(
                f"outer fold {fold} completed only {len(completed_trials)}/"
                f"{self.n_trials} Optuna trials; rerun the same study to resume"
            )
        selected_trial = study.best_trial
        if self.tie_break_inner_std:
            best_value = max(float(trial.value) for trial in completed_trials)
            tied = [
                trial
                for trial in completed_trials
                if abs(float(trial.value) - best_value) <= 1e-12
            ]
            selected_trial = min(
                tied,
                key=lambda trial: (
                    float(trial.user_attrs["inner_macro_f1_std"]),
                    int(trial.number),
                ),
            )

        trials = []
        for trial in study.trials:
            trials.append(
                {
                    "number": int(trial.number),
                    "state": trial.state.name,
                    "value": None if trial.value is None else float(trial.value),
                    "parameters": dict(trial.params),
                    "user_attributes": dict(trial.user_attrs),
                }
            )
        record = {
            "outer_fold": fold,
            "fit_scope": "outer_train_inner_cv_only",
            "test_or_outer_validation_used_for_selection": False,
            "study_name": study_name,
            "sampler": "TPESampler",
            "sampler_seed": self.seed + fold,
            "inner_n_splits": self.inner_n_splits,
            "requested_trials": self.n_trials,
            "completed_trials": sum(
                trial.state.name == "COMPLETE" for trial in study.trials
            ),
            "best_trial": int(selected_trial.number),
            "best_value": float(selected_trial.value),
            "best_parameters": dict(selected_trial.params),
            "best_trial_tie_break": (
                "minimum_inner_macro_f1_std_then_trial_number"
                if self.tie_break_inner_std
                else "optuna_default"
            ),
            "search_space": self.search_space,
            "database_path": str(database_path.relative_to(self.root)),
            "trials": trials,
        }
        summary_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.records.append(record)
        self.artifact_paths.extend((database_path, summary_path))
        return FoldTuningResult(
            parameters=dict(selected_trial.params),
            record=record,
            artifact_paths=(database_path, summary_path),
        )
