#!/usr/bin/env python
"""Run EXP-450: fixed 0.5/0.5 blend of EXP-374 and EXP-449."""

import run_exp135_fixed_probability_blend as runner


runner.CONFIG_PATH = runner.ROOT / "configs/exp450_lightgbm_exp374_blend.yaml"
runner.ISSUE = 450
runner.EXP_ID = "EXP-450"
runner.SLUG = "exp450_lightgbm_exp374_blend"
runner.EXPECTED_COMPONENTS = ("EXP-374", "EXP-449")
runner.EXPECTED_WEIGHTS = (0.5, 0.5)
runner.PARENT_EXPERIMENT = "EXP-374"
runner.RUNNER_COMMAND = "uv run python scripts/run_exp450_lightgbm_exp374_blend.py"
runner.RUNNER_NOTES = (
    "Inference-only fixed 0.5/0.5 probability mean of EXP-374 and EXP-449. "
    "The single weight pair was fixed before the official run; test "
    "distribution and Public LB do not select it."
)


if __name__ == "__main__":
    runner.main()
