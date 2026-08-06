"""Post-hoc class-wise logit offset for Macro F1, fit via inner cross-fitting.

Issue #233. See `reports/analysis/external_biological_knowledge_feature_review.md`
("2. Macro F1용 nested decision rule", lines 91-106) for the design constraints
this module implements:

- The offset is fit per outer fold, using only that outer fold's train
  partition (never the full dataset OOF at once).
- Within an outer fold's train partition, honest (leak-free) probabilities
  come from a fixed inner K-fold cross-fit (see
  `fit_inner_cross_fitted_probabilities`) -- never from a model that saw the
  row during its own training.
- The offset range, regularization and candidate set are fixed here, before
  any run, not tuned against outer validation or test.
- Outer validation and test only ever get `apply_class_offset` (transform),
  never `search_class_offsets` (fit).
- The offset acts multiplicatively in probability space:
  `softmax(z + o) ∝ softmax(z) * exp(o)`, so no raw XGBoost margin/logit
  retraining is needed -- it is applied directly to already-computed
  probabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold

from open_cancer.constants import CLASS_LABELS

# Fixed before execution (Issue #233 design constraint). Not tuned against
# outer validation or test at any point.
CANDIDATE_OFFSET_GRID: tuple[float, ...] = tuple(
    round(float(value), 1) for value in np.arange(-1.0, 1.0001, 0.1)
)
REGULARIZATION_LAMBDA: float = 0.001
MAX_COORDINATE_PASSES: int = 5
INNER_N_SPLITS: int = 3


class NestedDecisionOffsetError(ValueError):
    """Raised when an offset search or application input violates the contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise NestedDecisionOffsetError(message)


def apply_class_offset(probabilities: np.ndarray, offset: np.ndarray) -> np.ndarray:
    """Transform-only: softmax(z)*exp(o), renormalized. Never fits anything."""
    probabilities = np.asarray(probabilities, dtype=np.float64)
    offset = np.asarray(offset, dtype=np.float64)
    _require(probabilities.ndim == 2, "확률은 2차원이어야 합니다.")
    _require(
        probabilities.shape[1] == len(CLASS_LABELS) == offset.shape[0],
        "확률/offset의 클래스 수가 고정 26개 순서와 다릅니다.",
    )
    _require(np.isfinite(probabilities).all(), "확률에 NaN 또는 무한대가 있습니다.")
    _require((probabilities >= 0).all(), "확률에 음수가 있습니다.")
    adjusted = probabilities * np.exp(offset)[None, :]
    row_sums = adjusted.sum(axis=1, keepdims=True)
    _require((row_sums > 0).all(), "offset 적용 후 확률 행의 합이 0입니다.")
    return adjusted / row_sums


def _regularized_macro_f1(
    probabilities: np.ndarray,
    targets: np.ndarray,
    offset: np.ndarray,
    *,
    regularization_lambda: float,
) -> float:
    adjusted = apply_class_offset(probabilities, offset)
    predictions = adjusted.argmax(axis=1)
    score = f1_score(
        targets,
        predictions,
        labels=np.arange(len(CLASS_LABELS)),
        average="macro",
        zero_division=0,
    )
    penalty = regularization_lambda * float(np.sum(offset**2))
    return float(score) - penalty


def search_class_offsets(
    probabilities: np.ndarray,
    targets: np.ndarray,
    *,
    candidate_grid: tuple[float, ...] = CANDIDATE_OFFSET_GRID,
    regularization_lambda: float = REGULARIZATION_LAMBDA,
    max_passes: int = MAX_COORDINATE_PASSES,
    eligible_classes: np.ndarray | None = None,
) -> dict[str, Any]:
    """Coordinate-descent grid search for a 26-dim class-wise offset.

    Only ever called on an inner-cross-fitted (honest) probability set --
    never on outer validation or test. Each class's offset is searched
    independently, holding the others fixed, maximizing L2-regularized
    Macro F1; repeated in fixed class order until a full pass makes no
    improvement or `max_passes` is reached.

    `eligible_classes`, if given, is a boolean array (26,) marking which
    classes may have a non-zero offset (Issue #276: classes below a sample-
    size gate are left at offset=0 and never searched, since coordinate
    descent on too few inner-fold samples fits noise rather than signal).
    """
    targets = np.asarray(targets, dtype=np.int64)
    n_classes = len(CLASS_LABELS)
    _require(probabilities.shape[0] == len(targets), "확률/target 행 수가 다릅니다.")
    _require(len(candidate_grid) > 0, "candidate_grid가 비어 있습니다.")
    if eligible_classes is None:
        eligible_classes = np.ones(n_classes, dtype=bool)
    else:
        eligible_classes = np.asarray(eligible_classes, dtype=bool)
        _require(eligible_classes.shape == (n_classes,), "eligible_classes 길이가 26이 아닙니다.")

    offset = np.zeros(n_classes, dtype=np.float64)
    best_score = _regularized_macro_f1(
        probabilities, targets, offset, regularization_lambda=regularization_lambda
    )
    trace: list[dict[str, Any]] = []
    for pass_index in range(max_passes):
        improved = False
        for class_index in range(n_classes):
            if not eligible_classes[class_index]:
                continue
            best_value = offset[class_index]
            best_local_score = best_score
            for candidate in candidate_grid:
                trial = offset.copy()
                trial[class_index] = candidate
                score = _regularized_macro_f1(
                    probabilities, targets, trial, regularization_lambda=regularization_lambda
                )
                if score > best_local_score:
                    best_local_score = score
                    best_value = candidate
            if best_value != offset[class_index]:
                offset[class_index] = best_value
                best_score = best_local_score
                improved = True
        trace.append(
            {
                "pass": pass_index,
                "regularized_score": best_score,
                "offset": offset.tolist(),
            }
        )
        if not improved:
            break

    return {
        "offset": offset,
        "final_regularized_score": best_score,
        "passes_run": len(trace),
        "trace": trace,
        "eligible_classes": eligible_classes.tolist(),
    }


@dataclass(frozen=True)
class InnerCrossFitResult:
    """Honest (leak-free) probabilities covering one outer fold's train partition."""

    row_positions: np.ndarray  # positions within outer_train_indices' own frame, sorted
    probabilities: np.ndarray  # aligned to row_positions
    inner_fold_assignment: np.ndarray  # which inner fold each row was held out in
    n_inner_splits: int


def fit_inner_cross_fitted_probabilities(
    *,
    features,
    targets: np.ndarray,
    train_fn,
    n_splits: int = INNER_N_SPLITS,
    seed: int,
) -> InnerCrossFitResult:
    """Honest inner-OOF probabilities over one outer fold's train partition.

    `features`/`targets` must already be restricted to one outer fold's train
    partition (never include that outer fold's validation rows). For each of
    `n_splits` inner folds, `train_fn(inner_train_idx, inner_holdout_idx)` is
    called and must return predicted probabilities (n_holdout, 26) for the
    held-out inner rows, using a model fit only on the inner-train rows.
    """
    targets = np.asarray(targets, dtype=np.int64)
    n_rows = features.shape[0]
    _require(n_rows == len(targets), "features/target 행 수가 다릅니다.")
    _require(n_splits >= 2, "inner n_splits는 2 이상이어야 합니다.")

    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    probabilities = np.full((n_rows, len(CLASS_LABELS)), np.nan, dtype=np.float64)
    inner_fold_assignment = np.full(n_rows, -1, dtype=np.int32)

    for inner_fold, (inner_train_idx, inner_holdout_idx) in enumerate(
        splitter.split(np.zeros(n_rows), targets)
    ):
        holdout_probabilities = train_fn(inner_train_idx, inner_holdout_idx)
        holdout_probabilities = np.asarray(holdout_probabilities, dtype=np.float64)
        _require(
            holdout_probabilities.shape == (len(inner_holdout_idx), len(CLASS_LABELS)),
            f"inner fold {inner_fold}: train_fn 반환 shape이 예상과 다릅니다.",
        )
        probabilities[inner_holdout_idx] = holdout_probabilities
        inner_fold_assignment[inner_holdout_idx] = inner_fold

    _require(not np.isnan(probabilities).any(), "inner cross-fit 확률에 채워지지 않은 행이 있습니다.")
    _require((inner_fold_assignment >= 0).all(), "모든 행이 정확히 하나의 inner fold에서 held out돼야 합니다.")

    return InnerCrossFitResult(
        row_positions=np.arange(n_rows),
        probabilities=probabilities,
        inner_fold_assignment=inner_fold_assignment,
        n_inner_splits=n_splits,
    )


def min_class_count_per_inner_fold(
    targets: np.ndarray, inner_fold_assignment: np.ndarray, n_inner_splits: int
) -> np.ndarray:
    """Smallest per-inner-fold sample count for each of the 26 classes.

    Issue #276's sample gate uses this (not the raw outer-train count) as
    the eligibility statistic: it directly measures how few examples of a
    class any single inner-fold evaluation actually saw, which is what
    makes the coordinate-descent search unstable for that class.
    """
    targets = np.asarray(targets, dtype=np.int64)
    n_classes = len(CLASS_LABELS)
    counts = np.zeros((n_inner_splits, n_classes), dtype=np.int64)
    for inner_fold in range(n_inner_splits):
        mask = inner_fold_assignment == inner_fold
        for class_index in range(n_classes):
            counts[inner_fold, class_index] = int(np.sum(targets[mask] == class_index))
    return counts.min(axis=0)


def apply_pairwise_redistribution(
    probabilities: np.ndarray,
    pair_indices: tuple[int, int],
    delta: float,
    *,
    eps: float = 1e-9,
) -> np.ndarray:
    """Transform-only: shift probability mass within one class pair's own sub-budget.

    Issue #604, follow-up to #233/#276/#515. Those experiments applied
    `softmax(z)*exp(o)` then renormalized over all 26 classes, which
    coupled every class's probability into a shared zero-sum competition
    even when only a few classes had non-zero offsets (#515 measured a
    0.0994 absolute F1 delta across the 22 "untouched" classes against a
    0.01 gate). This function instead holds `s = p[a] + p[b]` fixed for
    one row and only redistributes *within* that pair: every other
    column is returned byte-identical to the input, and the row's total
    sum is trivially conserved since the pair's two entries still sum to
    `s`. `delta` shifts the pair's internal split ratio in logit space:
    `r' = sigmoid(logit(p[a]/s) + delta)`.
    """
    probabilities = np.asarray(probabilities, dtype=np.float64)
    _require(probabilities.ndim == 2, "확률은 2차원이어야 합니다.")
    _require(
        probabilities.shape[1] == len(CLASS_LABELS),
        "확률의 클래스 수가 고정 26개 순서와 다릅니다.",
    )
    _require(np.isfinite(probabilities).all(), "확률에 NaN 또는 무한대가 있습니다.")
    _require((probabilities >= 0).all(), "확률에 음수가 있습니다.")
    index_a, index_b = pair_indices
    _require(
        0 <= index_a < len(CLASS_LABELS) and 0 <= index_b < len(CLASS_LABELS) and index_a != index_b,
        "pair_indices가 유효한 서로 다른 클래스 인덱스 쌍이어야 합니다.",
    )
    result = probabilities.copy()
    p_a = probabilities[:, index_a]
    p_b = probabilities[:, index_b]
    s = p_a + p_b
    has_mass = s > eps
    ratio = np.where(has_mass, p_a / np.where(has_mass, s, 1.0), 0.5)
    ratio_clipped = np.clip(ratio, eps, 1.0 - eps)
    logit_ratio = np.log(ratio_clipped / (1.0 - ratio_clipped))
    shifted_ratio = 1.0 / (1.0 + np.exp(-(logit_ratio + delta)))
    new_p_a = s * shifted_ratio
    new_p_b = s - new_p_a
    result[:, index_a] = np.where(has_mass, new_p_a, p_a)
    result[:, index_b] = np.where(has_mass, new_p_b, p_b)
    return result


def _regularized_macro_f1_pairwise(
    probabilities: np.ndarray,
    targets: np.ndarray,
    pair_indices: tuple[int, int],
    delta: float,
    *,
    regularization_lambda: float,
) -> float:
    adjusted = apply_pairwise_redistribution(probabilities, pair_indices, delta)
    predictions = adjusted.argmax(axis=1)
    score = f1_score(
        targets,
        predictions,
        labels=np.arange(len(CLASS_LABELS)),
        average="macro",
        zero_division=0,
    )
    return float(score) - regularization_lambda * (delta**2)


def search_pairwise_delta(
    probabilities: np.ndarray,
    targets: np.ndarray,
    pair_indices: tuple[int, int],
    *,
    candidate_grid: tuple[float, ...] = CANDIDATE_OFFSET_GRID,
    regularization_lambda: float = REGULARIZATION_LAMBDA,
) -> dict[str, Any]:
    """Single-scalar grid search for one pair's redistribution `delta`.

    Only ever called on an inner-cross-fitted (honest) probability set --
    never on outer validation or test. Unlike `search_class_offsets`, this
    needs no coordinate descent: a pair's delta only affects that pair's
    own two columns, so pairs never interact and each is searched
    independently over the fixed candidate grid.
    """
    targets = np.asarray(targets, dtype=np.int64)
    _require(probabilities.shape[0] == len(targets), "확률/target 행 수가 다릅니다.")
    _require(len(candidate_grid) > 0, "candidate_grid가 비어 있습니다.")
    best_delta = 0.0
    best_score = _regularized_macro_f1_pairwise(
        probabilities, targets, pair_indices, 0.0, regularization_lambda=regularization_lambda
    )
    trace: list[dict[str, Any]] = []
    for candidate in candidate_grid:
        score = _regularized_macro_f1_pairwise(
            probabilities, targets, pair_indices, candidate, regularization_lambda=regularization_lambda
        )
        trace.append({"delta": candidate, "regularized_score": score})
        if score > best_score:
            best_score = score
            best_delta = candidate
    return {
        "delta": best_delta,
        "final_regularized_score": best_score,
        "trace": trace,
    }
