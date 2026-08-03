#!/usr/bin/env python
"""Run EXP-294: EXP-223 pathway pipeline + domain-propensity sample reweighting."""

import argparse

from run_exp096_fixed_pathway_burden import FixedPathwayBurdenFoldBuilder
from run_hotspot_xgb import ROOT, finalize_saved_run, main


CONFIG = ROOT / "configs" / "exp294_domain_reweighted_pathway.yaml"
MEMBERSHIP = (
    ROOT
    / "reports"
    / "exp223_pathway_macro_f1_checkpoint"
    / "pathway_membership.json"
)
RUNNER_COMMAND = "uv run python scripts/run_exp294_domain_reweighted_pathway.py"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finalize-existing", action="store_true")
    args = parser.parse_args()
    if args.finalize_existing:
        finalize_saved_run(CONFIG, runner_command=RUNNER_COMMAND)
    else:
        main(
            CONFIG,
            fold_feature_builder=FixedPathwayBurdenFoldBuilder(MEMBERSHIP),
            runner_command=RUNNER_COMMAND,
        )
