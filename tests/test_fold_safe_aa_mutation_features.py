"""Unit tests for the EXP-439 stateless feature contract."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_exp439_fold_safe_aa_mutation_xgb import (  # noqa: E402
    build_stateless_features,
    classify_mutation_token,
    engineered_feature_names,
    normalize_stop_notation_token,
    select_gene_indices,
)


def test_stop_notation_and_event_classification() -> None:
    """X/Ter/* must share ST semantics without guessing complex tokens."""
    assert normalize_stop_notation_token("Q30Ter") == "Q30*"
    assert normalize_stop_notation_token("Q30X") == "Q30*"
    assert classify_mutation_token("Q30*") == ("ST", "Q")
    assert classify_mutation_token("A10V") == ("M", "A")
    assert classify_mutation_token("G20G") == ("S", "G")
    assert classify_mutation_token("K16fs") == ("FS", "K")
    assert classify_mutation_token("delins") == ("MT", None)
    assert classify_mutation_token("A10V", multi_token=True) == ("MT", "A")


def test_stateless_matrix_has_expected_counts_and_missing_policy() -> None:
    """WT, blanks, single tokens and multi-token cells remain distinguishable."""
    frame = pd.DataFrame(
        {
            "GENE_A": ["WT", "A10V", "Q30Ter", ""],
            "GENE_B": ["G20G", "K16fs", "A10V A11V", "WT"],
        }
    )
    gene, engineered, metadata = build_stateless_features(
        frame,
        ["GENE_A", "GENE_B"],
    )
    assert gene.shape == (4, 2)
    assert gene.nnz == 5
    assert engineered.shape == (4, len(engineered_feature_names()))
    assert metadata["non_wt_cell_count"] == 5
    assert metadata["blank_cell_count"] == 1
    assert metadata["raw_event_count"] == 6


def test_gene_selector_uses_only_supplied_training_rows() -> None:
    """Changing validation-only rows must not alter fold-train selection."""
    frame_a = pd.DataFrame(
        {
            "G1": ["A1V", "A1V", "WT", "WT"],
            "G2": ["WT", "WT", "A1V", "A1V"],
            "G3": ["A1V", "WT", "WT", "WT"],
        }
    )
    frame_b = frame_a.copy()
    frame_b.loc[2:, "G2"] = ["A1V A2V", "A1V A2V"]
    gene_a, _, _ = build_stateless_features(frame_a, ["G1", "G2", "G3"])
    gene_b, _, _ = build_stateless_features(frame_b, ["G1", "G2", "G3"])
    train_rows = np.array([0, 1], dtype=np.int32)
    selected_a = select_gene_indices(
        gene_a,
        train_rows,
        minimum_support=1,
        top_n=2,
    )
    selected_b = select_gene_indices(
        gene_b,
        train_rows,
        minimum_support=1,
        top_n=2,
    )
    np.testing.assert_array_equal(selected_a, selected_b)
    np.testing.assert_array_equal(selected_a, np.array([0, 2], dtype=np.int32))
