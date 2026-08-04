#!/usr/bin/env python
"""Run EXP-327: EXP-229 with frozen isoform-relative position bins."""

from __future__ import annotations

from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp327_isoform_relative_position_bin.yaml"
MEMBERSHIP = (
    ROOT / "reports" / "exp327_isoform_relative_position_bin" / "pathway_membership.json"
)


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=PathwayMutationTypeFoldBuilder(membership_path=MEMBERSHIP),
        runner_command="uv run python scripts/run_exp327_isoform_relative_position_bin.py",
    )
