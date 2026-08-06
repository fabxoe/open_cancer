from __future__ import annotations

from pathlib import Path


def test_generalized_lightgbm_runner_has_no_fixed_exp449_identity() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "scripts" / "run_exp449_lightgbm_exp374.py").read_text()
    assert 'expected_experiment_id = str(config["experiment_id"])' in text
    assert "FOLD_BUILDER_FACTORY()" in text
    assert "RUNNER_COMMAND" in text


def test_ablation_builder_modes_are_explicit() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "scripts" / "exp527_lightgbm_ablation_builders.py").read_text()
    assert "build_parser_only_features" in text
    assert "build_cosine_only_features" in text
    assert "build_parser_plus_cosine_features" in text
    assert "base_feature_names_to_drop=tuple(base_feature_names)" in text
