#!/usr/bin/env python
"""Run EXP-127: CatBoost on frozen Feature Spec v1."""

from run_exp123_sparse_logistic_v1 import ROOT, main


if __name__ == "__main__":
    main(
        ROOT / "configs" / "exp127_catboost_v1.yaml",
        expected_experiment_id="EXP-127",
        runner_command="uv run python scripts/run_exp127_catboost_v1.py",
    )
