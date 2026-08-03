#!/usr/bin/env python
"""Run EXP-279: EXP-219 with rolling-median Macro-F1 checkpoints."""

from __future__ import annotations

import argparse
from pathlib import Path

from run_hotspot_xgb import finalize_saved_run, main


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "exp279_checkpoint_rolling_median.yaml"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finalize-existing", action="store_true")
    args = parser.parse_args()
    command = "uv run python scripts/run_exp279_checkpoint_rolling_median.py"
    if args.finalize_existing:
        finalize_saved_run(CONFIG, runner_command=command)
    else:
        main(config_override=CONFIG, runner_command=command)
