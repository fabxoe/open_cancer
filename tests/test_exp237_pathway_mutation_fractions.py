from __future__ import annotations

from pathlib import Path

import yaml


def test_exp237_keeps_exp229_model_and_split_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    parent = yaml.safe_load(
        (root / "configs/exp229_pathway_mutation_types.yaml").read_text(
            encoding="utf-8"
        )
    )
    candidate = yaml.safe_load(
        (root / "configs/exp237_pathway_mutation_fractions.yaml").read_text(
            encoding="utf-8"
        )
    )

    for key in ("seed", "split", "features", "hotspots", "external_knowledge", "model"):
        assert candidate[key] == parent[key]
    assert candidate["training"]["balanced_sample_weight"] is True
    assert candidate["training"]["checkpoint_selection"] == "macro_f1_validation"
    assert candidate["parent_experiment"] == "EXP-229"


def test_exp237_fraction_contract_is_fixed_before_execution() -> None:
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load(
        (root / "configs/exp237_pathway_mutation_fractions.yaml").read_text(
            encoding="utf-8"
        )
    )
    family = config["abc_families"]["pathway_mutation_type_fraction"]
    assert config["experiment_id"] == "EXP-237"
    assert config["issue_number"] == 237
    assert family["denominator"] == "pathway_mutated_gene_count"
    assert family["zero_denominator"] == 0.0
    assert family["candidate_output_dimension"] == 50
