#!/usr/bin/env python
"""Run EXP-566: LightGBM with only 26 leakage-safe class-cosine scores."""

import run_exp449_lightgbm_exp374 as runner
from exp527_lightgbm_ablation_builders import build_cosine_only_features


runner.CONFIG_PATH = runner.ROOT / "configs/exp566_lightgbm_cosine_only.yaml"
runner.SLUG = "exp566_lightgbm_cosine_only"
runner.FOLD_BUILDER_FACTORY = build_cosine_only_features
runner.RUNNER_COMMAND = "uv run python scripts/run_exp566_lightgbm_cosine_only.py"


if __name__ == "__main__":
    runner.main()
