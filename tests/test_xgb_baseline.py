from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from open_cancer.constants import CLASS_LABELS
from open_cancer.xgb_baseline import (
    align_fold_ids,
    encode_fixed_labels,
    load_resolved_baseline_config,
    mutation_presence_matrix,
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
