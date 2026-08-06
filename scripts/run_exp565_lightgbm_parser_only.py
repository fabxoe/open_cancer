#!/usr/bin/env python
"""Run EXP-565: LightGBM with EXP-527 parser-v4 parent features only."""

import run_exp449_lightgbm_exp374 as runner
from exp527_lightgbm_ablation_builders import build_parser_only_features


runner.CONFIG_PATH = runner.ROOT / "configs/exp565_lightgbm_parser_only.yaml"
runner.SLUG = "exp565_lightgbm_parser_only"
runner.FOLD_BUILDER_FACTORY = build_parser_only_features
runner.RUNNER_COMMAND = "uv run python scripts/run_exp565_lightgbm_parser_only.py"


if __name__ == "__main__":
    runner.main()
