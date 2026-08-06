from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


def _load_module():
    root = Path(__file__).resolve().parents[1]
    scripts = root / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location(
            "audit_train_only_stress_subgroup_support",
            scripts / "audit_train_only_stress_subgroup_support.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


def test_bucket_counts_partitions_without_overlap() -> None:
    module = _load_module()
    values = np.array([0.0, 1.0, 5.0, 5.0, 9.0, 10.0, 20.0])
    counts = module.bucket_counts(
        values,
        {
            "<=q10": (-np.inf, 5.0),
            "q10-q90": (5.0, 10.0),
            ">q90": (10.0, np.inf),
        },
    )
    assert counts == {"<=q10": 3, "q10-q90": 3, ">q90": 1}
    assert sum(counts.values()) == len(values)


def test_min_usable_positive_rows_threshold_is_positive() -> None:
    module = _load_module()
    assert module.MIN_USABLE_POSITIVE_ROWS > 0
