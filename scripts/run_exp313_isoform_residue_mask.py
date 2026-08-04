#!/usr/bin/env python
"""Run EXP-313: EXP-229 plus the frozen Ensembl residue-position mask."""

from __future__ import annotations

from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp313_isoform_residue_mask.yaml"
MEMBERSHIP = ROOT / "reports" / "exp313_isoform_residue_mask" / "pathway_membership.json"


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=PathwayMutationTypeFoldBuilder(membership_path=MEMBERSHIP),
        runner_command="uv run python scripts/run_exp313_isoform_residue_mask.py",
    )
