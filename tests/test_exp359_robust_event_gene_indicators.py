from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FoldFeatureBundle


def _load_runner():
    root = Path(__file__).resolve().parents[1]
    scripts = root / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location(
            "run_exp359_test", scripts / "run_exp359_robust_event_gene_indicators.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


def test_exp359_builder_replaces_gene_complex_but_preserves_sample_complex(monkeypatch) -> None:
    module = _load_runner()

    class FakePathwayBuilder:
        def __init__(self) -> None:
            self.gene_columns = ("G1", "G2")
            self.train = pd.DataFrame(
                {
                    "ID": ["A", "B", "C", "D"],
                    "SUBCLASS": ["X", "Y", "X", "Y"],
                    "G1": ["R213X", "P2del", "WT", "R4H"],
                    "G2": ["WT", "Q3*", "A4_B5insA", "WT"],
                }
            )
            self.test = pd.DataFrame(
                {"ID": ["E"], "G1": ["P2del"], "G2": ["R3X"]}
            )

        def __call__(self, **kwargs):
            return FoldFeatureBundle(
                train=sparse.csr_matrix((len(kwargs["train_indices"]), 1)),
                validation=sparse.csr_matrix((len(kwargs["valid_indices"]), 1)),
                test=sparse.csr_matrix((len(self.test), 1)),
                fitted_families=(),
                feature_names=("pathway_extra",),
                registry={},
            )

    monkeypatch.setattr(module, "PathwayMutationTypeFoldBuilder", FakePathwayBuilder)
    builder = module.RobustEventGeneIndicatorFoldBuilder()
    bundle = builder(
        fold=0,
        train_indices=np.asarray([0, 1, 2], dtype=np.int32),
        valid_indices=np.asarray([3], dtype=np.int32),
        base_train=sparse.csr_matrix((3, 4), dtype=np.float32),
        base_validation=sparse.csr_matrix((1, 4), dtype=np.float32),
        base_test=sparse.csr_matrix((1, 4), dtype=np.float32),
        base_feature_names=(
            "sample__complex_count",
            "G1__complex",
            "G2__complex",
            "other",
        ),
        target=np.asarray([0, 1, 0]),
    )

    assert bundle.base_feature_names_to_drop == ("G1__complex", "G2__complex")
    assert "sample__complex_count" not in bundle.base_feature_names_to_drop
    assert bundle.registry["base_feature_replacement"]["drop_count"] == 2
    assert bundle.registry["base_feature_replacement"]["add_count"] == 12
    assert bundle.registry["base_feature_replacement"]["preserve_sample_complex_count"]
    assert bundle.train.shape[0] == 3
    assert bundle.validation.shape[0] == 1
    assert bundle.test.shape[0] == 1
