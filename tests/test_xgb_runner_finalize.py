from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
from scipy import sparse

from open_cancer.feature_family import FoldFeatureBundle


def _load_runner_module():
    root = Path(__file__).resolve().parents[1]
    scripts = root / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location(
            "run_hotspot_xgb_finalize_test", scripts / "run_hotspot_xgb.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


def test_finalize_rebuilds_fold_specific_test_matrices() -> None:
    runner = _load_runner_module()
    train = sparse.csr_matrix(np.arange(24, dtype=np.float32).reshape(6, 4))
    test = sparse.csr_matrix(np.arange(8, dtype=np.float32).reshape(2, 4))
    folds = np.asarray([0, 1, 2, 0, 1, 2], dtype=np.int32)
    target = np.asarray([0, 1, 2, 1, 2, 0], dtype=np.int32)
    calls: list[tuple[int, tuple[int, ...]]] = []

    def builder(**kwargs):
        fold = int(kwargs["fold"])
        calls.append((fold, tuple(kwargs["target"].tolist())))
        extra_test = sparse.csr_matrix(
            np.full((test.shape[0], 1), fold + 10, dtype=np.float32)
        )
        return FoldFeatureBundle(
            train=sparse.csr_matrix((len(kwargs["train_indices"]), 1)),
            validation=sparse.csr_matrix((len(kwargs["valid_indices"]), 1)),
            test=extra_test,
            fitted_families=(),
            feature_names=(f"fold_{fold}",),
            registry={},
        )

    rebuilt = runner.rebuild_fold_test_features(
        fold_feature_builder=builder,
        fold_assignments=folds,
        target=target,
        train_features=train,
        test_features=test,
        feature_names=("a", "b", "c", "d"),
        n_splits=3,
    )
    assert calls == [(0, (1, 2, 2, 0)), (1, (0, 2, 1, 0)), (2, (0, 1, 1, 2))]
    for fold, matrix in enumerate(rebuilt):
        assert matrix.shape == (2, 5)
        np.testing.assert_array_equal(matrix[:, -1].toarray().ravel(), fold + 10)


def test_finalize_rejects_misaligned_base_features() -> None:
    runner = _load_runner_module()
    with np.testing.assert_raises_regex(ValueError, "이름 수와 열 수"):
        runner.rebuild_fold_test_features(
            fold_feature_builder=lambda **_: None,
            fold_assignments=np.asarray([0, 1]),
            target=np.asarray([0, 1]),
            train_features=sparse.csr_matrix((2, 2)),
            test_features=sparse.csr_matrix((1, 2)),
            feature_names=("only_one",),
            n_splits=2,
        )
