#!/usr/bin/env python
"""Run EXP-209: LightGBM on frozen Feature Spec v2-performance."""

from run_exp123_sparse_logistic_v1 import ROOT, main


if __name__ == "__main__":
    main(
        ROOT / "configs" / "exp209_lightgbm_v2_performance.yaml",
        expected_experiment_id="EXP-209",
        runner_command="uv run python scripts/run_exp209_lightgbm_v2_performance.py",
    )
