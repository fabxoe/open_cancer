from __future__ import annotations

import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from exp571_data_centric_feature_builders import (  # noqa: E402
    PARSER_QC_NAMES,
    build_parser_qc_features,
)
from run_exp620_lightgbm_regularization_multiseed import (  # noqa: E402
    EXPECTED_EXPERIMENT_ID,
    EXPECTED_ISSUE_NUMBER,
)


CONFIG_PATH = ROOT / "configs/exp620_lightgbm_regularization_multiseed.yaml"


def load_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_experiment_identity_matches_issue() -> None:
    config = load_config()
    assert config["experiment_id"] == EXPECTED_EXPERIMENT_ID == "EXP-620"
    assert config["issue_number"] == EXPECTED_ISSUE_NUMBER == 620
    assert config["parent_experiment"] == "EXP-571"


def test_canonical_split_and_parent_features_are_frozen() -> None:
    config = load_config()
    assert config["split"] == {
        "path": "data/splits/stratified_5fold_seed42.csv",
        "n_splits": 5,
    }
    assert config["features"]["added_family"] == "parser_status_ratios"
    assert config["features"]["event_span_enabled"] is False
    assert len(PARSER_QC_NAMES) == 5
    assert callable(build_parser_qc_features)


def test_regularization_preset_is_more_conservative_than_parent() -> None:
    parameters = load_config()["model"]["parameters"]
    assert parameters["num_leaves"] == 23
    assert parameters["max_depth"] == 7
    assert parameters["min_child_samples"] == 30
    assert parameters["reg_alpha"] == 0.2
    assert parameters["reg_lambda"] == 3.0
    assert parameters["deterministic"] is True
    assert parameters["force_col_wise"] is True


def test_seed42_is_official_and_other_seeds_are_diagnostic() -> None:
    training = load_config()["training"]
    assert training["official_seed"] == 42
    assert training["diagnostic_seeds"] == [142, 242]
    assert training["test_used_for_fit"] is False
    assert training["public_lb_used_for_selection"] is False
