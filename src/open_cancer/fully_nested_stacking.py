"""Leakage-audited fully nested stacking for a fixed base-model portfolio.

The module deliberately knows nothing about a particular feature family.  A
base adapter receives explicit global row indices and must fit every learned
transformer and estimator from those rows only.  The orchestration layer then
proves the outer/inner separation, caches predictions by index/config hashes,
and records a machine-readable scope audit.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

import numpy as np
from sklearn.ensemble import ExtraTreesClassifier

from open_cancer.constants import CLASS_LABELS


class NestedStackingError(ValueError):
    """Raised when a split, prediction, or cache violates the nested contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise NestedStackingError(message)


def index_sha256(indices: Sequence[int] | np.ndarray) -> str:
    """Hash sorted unique integer indices in a platform-independent encoding."""

    values = np.asarray(indices, dtype=np.int64)
    _require(values.ndim == 1, "index array must be one-dimensional")
    _require(np.array_equal(values, np.unique(values)), "indices must be sorted and unique")
    return hashlib.sha256(values.astype("<i8", copy=False).tobytes()).hexdigest()


def stable_json_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def fixed_median_parameters(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Collapse pre-existing numeric fold parameters to one deterministic config.

    This is used when historical parameters are indexed by canonical folds but
    the new nested split has no honest mapping to those fold numbers.  Integer
    inputs remain integers; other numeric values use the ordinary median.
    """

    _require(bool(records), "at least one parameter record is required")
    keys = tuple(sorted(records[0]))
    _require(
        all(tuple(sorted(record)) == keys for record in records),
        "all parameter records must have identical keys",
    )
    result: dict[str, Any] = {}
    for key in keys:
        values = [record[key] for record in records]
        _require(
            all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values),
            f"median parameter is not numeric: {key}",
        )
        median = float(np.median(np.asarray(values, dtype=np.float64)))
        result[key] = int(round(median)) if all(isinstance(value, int) for value in values) else median
    return result


@dataclass(frozen=True)
class OuterInnerSplit:
    outer_fold: int
    inner_fold: int
    fit_indices: np.ndarray
    validation_indices: np.ndarray
    outer_validation_indices: np.ndarray


def build_outer_inner_splits(folds: np.ndarray) -> tuple[OuterInnerSplit, ...]:
    """Use the four remaining canonical folds as inner folds for each outer fold."""

    values = np.asarray(folds, dtype=np.int32)
    _require(values.ndim == 1 and len(values) > 0, "fold vector is empty or invalid")
    labels = tuple(int(value) for value in sorted(np.unique(values)))
    _require(labels == tuple(range(len(labels))), "fold labels must be contiguous from zero")
    _require(len(labels) >= 3, "nested stacking needs at least three folds")
    output: list[OuterInnerSplit] = []
    all_indices = np.arange(len(values), dtype=np.int64)
    for outer_fold in labels:
        outer_validation = all_indices[values == outer_fold]
        outer_train = all_indices[values != outer_fold]
        inner_validation_union: list[np.ndarray] = []
        for inner_fold in labels:
            if inner_fold == outer_fold:
                continue
            inner_validation = all_indices[values == inner_fold]
            inner_fit = all_indices[(values != outer_fold) & (values != inner_fold)]
            _require(len(np.intersect1d(inner_fit, inner_validation)) == 0, "inner fit/validation overlap")
            _require(len(np.intersect1d(inner_fit, outer_validation)) == 0, "outer validation leaked into inner fit")
            _require(len(np.intersect1d(inner_validation, outer_validation)) == 0, "inner/outer validation overlap")
            output.append(
                OuterInnerSplit(
                    outer_fold=outer_fold,
                    inner_fold=inner_fold,
                    fit_indices=inner_fit,
                    validation_indices=inner_validation,
                    outer_validation_indices=outer_validation,
                )
            )
            inner_validation_union.append(inner_validation)
        covered = np.sort(np.concatenate(inner_validation_union))
        _require(np.array_equal(covered, outer_train), "inner validation rows do not cover outer train exactly once")
    return tuple(output)


@dataclass(frozen=True)
class BasePrediction:
    probabilities: np.ndarray
    feature_audit: Mapping[str, Any]


class NestedBaseAdapter(Protocol):
    """One candidate capable of a fit on arbitrary global row indices."""

    name: str

    @property
    def signature(self) -> Mapping[str, Any]: ...

    def fit_predict(
        self,
        *,
        fit_indices: np.ndarray,
        predict_indices: np.ndarray | None,
        predict_test: bool,
        seed: int,
        scope_name: str,
    ) -> BasePrediction: ...


class PredictionCache:
    """Content-addressed prediction cache with metadata validation."""

    def __init__(self, directory: Path, *, enabled: bool = True) -> None:
        self.directory = directory
        self.enabled = enabled
        self.directory.mkdir(parents=True, exist_ok=True)

    def get_or_compute(
        self,
        payload: Mapping[str, Any],
        compute: Callable[[], BasePrediction],
    ) -> tuple[BasePrediction, bool, str]:
        key = stable_json_sha256(payload)
        matrix_path = self.directory / f"{key}.npz"
        metadata_path = self.directory / f"{key}.json"
        if self.enabled and matrix_path.exists() and metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            _require(metadata.get("cache_payload") == payload, "prediction cache payload mismatch")
            with np.load(matrix_path, allow_pickle=False) as stored:
                probability = np.asarray(stored["probabilities"], dtype=np.float64)
            return BasePrediction(probability, metadata.get("feature_audit", {})), True, key

        computed = compute()
        result = BasePrediction(
            np.asarray(computed.probabilities, dtype=np.float32),
            computed.feature_audit,
        )
        if self.enabled:
            np.savez_compressed(matrix_path, probabilities=np.asarray(result.probabilities, dtype=np.float32))
            metadata_path.write_text(
                json.dumps(
                    {"cache_payload": payload, "feature_audit": dict(result.feature_audit)},
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
        return result, False, key


@dataclass(frozen=True)
class FullyNestedStackingOutput:
    oof_probabilities: np.ndarray
    test_probabilities: np.ndarray
    base_oof_probabilities: Mapping[str, np.ndarray]
    base_test_probabilities: Mapping[str, np.ndarray]
    fold_metrics: tuple[Mapping[str, Any], ...]
    audit_records: tuple[Mapping[str, Any], ...]
    runtime_seconds: float


def _probabilities(values: np.ndarray, rows: int) -> np.ndarray:
    matrix = np.asarray(values, dtype=np.float64)
    _require(matrix.shape == (rows, len(CLASS_LABELS)), f"probability shape mismatch: {matrix.shape}")
    _require(np.isfinite(matrix).all(), "probabilities contain non-finite values")
    _require((matrix >= 0).all(), "probabilities contain negative values")
    sums = matrix.sum(axis=1, keepdims=True)
    _require((sums > 0).all(), "probability row sum is zero")
    return matrix / sums


def default_meta_factory(seed: int) -> ExtraTreesClassifier:
    return ExtraTreesClassifier(
        n_estimators=700,
        min_samples_leaf=2,
        max_features="sqrt",
        class_weight="balanced",
        # The meta matrix is tiny; one thread keeps cache-resumed reruns bitwise
        # reproducible without materially affecting runtime.
        n_jobs=1,
        random_state=seed,
    )


def run_fully_nested_stacking(
    *,
    adapters: Sequence[NestedBaseAdapter],
    targets: np.ndarray,
    folds: np.ndarray,
    test_row_count: int,
    cache: PredictionCache,
    seed: int = 42,
    meta_factory: Callable[[int], Any] = default_meta_factory,
    progress: Callable[[str], None] = print,
) -> FullyNestedStackingOutput:
    """Run outer evaluation, reusable base OOF, and final test deployment.

    Per outer fold, the meta learner sees four-fold inner OOF predictions only.
    Every base model is then refit on the full outer-train partition before it
    predicts untouched outer-validation.  The outer-refit predictions also
    form leakage-free full-data base OOF features for the final deployment meta
    learner, so no redundant canonical OOF run is needed.
    """

    started = time.perf_counter()
    y = np.asarray(targets, dtype=np.int32)
    fold_values = np.asarray(folds, dtype=np.int32)
    _require(len(y) == len(fold_values), "target/fold row mismatch")
    _require(bool(adapters), "at least one base adapter is required")
    names = tuple(adapter.name for adapter in adapters)
    _require(len(names) == len(set(names)), "base adapter names must be unique")
    n_rows = len(y)
    n_classes = len(CLASS_LABELS)
    labels = tuple(int(value) for value in sorted(np.unique(fold_values)))
    split_lookup = {
        (split.outer_fold, split.inner_fold): split
        for split in build_outer_inner_splits(fold_values)
    }
    oof = np.full((n_rows, n_classes), np.nan, dtype=np.float64)
    base_oof = {
        name: np.full((n_rows, n_classes), np.nan, dtype=np.float64) for name in names
    }
    audits: list[Mapping[str, Any]] = []
    fold_metrics: list[Mapping[str, Any]] = []
    completed_fit_count = 0
    total_fit_count = len(labels) * (len(labels) - 1) * len(adapters) + len(labels) * len(adapters) + len(adapters)

    def run_base(
        adapter: NestedBaseAdapter,
        *,
        fit_indices: np.ndarray,
        predict_indices: np.ndarray | None,
        predict_test: bool,
        stage: str,
        outer_fold: int | None,
        inner_fold: int | None,
        protected_indices: np.ndarray,
    ) -> BasePrediction:
        nonlocal completed_fit_count
        fit_indices = np.asarray(fit_indices, dtype=np.int64)
        if predict_indices is not None:
            predict_indices = np.asarray(predict_indices, dtype=np.int64)
        _require(len(np.intersect1d(fit_indices, protected_indices)) == 0, f"{stage}: protected rows leaked into fit")
        if predict_indices is not None:
            _require(len(np.intersect1d(fit_indices, predict_indices)) == 0, f"{stage}: fit/predict overlap")
        scope_name = f"{stage}__outer_{outer_fold}__inner_{inner_fold}__{adapter.name}"
        payload = {
            "schema_version": 1,
            "adapter": adapter.name,
            "adapter_signature": dict(adapter.signature),
            "stage": stage,
            "outer_fold": outer_fold,
            "inner_fold": inner_fold,
            "seed": seed + completed_fit_count,
            "fit_indices_sha256": index_sha256(fit_indices),
            "predict_indices_sha256": None if predict_indices is None else index_sha256(predict_indices),
            "predict_test": predict_test,
        }
        progress(
            f"[{completed_fit_count + 1}/{total_fit_count}] {stage} | "
            f"outer={outer_fold} inner={inner_fold} model={adapter.name}"
        )
        fit_started = time.perf_counter()
        result, cache_hit, cache_key = cache.get_or_compute(
            payload,
            lambda: adapter.fit_predict(
                fit_indices=fit_indices,
                predict_indices=predict_indices,
                predict_test=predict_test,
                seed=int(payload["seed"]),
                scope_name=scope_name,
            ),
        )
        completed_fit_count += 1
        fit_runtime = time.perf_counter() - fit_started
        elapsed = time.perf_counter() - started
        average = elapsed / completed_fit_count
        remaining = average * (total_fit_count - completed_fit_count)
        progress(
            f"[{completed_fit_count}/{total_fit_count}] complete | "
            f"runtime={fit_runtime:.1f}s cache_hit={cache_hit} "
            f"elapsed={elapsed / 60:.1f}m rough_eta={remaining / 60:.1f}m"
        )
        expected_rows = test_row_count if predict_test else len(predict_indices)
        probability = _probabilities(result.probabilities, expected_rows)
        audit = {
            "stage": stage,
            "outer_fold": outer_fold,
            "inner_fold": inner_fold,
            "model": adapter.name,
            "fit_row_count": len(fit_indices),
            "fit_indices_sha256": payload["fit_indices_sha256"],
            "predict_row_count": expected_rows,
            "predict_indices_sha256": payload["predict_indices_sha256"],
            "protected_row_count": len(protected_indices),
            "protected_indices_sha256": index_sha256(protected_indices),
            "fit_protected_overlap": int(len(np.intersect1d(fit_indices, protected_indices))),
            "fit_predict_overlap": None if predict_indices is None else int(len(np.intersect1d(fit_indices, predict_indices))),
            "cache_hit": cache_hit,
            "cache_key": cache_key,
            "fit_runtime_seconds": fit_runtime,
            "feature_audit": dict(result.feature_audit),
        }
        audits.append(audit)
        return BasePrediction(probability, result.feature_audit)

    all_indices = np.arange(n_rows, dtype=np.int64)
    for outer_fold in labels:
        outer_valid = all_indices[fold_values == outer_fold]
        outer_train = all_indices[fold_values != outer_fold]
        inner_meta = np.full(
            (len(outer_train), len(adapters) * n_classes), np.nan, dtype=np.float64
        )
        outer_position = {int(index): position for position, index in enumerate(outer_train)}
        for inner_fold in labels:
            if inner_fold == outer_fold:
                continue
            split = split_lookup[(outer_fold, inner_fold)]
            target_positions = np.asarray(
                [outer_position[int(index)] for index in split.validation_indices], dtype=np.int64
            )
            for model_index, adapter in enumerate(adapters):
                result = run_base(
                    adapter,
                    fit_indices=split.fit_indices,
                    predict_indices=split.validation_indices,
                    predict_test=False,
                    stage="inner_oof",
                    outer_fold=outer_fold,
                    inner_fold=inner_fold,
                    protected_indices=outer_valid,
                )
                block = slice(model_index * n_classes, (model_index + 1) * n_classes)
                inner_meta[target_positions, block] = result.probabilities
        _require(not np.isnan(inner_meta).any(), f"outer {outer_fold}: incomplete inner OOF")
        meta = meta_factory(seed + outer_fold)
        meta.fit(inner_meta, y[outer_train])
        outer_meta = np.empty((len(outer_valid), len(adapters) * n_classes), dtype=np.float64)
        for model_index, adapter in enumerate(adapters):
            result = run_base(
                adapter,
                fit_indices=outer_train,
                predict_indices=outer_valid,
                predict_test=False,
                stage="outer_refit",
                outer_fold=outer_fold,
                inner_fold=None,
                protected_indices=outer_valid,
            )
            block = slice(model_index * n_classes, (model_index + 1) * n_classes)
            outer_meta[:, block] = result.probabilities
            base_oof[adapter.name][outer_valid] = result.probabilities
        raw = np.asarray(meta.predict_proba(outer_meta), dtype=np.float64)
        outer_probability = np.zeros((len(outer_valid), n_classes), dtype=np.float64)
        outer_probability[:, np.asarray(meta.classes_, dtype=np.int64)] = raw
        outer_probability = _probabilities(outer_probability, len(outer_valid))
        oof[outer_valid] = outer_probability
        prediction = outer_probability.argmax(axis=1)
        from sklearn.metrics import f1_score

        fold_score = float(f1_score(y[outer_valid], prediction, average="macro", zero_division=0))
        fold_metrics.append(
            {
                "outer_fold": outer_fold,
                "macro_f1": fold_score,
                "outer_train_row_count": len(outer_train),
                "outer_validation_row_count": len(outer_valid),
                "inner_meta_shape": list(inner_meta.shape),
            }
        )
        progress(f"outer fold {outer_fold} complete | macro_f1={fold_score:.10f}")

    _require(not np.isnan(oof).any(), "fully nested OOF is incomplete")
    _require(all(not np.isnan(matrix).any() for matrix in base_oof.values()), "base OOF is incomplete")

    deployment_meta = np.hstack([base_oof[name] for name in names])
    final_meta = meta_factory(seed + 10_000)
    final_meta.fit(deployment_meta, y)
    base_test: dict[str, np.ndarray] = {}
    test_meta = np.empty((test_row_count, len(adapters) * n_classes), dtype=np.float64)
    for model_index, adapter in enumerate(adapters):
        result = run_base(
            adapter,
            fit_indices=all_indices,
            predict_indices=None,
            predict_test=True,
            stage="final_refit",
            outer_fold=None,
            inner_fold=None,
            protected_indices=np.asarray([], dtype=np.int64),
        )
        block = slice(model_index * n_classes, (model_index + 1) * n_classes)
        test_meta[:, block] = result.probabilities
        base_test[adapter.name] = result.probabilities
    raw_test = np.asarray(final_meta.predict_proba(test_meta), dtype=np.float64)
    test_probability = np.zeros((test_row_count, n_classes), dtype=np.float64)
    test_probability[:, np.asarray(final_meta.classes_, dtype=np.int64)] = raw_test
    test_probability = _probabilities(test_probability, test_row_count)
    return FullyNestedStackingOutput(
        oof_probabilities=oof,
        test_probabilities=test_probability,
        base_oof_probabilities=base_oof,
        base_test_probabilities=base_test,
        fold_metrics=tuple(fold_metrics),
        audit_records=tuple(audits),
        runtime_seconds=float(time.perf_counter() - started),
    )
