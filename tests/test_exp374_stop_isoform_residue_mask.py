from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_exp374_is_a_single_mask_change_on_exp369() -> None:
    config = yaml.safe_load(
        (ROOT / "configs/exp374_stop_isoform_residue_mask.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert config["experiment_id"] == "EXP-374"
    assert config["issue_number"] == 374
    assert config["parent_experiment"] == "EXP-369"
    assert config["features"]["mutation_type"]["parser"]["name"] == (
        "stop_notation_invariant_v2"
    )
    mask = config["features"]["residue_position"]["isoform_semantic_mask"]
    assert mask["enabled"] is True
    assert mask["trusted_categories"] == [
        "CANONICAL_MATCH",
        "MANE_MATCH",
        "OTHER_ISOFORM_MATCH",
    ]
    assert config["model"]["max_depth"] == 6
    assert "frozen_fold_parameters" not in config
