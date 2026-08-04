from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_exp392_is_a_single_feature_adapter_change_on_exp374() -> None:
    config = yaml.safe_load(
        (ROOT / "configs/exp392_range_semantic_indicators.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert config["experiment_id"] == "EXP-392"
    assert config["issue_number"] == 392
    assert config["parent_experiment"] == "EXP-374"
    assert config["features"]["mutation_type"]["parser"]["name"] == (
        "stop_notation_invariant_v2"
    )
    assert config["features"]["residue_position"]["isoform_semantic_mask"][
        "enabled"
    ] is True
    assert config["range_semantic_indicators"]["values"] == [
        "range_stop",
        "range_no_change",
    ]
    assert config["model"]["max_depth"] == 6
    assert "frozen_fold_parameters" not in config
