from __future__ import annotations

from pathlib import Path

import yaml


def test_exp240_keeps_exp229_training_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    parent = yaml.safe_load(
        (root / "configs/exp229_pathway_mutation_types.yaml").read_text(
            encoding="utf-8"
        )
    )
    candidate = yaml.safe_load(
        (root / "configs/exp240_molecular_constellations.yaml").read_text(
            encoding="utf-8"
        )
    )
    for key in ("seed", "split", "features", "hotspots", "model"):
        assert candidate[key] == parent[key]
    assert candidate["training"]["balanced_sample_weight"] is True
    assert candidate["training"]["checkpoint_selection"] == "macro_f1_validation"
    assert candidate["parent_experiment"] == "EXP-229"
    family = candidate["abc_families"]["molecular_constellation"]
    assert family["candidate_output_dimension"] == 21
    assert family["fit_scope"] == "stateless"


def test_exp240_uses_issue_derived_identity_and_fixed_knowledge_scope() -> None:
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load(
        (root / "configs/exp240_molecular_constellations.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert config["experiment_id"] == "EXP-240"
    assert config["issue_number"] == 240
    assert (
        config["external_knowledge"]["lineage_module_data_scope"]
        == "fixed_relations_only_no_external_patient_data"
    )
