from __future__ import annotations

import numpy as np
import pytest

from open_cancer.nested_optuna import (
    inner_splits,
    remaining_trial_count,
    suggest_xgboost_parameters,
)


class FakeTrial:
    number = 0

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def suggest_int(self, name, low, high):
        self.calls.append(("int", name, low, high))
        return low

    def suggest_float(self, name, low, high, *, log=False):
        self.calls.append(("float", name, low, high, log))
        return low

    def set_user_attr(self, key, value):
        pass


def test_search_space_is_pre_registered() -> None:
    trial = FakeTrial()
    parameters = suggest_xgboost_parameters(trial)
    assert parameters == {
        "max_depth": 4,
        "min_child_weight": 1.0,
        "subsample": 0.5,
        "colsample_bytree": 0.5,
        "reg_alpha": 0.0,
        "reg_lambda": 0.5,
        "learning_rate": 0.02,
    }
    assert trial.calls[-1] == ("float", "learning_rate", 0.02, 0.08, True)


def test_native_v3_regularized_search_space_is_explicit() -> None:
    trial = FakeTrial()
    parameters = suggest_xgboost_parameters(
        trial,
        {
            "max_depth": [3, 7],
            "min_child_weight": [2.0, 20.0],
            "subsample": [0.6, 0.9],
            "colsample_bytree": [0.25, 0.75],
            "reg_alpha": [0.0, 2.0],
            "reg_lambda": [1.0, 12.0],
            "learning_rate": [0.02, 0.08, "log"],
            "gamma": [0.0, 0.5],
        },
    )
    assert parameters == {
        "max_depth": 3,
        "min_child_weight": 2.0,
        "subsample": 0.6,
        "colsample_bytree": 0.25,
        "reg_alpha": 0.0,
        "reg_lambda": 1.0,
        "learning_rate": 0.02,
        "gamma": 0.0,
    }
    assert trial.calls[-1] == ("float", "gamma", 0.0, 0.5, False)


def test_inner_splits_are_deterministic_disjoint_and_complete() -> None:
    target = np.repeat(np.arange(4), 9)
    first = inner_splits(target, outer_fold=2, seed=42, n_splits=3)
    second = inner_splits(target, outer_fold=2, seed=42, n_splits=3)
    seen = []
    for (train_a, valid_a), (train_b, valid_b) in zip(first, second, strict=True):
        assert np.array_equal(train_a, train_b)
        assert np.array_equal(valid_a, valid_b)
        assert set(train_a).isdisjoint(set(valid_a))
        seen.extend(valid_a.tolist())
        assert np.bincount(target[valid_a], minlength=4).tolist() == [3, 3, 3, 3]
    assert sorted(seen) == list(range(len(target)))


@pytest.mark.parametrize(
    ("existing", "requested", "expected"),
    [(0, 30, 30), (12, 30, 18), (30, 30, 0), (31, 30, 0)],
)
def test_remaining_trial_count(existing: int, requested: int, expected: int) -> None:
    assert remaining_trial_count(existing, requested) == expected
