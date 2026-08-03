from __future__ import annotations

from pathlib import Path

import yaml


def test_exp250_identity_and_outer_train_selection_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load(
        (root / "configs/exp250_lineage_group_selection.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert config["experiment_id"] == "EXP-250"
    assert config["issue_number"] == 250
    assert config["parent_experiment"] == "EXP-245"
    selector = config["abc_families"]["lineage_group_permutation_selector"]
    assert selector["fit_scope"] == "outer_fold_train_only"
    assert selector["inner_folds"] == 3
    assert selector["minimum_positive_inner_folds"] == 2
