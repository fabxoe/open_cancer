"""Fold-safe randomized XGBoost search for canonical outer cross-validation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from scipy import sparse
from sklearn.metrics import f1_score, log_loss
from sklearn.model_selection import ParameterSampler, StratifiedKFold
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.constants import CLASS_LABELS


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def select_best_trial(trials: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    """Select by Macro F1, then log loss, complexity, and stable trial number."""
    _require(len(trials) > 0, "선택할 search trial이 없습니다.")
    return min(
        trials,
        key=lambda row: (
            -float(row["mean_macro_f1"]),
            float(row["mean_log_loss"]),
            int(row["parameters"].get("max_depth", 0)),
            int(row["trial"]),
        ),
    )


def run_nested_xgb_search(
    *,
    train_features: sparse.csr_matrix,
    targets: np.ndarray,
    outer_folds: np.ndarray,
    base_parameters: Mapping[str, Any],
    parameter_space: Mapping[str, Sequence[Any]],
    n_iter: int,
    inner_splits: int,
    seed: int,
    balanced_sample_weight: bool,
) -> tuple[tuple[dict[str, Any], ...], dict[str, Any]]:
    """Tune each outer model using only rows in that outer training fold."""
    import xgboost as xgb

    y = np.asarray(targets, dtype=np.int32)
    folds = np.asarray(outer_folds, dtype=np.int8)
    _require(sparse.isspmatrix_csr(train_features), "train_features는 CSR이어야 합니다.")
    _require(train_features.shape[0] == len(y) == len(folds), "train 행 계약이 다릅니다.")
    _require(set(np.unique(folds)) == set(range(5)), "canonical outer fold는 0..4여야 합니다.")
    _require(set(np.unique(y)) == set(range(len(CLASS_LABELS))), "고정 26개 class index가 필요합니다.")
    _require(n_iter > 0 and inner_splits >= 2, "search 반복 수 또는 inner fold 수가 잘못되었습니다.")

    sampled = list(ParameterSampler(dict(parameter_space), n_iter=n_iter, random_state=seed))
    selected_parameters: list[dict[str, Any]] = []
    outer_records: list[dict[str, Any]] = []
    for outer_fold in range(5):
        outer_train_indices = np.flatnonzero(folds != outer_fold)
        outer_y = y[outer_train_indices]
        inner_cv = StratifiedKFold(
            n_splits=inner_splits,
            shuffle=True,
            random_state=seed + outer_fold,
        )
        trials: list[dict[str, Any]] = []
        for trial_index, candidate in enumerate(sampled):
            inner_rows: list[dict[str, Any]] = []
            for inner_fold, (fit_local, valid_local) in enumerate(
                inner_cv.split(np.zeros(len(outer_y)), outer_y)
            ):
                fit_indices = outer_train_indices[fit_local]
                valid_indices = outer_train_indices[valid_local]
                parameters = {
                    **dict(base_parameters),
                    **dict(candidate),
                    "num_class": len(CLASS_LABELS),
                    "random_state": seed + outer_fold * 1000 + trial_index * 10 + inner_fold,
                }
                model = xgb.XGBClassifier(**parameters)
                weights = (
                    compute_sample_weight(class_weight="balanced", y=y[fit_indices])
                    if balanced_sample_weight
                    else None
                )
                model.fit(
                    train_features[fit_indices],
                    y[fit_indices],
                    sample_weight=weights,
                    eval_set=[(train_features[valid_indices], y[valid_indices])],
                    verbose=False,
                )
                probabilities = model.predict_proba(train_features[valid_indices])
                predictions = probabilities.argmax(axis=1)
                inner_rows.append(
                    {
                        "inner_fold": inner_fold,
                        "macro_f1": float(
                            f1_score(y[valid_indices], predictions, average="macro")
                        ),
                        "log_loss": float(
                            log_loss(
                                y[valid_indices],
                                probabilities,
                                labels=np.arange(len(CLASS_LABELS)),
                            )
                        ),
                        "best_iteration": int(model.best_iteration),
                    }
                )
            trials.append(
                {
                    "trial": trial_index,
                    "parameters": dict(candidate),
                    "mean_macro_f1": float(np.mean([row["macro_f1"] for row in inner_rows])),
                    "mean_log_loss": float(np.mean([row["log_loss"] for row in inner_rows])),
                    "inner_folds": inner_rows,
                }
            )
        best = select_best_trial(trials)
        selected = {**dict(base_parameters), **dict(best["parameters"])}
        selected_parameters.append(selected)
        outer_records.append(
            {
                "outer_fold": outer_fold,
                "outer_train_rows": int(len(outer_train_indices)),
                "selection_metric": "macro_f1",
                "selected_trial": int(best["trial"]),
                "selected_parameters": selected,
                "selected_inner_macro_f1": float(best["mean_macro_f1"]),
                "selected_inner_log_loss": float(best["mean_log_loss"]),
                "trials": trials,
            }
        )
    document = {
        "method": "randomized nested cross-validation",
        "fit_scope": "each canonical outer-train fold only",
        "outer_folds": 5,
        "inner_splits": inner_splits,
        "n_iter": n_iter,
        "primary_metric": "macro_f1",
        "secondary_metric": "log_loss",
        "seed": seed,
        "folds": outer_records,
    }
    return tuple(selected_parameters), document
