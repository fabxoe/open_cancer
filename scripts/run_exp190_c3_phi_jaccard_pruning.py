#!/usr/bin/env python
"""Run EXP-190: fold-safe broad Phi/Jaccard pruning on Feature Spec v1."""

from __future__ import annotations

from pathlib import Path

from run_exp188_c1_phi_jaccard_pruning import main


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "exp190_c3_phi_jaccard_pruning.yaml"


if __name__ == "__main__":
    main(config_path=CONFIG)
