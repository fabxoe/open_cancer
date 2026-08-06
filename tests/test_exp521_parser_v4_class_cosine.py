from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_exp521_identity_and_fold_safe_contract() -> None:
    config = yaml.safe_load(
        (ROOT / "configs" / "exp521_parser_v4_class_cosine.yaml").read_text()
    )
    assert config["experiment_id"] == "EXP-521"
    assert config["issue_number"] == 521
    assert config["parent_experiment"] == "EXP-374"
    assert config["features"]["class_profile"]["method"] == "cosine"
    assert config["features"]["class_profile"]["fit_scope"] == "outer_train_only"
    assert config["features"]["parser_v4_patient_semantic_vector"]["include_directly_in_model"] is False
