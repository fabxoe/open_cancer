#!/usr/bin/env python
"""Run EXP-237: replace pathway mutation-type counts with fractions."""

from open_cancer.abc_c_features import pathway_mutation_type_fraction_family
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp237_pathway_mutation_fractions.yaml"
MEMBERSHIP = (
    ROOT
    / "reports"
    / "exp237_pathway_mutation_fractions"
    / "pathway_membership.json"
)


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=PathwayMutationTypeFoldBuilder(
            MEMBERSHIP,
            composition_factory=pathway_mutation_type_fraction_family,
        ),
        runner_command="uv run python scripts/run_exp237_pathway_mutation_fractions.py",
    )
