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
            "run_adversarial_validation", scripts / "run_adversarial_validation.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


def test_feature_family_and_distribution_classification() -> None:
    module = _load_module()
    assert module.classify_feature_family("TP53__mutated") == "mutated"
    assert module.classify_feature_family("TP53__max_residue_position") == (
        "max_residue_position"
    )
    assert module.classify_feature_family("sample__complex_count") == (
        "sample_burden_aggregate"
    )
    assert module.classify_distribution_kind("TP53__mutated") == "presence"
    assert module.classify_distribution_kind("sample__complex_count") == "continuous"


def test_distribution_summary_preserves_train_test_boundaries() -> None:
    module = _load_module()
    result = module.compute_feature_distribution(
        "TP53__mutated",
        np.asarray([0.0, 1.0, 0.0, 1.0]),
        np.asarray([1.0, 1.0]),
    )
    assert result["train_nonzero"] == 2
    assert result["test_nonzero"] == 2
    assert result["train_prevalence"] == 0.5
    assert result["test_prevalence"] == 1.0
    assert result["prevalence_abs_diff"] == 0.5
    assert result["prevalence_relative_ratio"] == 2.0
