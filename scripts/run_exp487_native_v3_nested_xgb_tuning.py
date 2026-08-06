#!/usr/bin/env python
"""Run EXP-487: nested XGBoost tuning of parser native-v3 semantics."""

from __future__ import annotations

import yaml

from open_cancer.nested_optuna import NestedOptunaFoldTuner
from open_cancer.parser_baseline_features import (
    ParserBaselineFoldBuilder,
    validate_controlled_parser_baseline_config,
)
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
)
from run_hotspot_xgb import ROOT, TEST_PATH, TRAIN_PATH, main


CONFIG = ROOT / "configs" / "exp487_native_v3_nested_xgb_tuning.yaml"
ARTIFACT_SLUG = "exp487_native_v3_nested_xgb_tuning"


if __name__ == "__main__":
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    representation = validate_controlled_parser_baseline_config(config)
    tuning = config["nested_optuna"]
    main(
        CONFIG,
        fold_feature_builder=ParserBaselineFoldBuilder(
            representation=representation,
            train_path=TRAIN_PATH,
            test_path=TEST_PATH,
        ),
        fold_model_tuner=NestedOptunaFoldTuner(
            artifact_slug=ARTIFACT_SLUG,
            root=ROOT,
            n_trials=int(tuning["n_trials_per_outer_fold"]),
            inner_n_splits=int(tuning["inner_n_splits"]),
            seed=int(config["seed"]),
            balanced_sample_weight=bool(
                config["training"]["balanced_sample_weight"]
            ),
            search_space=tuning["search_space"],
            tie_break_inner_std=True,
        ),
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        runner_command=(
            "uv run --group experiment python "
            "scripts/run_exp487_native_v3_nested_xgb_tuning.py"
        ),
    )
