#!/usr/bin/env python
"""Run EXP-464: official record for the (EXP-374, EXP-449) blend ratio sweep.

The full 4-ratio comparison (0.9/0.1, 0.8/0.2, 0.7/0.3, 0.6/0.4) is computed
by scripts/sweep_exp464_blend_ratios.py against the mandatory test-like
subset gate; none passed. This script writes the official experiment
record for the least-bad ratio (0.7/0.3), reusing EXP-135's fixed
probability-blend engine.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scripts.run_exp135_fixed_probability_blend as runner

runner.CONFIG_PATH = runner.ROOT / "configs/exp464_blend_ratio_sweep.yaml"
runner.ISSUE = 464
runner.EXP_ID = "EXP-464"
runner.SLUG = "exp464_blend_ratio_sweep"
runner.EXPECTED_COMPONENTS = ("EXP-374", "EXP-449")
runner.EXPECTED_WEIGHTS = (0.7, 0.3)
runner.PARENT_EXPERIMENT = "EXP-374"
runner.RUNNER_COMMAND = "uv run python scripts/run_exp464_blend_ratio_sweep.py"
runner.RUNNER_NOTES = (
    "Inference-only fixed 0.7/0.3 arithmetic probability mean of EXP-374 and "
    "EXP-449 -- the least-bad point from a 4-ratio sweep (0.9/0.1..0.6/0.4), "
    "recorded as EXP-464's official representative arm. All 4 ratios failed "
    "the mandatory train_domain_propensity.csv test-like subset check "
    "(delta >= 0 required); see reports/exp464_blend_ratio_sweep/"
    "sweep_results.json for the full table. REJECTED."
)

if __name__ == "__main__":
    runner.main()
