from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_exp527_identity_and_leave_one_out_contract() -> None:
    config = yaml.safe_load(
        (ROOT / "configs" / "exp527_parser_v4_class_cosine_loo.yaml").read_text()
    )
    assert config["experiment_id"] == "EXP-527"
    assert config["issue_number"] == 527
    assert config["parent_experiment"] == "EXP-521"
    profile = config["features"]["class_profile"]
    assert profile["method"] == "cosine"
    assert profile["fit_scope"] == "outer_train_only"
    assert profile["train_transform"] == "leave_one_out_target_class"
    assert profile["validation_test_transform"] == "full_outer_train_centroid"
    assert (
        config["features"]["parser_v4_patient_semantic_vector"][
            "include_directly_in_model"
        ]
        is False
    )
