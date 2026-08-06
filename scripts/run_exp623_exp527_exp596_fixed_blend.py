#!/usr/bin/env python
"""Run EXP-623: fixed 0.5/0.5 blend of EXP-527 and EXP-596."""

import run_exp135_fixed_probability_blend as runner


runner.CONFIG_PATH = runner.ROOT / "configs/exp623_exp527_exp596_fixed_blend.yaml"
runner.ISSUE = 623
runner.EXP_ID = "EXP-623"
runner.SLUG = "exp623_exp527_exp596_fixed_blend"
runner.EXPECTED_COMPONENTS = ("EXP-527", "EXP-596")
runner.EXPECTED_WEIGHTS = (0.5, 0.5)
runner.PARENT_EXPERIMENT = "EXP-527"
runner.RUNNER_COMMAND = (
    "uv run python scripts/run_exp623_exp527_exp596_fixed_blend.py"
)
runner.RUNNER_NOTES = (
    "Inference-only fixed 0.5/0.5 probability mean of EXP-527 XGBoost and "
    "EXP-596 RandomForest. The single weight pair was fixed before the "
    "official run; test distribution and Public LB do not select it."
)


if __name__ == "__main__":
    runner.main()
