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


def suggest_xgboost_parameters(trial: TrialLike) -> dict[str, Any]:
    """Return the pre-registered EXP-229 Optuna search space."""

    return {
        "max_depth": trial.suggest_int("max_depth", 4, 8),
        "min_child_weight": trial.suggest_float("min_child_weight", 1.0, 10.0),
        "subsample": trial.suggest_float("subsample", 0.5, 0.9),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 0.9),
        "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 1.0),
        "reg_lambda": trial.suggest_float("reg_lambda", 0.5, 5.0),
        "learning_rate": trial.suggest_float(
            "learning_rate", 0.02, 0.08, log=True
        ),
    }


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
    ) -> None:
        self.artifact_slug = artifact_slug
        self.root = root
        self.n_trials = n_trials
        self.inner_n_splits = inner_n_splits
        self.seed = seed
        self.balanced_sample_weight = balanced_sample_weight
        self.timeout_seconds = timeout_seconds
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
            candidate = suggest_xgboost_parameters(trial)
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
            "best_trial": int(study.best_trial.number),
            "best_value": float(study.best_value),
            "best_parameters": dict(study.best_params),
            "search_space": {
                "max_depth": [4, 8],
                "min_child_weight": [1.0, 10.0],
                "subsample": [0.5, 0.9],
                "colsample_bytree": [0.5, 0.9],
                "reg_alpha": [0.0, 1.0],
                "reg_lambda": [0.5, 5.0],
                "learning_rate": [0.02, 0.08, "log"],
            },
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
            parameters=dict(study.best_params),
            record=record,
            artifact_paths=(database_path, summary_path),
        )
