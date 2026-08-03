from __future__ import annotations

from pathlib import Path

import yaml


def test_exp253_identity_and_fixed_components() -> None:
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load(
        (root / "configs/exp253_lightgbm_xgboost_blend.yaml").read_text(
            encoding="utf-8"
        )
    )
    runner = (root / "scripts/run_exp253_lightgbm_xgboost_blend.py").read_text(
        encoding="utf-8"
    )

    assert config["experiment_id"] == "EXP-253"
    assert config["issue_number"] == 253
    assert [item["experiment_id"] for item in config["ensemble"]["components"]] == [
        "EXP-209",
        "EXP-229",
    ]
    assert [item["weight"] for item in config["ensemble"]["components"]] == [0.5, 0.5]
    assert config["split"]["path"] == "data/splits/stratified_5fold_seed42.csv"
    assert "EXP-253" in runner
    assert "EXP-209" in runner and "EXP-229" in runner
