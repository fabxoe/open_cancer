#!/usr/bin/env python
"""Run EXP-323: fixed 0.5/0.5 blend of EXP-285 and EXP-313."""

import run_exp135_fixed_probability_blend as runner


runner.CONFIG_PATH = runner.ROOT / "configs/exp323_exp285_exp313_fixed_blend.yaml"
runner.ISSUE = 323
runner.EXP_ID = "EXP-323"
runner.SLUG = "exp323_exp285_exp313_fixed_blend"
runner.EXPECTED_COMPONENTS = ("EXP-285", "EXP-313")
runner.EXPECTED_WEIGHTS = (0.5, 0.5)
runner.PARENT_EXPERIMENT = "EXP-285"
runner.RUNNER_COMMAND = (
    "uv run python scripts/run_exp323_exp285_exp313_fixed_blend.py"
)
runner.RUNNER_NOTES = (
    "Inference-only fixed 0.5/0.5 probability mean of EXP-285 and EXP-313. "
    "The single weight pair was fixed before the official run after a "
    "target-independent artifact-contract and diversity audit; test distribution "
    "and Public LB do not select it."
)


if __name__ == "__main__":
    runner.main()
