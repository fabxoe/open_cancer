#!/usr/bin/env python
"""Run EXP-219: EXP-094 with validation Macro-F1 checkpoint selection."""

from __future__ import annotations

import argparse
from pathlib import Path

from run_hotspot_xgb import finalize_saved_run, main


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "exp219_macro_f1_checkpoint_selection.yaml"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finalize-existing", action="store_true")
    args = parser.parse_args()
    command = "uv run python scripts/run_exp219_macro_f1_checkpoint_selection.py"
    if args.finalize_existing:
        finalize_saved_run(CONFIG, runner_command=command)
    else:
        main(config_override=CONFIG, runner_command=command)
