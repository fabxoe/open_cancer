#!/usr/bin/env python
"""Run EXP-484: fixed 0.7/0.3 blend of EXP-374 and EXP-459."""

import run_exp135_fixed_probability_blend as runner


runner.CONFIG_PATH = runner.ROOT / "configs/exp484_exp374_exp459_blend.yaml"
runner.ISSUE = 484
runner.EXP_ID = "EXP-484"
runner.SLUG = "exp484_exp374_exp459_blend"
runner.EXPECTED_COMPONENTS = ("EXP-374", "EXP-459")
runner.EXPECTED_WEIGHTS = (0.7, 0.3)
runner.PARENT_EXPERIMENT = "EXP-374"
runner.RUNNER_COMMAND = "uv run python scripts/run_exp484_exp374_exp459_blend.py"
runner.RUNNER_NOTES = (
    "Inference-only fixed 0.7/0.3 probability mean of EXP-374 and EXP-459. "
    "Weight was fixed by the #482 test-like propensity screening (PR #483) "
    "before this official run; test distribution and Public LB do not select it."
)


if __name__ == "__main__":
    runner.main()
