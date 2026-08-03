from __future__ import annotations

from pathlib import Path

import yaml


def test_exp232_keeps_exp229_outer_training_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    parent = yaml.safe_load(
        (root / "configs/exp229_pathway_mutation_types.yaml").read_text(
            encoding="utf-8"
        )
    )
    candidate = yaml.safe_load(
        (root / "configs/exp232_pathway_group_selection.yaml").read_text(
            encoding="utf-8"
        )
    )

    for key in ("seed", "split", "features", "hotspots", "external_knowledge", "model"):
        assert candidate[key] == parent[key]
    assert candidate["training"]["balanced_sample_weight"] is True
    assert candidate["training"]["checkpoint_selection"] == "macro_f1_validation"
    assert candidate["parent_experiment"] == "EXP-229"


def test_exp232_selector_is_nested_and_does_not_use_test() -> None:
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load(
        (root / "configs/exp232_pathway_group_selection.yaml").read_text(
            encoding="utf-8"
        )
    )
    selector = config["abc_families"]["pathway_group_permutation_selector"]
    assert config["experiment_id"] == "EXP-232"
    assert config["issue_number"] == 232
    assert selector["fit_scope"] == "outer_fold_train_only"
    assert selector["inner_folds"] == 3
    assert selector["minimum_positive_inner_folds"] == 2
    assert "test" not in selector
