from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy import sparse

from open_cancer.constants import CLASS_LABELS
from open_cancer.xgb_baseline import (
    align_fold_ids,
    correlated_gene_weights,
    encode_fixed_labels,
    load_resolved_baseline_config,
    mutation_presence_matrix,
    select_correlated_genes,
    select_gene_columns,
    weighted_gene_burden,
    weighted_protect_burden,
)


def test_config_uses_defaults_and_minimal_overrides(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(
        "experiment:\n  slug: test\nmodel:\n  use_balanced_sample_weight: true\n",
        encoding="utf-8",
    )

    config = load_resolved_baseline_config(path)

    assert config["experiment"]["slug"] == "test"
    assert config["run"]["seed"] == 42
    assert config["features"]["include_mutation_burden"] is False
    assert config["model"]["use_balanced_sample_weight"] is True
    assert config["model"]["params"]["early_stopping_rounds"] == 50


def test_mutation_presence_encodes_wt_and_empty_as_zero() -> None:
    frame = pd.DataFrame(
        {
            "G1": ["WT", "", "R175H"],
            "G2": ["V600E", "WT", "A B"],
        }
    )

    matrix = mutation_presence_matrix(frame, ["G1", "G2"])

    assert matrix.dtype == np.float32
    assert matrix.toarray().tolist() == [[0.0, 1.0], [0.0, 0.0], [1.0, 1.0]]


def test_fixed_label_encoding_uses_project_order() -> None:
    encoded = encode_fixed_labels(pd.Series([CLASS_LABELS[-1], CLASS_LABELS[0]]))

    assert encoded.tolist() == [len(CLASS_LABELS) - 1, 0]


def test_select_gene_columns_filters_and_preserves_train_order(tmp_path: Path) -> None:
    whitelist_path = tmp_path / "whitelist.csv"
    whitelist_path.write_text("gene\nG3\nG1\n", encoding="utf-8")

    selected = select_gene_columns(["G1", "G2", "G3", "G4"], whitelist_path)

    assert selected == ["G1", "G3"]


def test_select_gene_columns_rejects_unknown_gene(tmp_path: Path) -> None:
    whitelist_path = tmp_path / "whitelist.csv"
    whitelist_path.write_text("gene\nG1\nG99\n", encoding="utf-8")

    with pytest.raises(ValueError, match="G99"):
        select_gene_columns(["G1", "G2"], whitelist_path)


def test_select_gene_columns_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        select_gene_columns(["G1"], tmp_path / "missing.csv")


def test_select_correlated_genes_picks_highest_absolute_correlation() -> None:
    gene_columns = ["P1", "P2", "C1", "C2", "C3"]
    matrix = sparse.csr_matrix(
        np.array(
            [
                [1, 1, 1, 0, 1],
                [1, 0, 1, 0, 0],
                [0, 1, 1, 0, 1],
                [0, 0, 0, 0, 0],
                [0, 0, 0, 0, 1],
                [1, 1, 1, 0, 0],
            ],
            dtype=np.float32,
        )
    )

    selected = select_correlated_genes(matrix, gene_columns, {"P1", "P2"}, top_k=1)

    assert selected == ["C1"]


def test_select_correlated_genes_rejects_top_k_out_of_range() -> None:
    gene_columns = ["P1", "C1", "C2"]
    matrix = sparse.csr_matrix(np.zeros((3, 3), dtype=np.float32))

    with pytest.raises(ValueError, match="top_k"):
        select_correlated_genes(matrix, gene_columns, {"P1"}, top_k=5)


def test_select_correlated_genes_requires_protect_gene_overlap() -> None:
    gene_columns = ["C1", "C2"]
    matrix = sparse.csr_matrix(np.zeros((2, 2), dtype=np.float32))

    with pytest.raises(ValueError, match="protect_genes"):
        select_correlated_genes(matrix, gene_columns, {"P1"}, top_k=1)


def test_correlated_gene_weights_reports_absolute_correlation() -> None:
    gene_columns = ["P1", "P2", "C1", "C2", "C3"]
    matrix = sparse.csr_matrix(
        np.array(
            [
                [1, 1, 1, 0, 1],
                [1, 0, 1, 0, 0],
                [0, 1, 1, 0, 1],
                [0, 0, 0, 0, 0],
                [0, 0, 0, 0, 1],
                [1, 1, 1, 0, 0],
            ],
            dtype=np.float32,
        )
    )

    weights = correlated_gene_weights(matrix, gene_columns, {"P1", "P2"}, top_k=1)

    assert list(weights) == ["C1"]
    assert weights["C1"] == pytest.approx(0.8660254, abs=1e-6)


def test_weighted_gene_burden_ignores_genes_outside_weights() -> None:
    gene_columns = ["G1", "G2", "G3"]
    matrix = sparse.csr_matrix(
        np.array([[1, 1, 1], [0, 1, 1], [1, 0, 0]], dtype=np.float32)
    )

    burden = weighted_gene_burden(matrix, gene_columns, {"G1": 2.0, "G3": 0.5})

    assert burden.tolist() == pytest.approx([2.5, 0.5, 2.0])


def test_weighted_protect_burden_sums_protect_and_correlated_contributions() -> None:
    gene_columns = ["P1", "C1"]
    matrix = sparse.csr_matrix(
        np.array([[1, 0], [0, 1], [1, 1]], dtype=np.float32)
    )

    burden = weighted_protect_burden(matrix, gene_columns, {"P1"}, {"C1": 0.5})

    assert burden.tolist() == pytest.approx([1.0, 0.5, 1.5])


def test_fold_alignment_follows_train_order() -> None:
    train_ids = pd.Series(["B", "A", "C", "D"])
    fold_table = pd.DataFrame(
        {
            "ID": ["A", "B", "C", "D"],
            "fold": [0, 1, 0, 1],
        }
    )

    fold_ids = align_fold_ids(train_ids, fold_table, n_splits=2)

    assert fold_ids.tolist() == [1, 0, 0, 1]
