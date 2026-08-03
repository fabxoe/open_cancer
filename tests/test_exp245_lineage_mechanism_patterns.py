from __future__ import annotations

from pathlib import Path

import yaml


def test_exp245_keeps_exp229_training_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    parent = yaml.safe_load(
        (root / "configs/exp229_pathway_mutation_types.yaml").read_text(
            encoding="utf-8"
        )
    )
    candidate = yaml.safe_load(
        (root / "configs/exp245_lineage_mechanism_patterns.yaml").read_text(
            encoding="utf-8"
        )
    )
    for key in ("seed", "split", "features", "hotspots", "model"):
        assert candidate[key] == parent[key]
    assert candidate["training"]["balanced_sample_weight"] is True
    assert candidate["training"]["checkpoint_selection"] == "macro_f1_validation"
    assert candidate["parent_experiment"] == "EXP-229"
    family = candidate["abc_families"]["lineage_mechanism_patterns"]
    assert family["candidate_output_dimension"] == 32
    assert family["fit_scope"] == "stateless"


def test_exp245_uses_issue_derived_identity_and_no_exp240_features() -> None:
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load(
        (root / "configs/exp245_lineage_mechanism_patterns.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert config["experiment_id"] == "EXP-245"
    assert config["issue_number"] == 245
    assert "EXP-240" not in config["component_experiments"]
    assert "fixed_literature_molecular_constellations" not in config["training"][
        "feature_types"
    ]
