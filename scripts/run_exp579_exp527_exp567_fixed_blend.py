#!/usr/bin/env python
"""Run EXP-579: fixed 0.5/0.5 blend of EXP-527 and EXP-567."""

import run_exp135_fixed_probability_blend as runner


runner.CONFIG_PATH = runner.ROOT / "configs/exp579_exp527_exp567_fixed_blend.yaml"
runner.ISSUE = 579
runner.EXP_ID = "EXP-579"
runner.SLUG = "exp579_exp527_exp567_fixed_blend"
runner.EXPECTED_COMPONENTS = ("EXP-527", "EXP-567")
runner.EXPECTED_WEIGHTS = (0.5, 0.5)
runner.PARENT_EXPERIMENT = "EXP-567"
runner.RUNNER_COMMAND = (
    "uv run python scripts/run_exp579_exp527_exp567_fixed_blend.py"
)
runner.RUNNER_NOTES = (
    "Inference-only fixed 0.5/0.5 probability mean of EXP-527 XGBoost and "
    "EXP-567 LightGBM. The single weight pair was fixed before the official "
    "run; test distribution and Public LB do not select it."
)


if __name__ == "__main__":
    runner.main()
