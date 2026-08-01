#!/usr/bin/env python
"""Run EXP-131: extended CatBoost training on frozen Feature Spec v1."""

from run_exp123_sparse_logistic_v1 import ROOT, main


if __name__ == "__main__":
    main(
        ROOT / "configs" / "exp131_catboost_v1_extended.yaml",
        expected_experiment_id="EXP-131",
        runner_command="uv run python scripts/run_exp131_catboost_v1_extended.py",
    )
