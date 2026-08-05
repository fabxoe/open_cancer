"""Tests for the EXP-476 leakage and feature contracts."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_exp476_config_feature_pipeline import (  # noqa: E402
    balanced_power_weights,
    build_stateless_features,
    classify_token,
    fit_class_panels,
    normalize_stop,
    select_recurrent_genes,
)


def test_stop_and_unknown_token_semantics() -> None:
    assert normalize_stop("Q30X") == "Q30*"
    assert normalize_stop("Q30Ter") == "Q30*"
    assert classify_token("Q30*") == ("ST", "Q")
    assert classify_token("K16fs") == ("FS", "K")
    assert classify_token("G20G") == ("S", "G")
    assert classify_token("A10V") == ("M", "A")
    assert classify_token("unmappable") == ("MT", None)


def test_missing_is_separate_and_not_mutated() -> None:
    frame = pd.DataFrame(
        {
            "G1": ["", "WT", "A10V"],
            "G2": ["WT", "K16fs", "A10V A11V"],
        }
    )
    gene, engineered, metadata = build_stateless_features(frame, ["G1", "G2"])
    assert gene.shape == (3, 2)
    assert gene.nnz == 3
    assert metadata["blank_cell_count"] == 1
    assert metadata["non_wt_cell_count"] == 3
    assert engineered.shape[0] == 3


def test_recurrent_gene_selection_ignores_validation_rows() -> None:
    base = pd.DataFrame(
        {
            "G1": ["A1V", "A1V", "WT", "WT"],
            "G2": ["WT", "WT", "A1V", "A1V"],
            "G3": ["A1V", "WT", "WT", "WT"],
        }
    )
    changed = base.copy()
    changed.loc[2:, "G2"] = ["A1V A2V", "A1V A2V"]
    matrix_a, _, _ = build_stateless_features(base, ["G1", "G2", "G3"])
    matrix_b, _, _ = build_stateless_features(changed, ["G1", "G2", "G3"])
    fit_rows = np.array([0, 1])
    selected_a = select_recurrent_genes(
        matrix_a, fit_rows, minimum_support=1, maximum_features=2
    )
    selected_b = select_recurrent_genes(
        matrix_b, fit_rows, minimum_support=1, maximum_features=2
    )
    np.testing.assert_array_equal(selected_a, selected_b)


def test_class_panels_ignore_rows_outside_fit_partition() -> None:
    frame = pd.DataFrame(
        {
            "G1": ["A1V", "A1V", "WT", "WT", "WT", "WT"],
            "G2": ["WT", "WT", "A1V", "A1V", "WT", "WT"],
            "G3": ["WT", "WT", "WT", "WT", "A1V", "A1V"],
        }
    )
    altered = frame.copy()
    altered.loc[4:, "G1"] = ["A1V", "A1V"]
    target = np.array([0, 0, 1, 1, 0, 1], dtype=np.int32)
    fit_rows = np.array([0, 1, 2, 3], dtype=np.int32)
    matrix_a, _, _ = build_stateless_features(frame, ["G1", "G2", "G3"])
    matrix_b, _, _ = build_stateless_features(altered, ["G1", "G2", "G3"])
    panels_a = fit_class_panels(
        matrix_a, target, fit_rows, top_k=1, minimum_support=1
    )
    panels_b = fit_class_panels(
        matrix_b, target, fit_rows, top_k=1, minimum_support=1
    )
    for panel_a, panel_b in zip(panels_a, panels_b):
        np.testing.assert_array_equal(panel_a, panel_b)


def test_weight_power_is_normalized_and_more_aggressive() -> None:
    target = np.array([0, 0, 0, 0, 1], dtype=np.int32)
    balanced = balanced_power_weights(target, 1.0)
    aggressive = balanced_power_weights(target, 1.15)
    assert np.isclose(balanced.mean(), 1.0)
    assert np.isclose(aggressive.mean(), 1.0)
    assert aggressive[target == 1][0] > balanced[target == 1][0]
