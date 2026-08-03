#!/usr/bin/env python
"""Run EXP-207: fold-local Boruta mutation-presence selection on Feature Spec v1."""

from __future__ import annotations

from pathlib import Path

from run_exp188_c1_phi_jaccard_pruning import main


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "exp207_s3_boruta_feature_selection.yaml"


if __name__ == "__main__":
    main(config_path=CONFIG)
