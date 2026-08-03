#!/usr/bin/env python
"""Run EXP-294: EXP-223 pathway pipeline + domain-propensity sample reweighting."""

from run_exp096_fixed_pathway_burden import FixedPathwayBurdenFoldBuilder
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp294_domain_reweighted_pathway.yaml"
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
        runner_command="uv run python scripts/run_exp294_domain_reweighted_pathway.py",
    )
