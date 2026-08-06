#!/usr/bin/env python
"""Run EXP-567: LightGBM with EXP-527 parser-v4 and class-cosine features."""

import run_exp449_lightgbm_exp374 as runner
from exp527_lightgbm_ablation_builders import build_parser_plus_cosine_features


runner.CONFIG_PATH = runner.ROOT / "configs/exp567_lightgbm_parser_cosine.yaml"
runner.SLUG = "exp567_lightgbm_parser_cosine"
runner.FOLD_BUILDER_FACTORY = build_parser_plus_cosine_features
runner.RUNNER_COMMAND = "uv run python scripts/run_exp567_lightgbm_parser_cosine.py"


if __name__ == "__main__":
    runner.main()
