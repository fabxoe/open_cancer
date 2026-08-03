#!/usr/bin/env python
"""Run EXP-211: One-vs-Rest XGBoost on frozen v2-performance features."""

from run_exp123_sparse_logistic_v1 import ROOT, main


if __name__ == "__main__":
    main(
        ROOT / "configs" / "exp211_ovr_xgboost_v2_performance.yaml",
        expected_experiment_id="EXP-211",
        runner_command="uv run python scripts/run_exp211_ovr_xgboost_v2_performance.py",
    )
