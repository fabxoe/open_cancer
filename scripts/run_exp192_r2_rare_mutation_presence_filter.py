#!/usr/bin/env python
"""Run EXP-192: fold-safe rare mutation-presence filter on Feature Spec v1."""

from __future__ import annotations

from pathlib import Path

from run_exp188_c1_phi_jaccard_pruning import main


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "exp192_r2_rare_mutation_presence_filter.yaml"


if __name__ == "__main__":
    main(config_path=CONFIG)
