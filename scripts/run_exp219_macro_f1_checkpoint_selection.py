#!/usr/bin/env python
"""Run EXP-219: EXP-094 with validation Macro-F1 checkpoint selection."""

from __future__ import annotations

from pathlib import Path

from run_hotspot_xgb import main


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "exp219_macro_f1_checkpoint_selection.yaml"


if __name__ == "__main__":
    main(
        config_override=CONFIG,
        runner_command=(
            "uv run python scripts/run_exp219_macro_f1_checkpoint_selection.py"
        ),
    )
