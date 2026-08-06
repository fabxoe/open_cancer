from __future__ import annotations

from pathlib import Path

import numpy as np

from open_cancer.constants import CLASS_LABELS
from open_cancer.fully_nested_stacking import (
    BasePrediction,
    PredictionCache,
    build_outer_inner_splits,
    fixed_median_parameters,
    run_fully_nested_stacking,
)


class _FakeAdapter:
    def __init__(self, name: str) -> None:
        self.name = name
        self.fit_calls = 0

    @property
    def signature(self):
        return {"name": self.name, "version": 1}

    def fit_predict(
        self,
        *,
        fit_indices,
        predict_indices,
        predict_test,
        seed,
        scope_name,
    ):
        self.fit_calls += 1
        rows = 7 if predict_test else len(predict_indices)
        generator = np.random.default_rng(seed + sum(ord(char) for char in self.name))
        probabilities = generator.random((rows, len(CLASS_LABELS))) + 0.01
        return BasePrediction(
            probabilities,
            {
                "scope_name": scope_name,
                "fit_rows": len(fit_indices),
                "vocabulary_fit_indices_only": True,
            },
        )


def _balanced_five_fold_problem():
    folds = np.repeat(np.arange(5, dtype=np.int32), len(CLASS_LABELS))
    targets = np.tile(np.arange(len(CLASS_LABELS), dtype=np.int32), 5)
    return targets, folds


def test_outer_inner_splits_cover_outer_train_without_overlap():
    _targets, folds = _balanced_five_fold_problem()
    splits = build_outer_inner_splits(folds)
    assert len(splits) == 20
    for outer_fold in range(5):
        outer = [split for split in splits if split.outer_fold == outer_fold]
        assert len(outer) == 4
        outer_validation = np.flatnonzero(folds == outer_fold)
        outer_train = np.flatnonzero(folds != outer_fold)
        assert np.array_equal(
            np.sort(np.concatenate([split.validation_indices for split in outer])),
            outer_train,
        )
        for split in outer:
            assert len(np.intersect1d(split.fit_indices, split.validation_indices)) == 0
            assert len(np.intersect1d(split.fit_indices, outer_validation)) == 0


def test_fixed_median_parameters_preserves_integer_type():
    result = fixed_median_parameters(
        [
            {"max_depth": 4, "learning_rate": 0.01},
            {"max_depth": 6, "learning_rate": 0.03},
            {"max_depth": 8, "learning_rate": 0.02},
        ]
    )
    assert result == {"learning_rate": 0.02, "max_depth": 6}
    assert isinstance(result["max_depth"], int)


def test_full_nested_engine_runs_104_base_fits_and_reuses_cache(tmp_path: Path):
    targets, folds = _balanced_five_fold_problem()
    adapters = tuple(_FakeAdapter(f"model-{index}") for index in range(4))
    cache = PredictionCache(tmp_path / "cache")
    output = run_fully_nested_stacking(
        adapters=adapters,
        targets=targets,
        folds=folds,
        test_row_count=7,
        cache=cache,
        progress=lambda _message: None,
    )
    assert sum(adapter.fit_calls for adapter in adapters) == 104
    assert len(output.audit_records) == 104
    assert output.oof_probabilities.shape == (len(targets), len(CLASS_LABELS))
    assert output.test_probabilities.shape == (7, len(CLASS_LABELS))
    assert np.allclose(output.oof_probabilities.sum(axis=1), 1.0)
    assert np.allclose(output.test_probabilities.sum(axis=1), 1.0)
    assert all(record["fit_protected_overlap"] == 0 for record in output.audit_records)
    assert all(
        record["fit_predict_overlap"] in {0, None}
        for record in output.audit_records
    )

    cached_adapters = tuple(_FakeAdapter(f"model-{index}") for index in range(4))
    cached_output = run_fully_nested_stacking(
        adapters=cached_adapters,
        targets=targets,
        folds=folds,
        test_row_count=7,
        cache=cache,
        progress=lambda _message: None,
    )
    assert sum(adapter.fit_calls for adapter in cached_adapters) == 0
    assert all(record["cache_hit"] for record in cached_output.audit_records)
    assert np.array_equal(output.oof_probabilities, cached_output.oof_probabilities)
    assert np.array_equal(output.test_probabilities, cached_output.test_probabilities)
