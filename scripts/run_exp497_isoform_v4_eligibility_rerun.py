#!/usr/bin/env python
"""Run EXP-497: EXP-374 rerun with the N6 (#493/#495) isoform eligibility fix."""

from __future__ import annotations

from functools import partial

from open_cancer.abc_c_features import (
    fixed_pathway_burden_family,
    pathway_mutation_type_family,
)
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
    parse_stop_notation_invariant_token,
)
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp497_isoform_v4_eligibility_rerun.yaml"
MEMBERSHIP = (
    ROOT / "reports" / "exp497_isoform_v4_eligibility_rerun" / "pathway_membership.json"
)


def build_fold_features() -> PathwayMutationTypeFoldBuilder:
    burden = partial(
        fixed_pathway_burden_family,
        token_parser=parse_stop_notation_invariant_token,
        version="2.1.0",
    )
    composition = partial(
        pathway_mutation_type_family,
        token_parser=parse_stop_notation_invariant_token,
        version="2.1.0",
    )
    return PathwayMutationTypeFoldBuilder(
        membership_path=MEMBERSHIP,
        burden_factory=burden,
        composition_factory=composition,
    )


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=build_fold_features(),
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        runner_command="uv run python scripts/run_exp497_isoform_v4_eligibility_rerun.py",
    )
