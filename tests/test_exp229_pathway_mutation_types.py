from __future__ import annotations

from pathlib import Path

import yaml


def test_exp229_keeps_exp223_training_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    parent = yaml.safe_load(
        (root / "configs/exp223_pathway_macro_f1_checkpoint.yaml").read_text(
            encoding="utf-8"
        )
    )
    candidate = yaml.safe_load(
        (root / "configs/exp229_pathway_mutation_types.yaml").read_text(
            encoding="utf-8"
        )
    )

    for key in ("seed", "split", "features", "hotspots", "external_knowledge", "model"):
        assert candidate[key] == parent[key]
    assert candidate["training"]["balanced_sample_weight"] is True
    assert candidate["training"]["checkpoint_selection"] == "macro_f1_validation"
    assert candidate["parent_experiment"] == "EXP-223"
    family = candidate["abc_families"]["pathway_mutation_type_composition"]
    assert family["candidate_output_dimension"] == 50
    assert family["fit_scope"] == "stateless"


def test_exp229_uses_issue_derived_identity() -> None:
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load(
        (root / "configs/exp229_pathway_mutation_types.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert config["experiment_id"] == "EXP-229"
    assert config["issue_number"] == 229
