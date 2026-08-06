from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_exp522_identity_and_fold_safe_contract() -> None:
    config = yaml.safe_load(
        (ROOT / "configs" / "exp522_parser_v4_class_likelihood.yaml").read_text()
    )
    assert config["experiment_id"] == "EXP-522"
    assert config["issue_number"] == 522
    assert config["parent_experiment"] == "EXP-374"
    profile = config["features"]["class_profile"]
    assert profile["method"] == "mean_log_likelihood"
    assert profile["fit_scope"] == "outer_train_only"
    assert profile["alpha"] == 1.0
    assert profile["include_class_prior"] is False
    assert (
        config["features"]["parser_v4_patient_semantic_vector"][
            "include_directly_in_model"
        ]
        is False
    )
