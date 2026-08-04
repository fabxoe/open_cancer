#!/usr/bin/env python
"""Run EXP-253: fixed 0.5/0.5 blend of EXP-209 and EXP-229."""

import run_exp135_fixed_probability_blend as runner


runner.CONFIG_PATH = runner.ROOT / "configs/exp253_lightgbm_xgboost_blend.yaml"
runner.ISSUE = 253
runner.EXP_ID = "EXP-253"
runner.SLUG = "exp253_lightgbm_xgboost_blend"
runner.EXPECTED_COMPONENTS = ("EXP-209", "EXP-229")
runner.EXPECTED_WEIGHTS = (0.5, 0.5)
runner.PARENT_EXPERIMENT = "EXP-229"
runner.RUNNER_COMMAND = "uv run python scripts/run_exp253_lightgbm_xgboost_blend.py"
runner.RUNNER_NOTES = (
    "Inference-only fixed 0.5/0.5 probability mean of EXP-209 and EXP-229. "
    "The single weight pair was fixed before the official run; test distribution "
    "and Public LB do not select it."
)


if __name__ == "__main__":
    runner.main()
