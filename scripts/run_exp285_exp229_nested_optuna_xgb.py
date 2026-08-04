#!/usr/bin/env python
"""Run EXP-285: nested Optuna tuning of the fixed EXP-229 feature policy."""

from __future__ import annotations

import yaml

from open_cancer.nested_optuna import NestedOptunaFoldTuner
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp285_exp229_nested_optuna_xgb.yaml"
ARTIFACT_SLUG = "exp285_exp229_nested_optuna_xgb"


if __name__ == "__main__":
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    tuning = config["nested_optuna"]
    main(
        CONFIG,
        fold_feature_builder=PathwayMutationTypeFoldBuilder(
            membership_path=(
                ROOT / "reports" / ARTIFACT_SLUG / "pathway_membership.json"
            )
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
        ),
        runner_command=(
            "uv run --group experiment python "
            "scripts/run_exp285_exp229_nested_optuna_xgb.py"
        ),
    )
