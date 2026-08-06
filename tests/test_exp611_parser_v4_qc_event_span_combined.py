from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from exp571_data_centric_feature_builders import (  # noqa: E402
    EVENT_SPAN_NAMES,
    PARSER_QC_NAMES,
    summarize_tokens,
)
from exp611_parser_v4_qc_event_span_combined_features import (  # noqa: E402
    COMBINED_FEATURE_NAMES,
)


def test_combined_family_is_exact_union_of_exp571_families() -> None:
    assert COMBINED_FEATURE_NAMES == PARSER_QC_NAMES + EVENT_SPAN_NAMES
    assert len(COMBINED_FEATURE_NAMES) == 12
    assert len(set(COMBINED_FEATURE_NAMES)) == 12


def test_combined_summaries_are_finite_and_stateless() -> None:
    qc, span = summarize_tokens(("A10V", "A10_A15del", "unusual"))
    combined = np.concatenate((qc, span))
    assert combined.shape == (len(COMBINED_FEATURE_NAMES),)
    assert np.isfinite(combined).all()


def test_config_freezes_parent_model_and_canonical_split() -> None:
    config_path = ROOT / "configs/exp611_parser_v4_qc_event_span_combined.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert config["experiment_id"] == "EXP-611"
    assert config["issue_number"] == 611
    assert config["parent_experiment"] == "EXP-571"
    assert config["split"]["path"] == (
        "data/splits/stratified_5fold_seed42.csv"
    )
    assert config["split"]["n_splits"] == 5
    assert config["features"]["combined_families"] == [
        "parser_status_ratios",
        "parser_event_span_summary",
    ]
    assert config["model"]["parameters"]["deterministic"] is True
