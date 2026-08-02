#!/usr/bin/env python
"""Run EXP-223: EXP-096 pathway features with Macro-F1 checkpoint selection."""

from run_exp096_fixed_pathway_burden import FixedPathwayBurdenFoldBuilder
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp223_pathway_macro_f1_checkpoint.yaml"
MEMBERSHIP = (
    ROOT
    / "reports"
    / "exp223_pathway_macro_f1_checkpoint"
    / "pathway_membership.json"
)


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=FixedPathwayBurdenFoldBuilder(MEMBERSHIP),
        runner_command="uv run python scripts/run_exp223_pathway_macro_f1_checkpoint.py",
    )
