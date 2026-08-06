"""Unit tests for the distribution-oriented feature pipeline."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "scripts"
    / "run_exp513_data_variation_distribution_concentration.py"
)

SPEC = importlib.util.spec_from_file_location(
    "run_exp513_data_variation_distribution_concentration",
    MODULE_PATH,
)
assert SPEC is not None
assert SPEC.loader is not None

MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_no_event_policy() -> None:
    for value in ("WT", "", "N/A", "wild_type"):
        assert MODULE.split_tokens(value) == ()
    assert MODULE.split_tokens("A10V") == ("A10V",)


def test_event_family_mapping() -> None:
    assert MODULE.classify_token("A10fs") == "FRAMESHIFT"
    assert MODULE.classify_token("Q20*") == "STOP"
    assert MODULE.classify_token("Splice_Site") == "SPLICE"
    assert MODULE.classify_token("G30G") == "SYNONYMOUS"
    assert MODULE.classify_token("A10del") == "INDEL"
    assert MODULE.classify_token("A10V") == "MISSENSE"
    assert MODULE.classify_token("unparsed") == "OTHER"


def test_concentration_statistics_are_order_invariant() -> None:
    first = MODULE.concentration_statistics(np.array([3, 1, 0, 2]))
    second = MODULE.concentration_statistics(np.array([2, 0, 3, 1]))
    assert np.allclose(first, second)


def test_feature_builder_does_not_count_blank_as_mutation() -> None:
    frame = pd.DataFrame(
        {
            "ID": ["S1", "S2", "S3"],
            "GENE_A": ["WT", "A10V", ""],
            "GENE_B": ["Q20*", "A11fs A12V", "WT"],
        }
    )
    config = {
        "count_clip": 9,
        "include_gene_presence": True,
        "include_gene_event_count": True,
        "include_gene_truncating_presence": True,
        "include_gene_multi_event_presence": True,
    }
    bundle = MODULE.build_features(frame, ["GENE_A", "GENE_B"], config)
    assert bundle.matrix.shape[0] == 3
    assert bundle.qc["non_wt_cell_count"] == 3
    assert bundle.qc["family_occurrences"]["FRAMESHIFT"] == 1
    assert bundle.qc["family_occurrences"]["STOP"] == 1


def test_support_selection_uses_only_supplied_training_rows() -> None:
    matrix = MODULE.sparse.csr_matrix(
        np.array([[1, 0, 0], [1, 1, 0], [0, 1, 1]], dtype=np.float32)
    )
    selected = MODULE.select_supported_features(matrix, np.array([0, 1]), minimum=2)
    assert selected.tolist() == [0]


def test_weight_power_is_normalized() -> None:
    y = np.array([0, 0, 0, 1])
    weights = MODULE.sample_weights(y, power=0.75)
    assert np.isclose(weights.mean(), 1.0)
    assert weights[y == 1][0] > weights[y == 0][0]
