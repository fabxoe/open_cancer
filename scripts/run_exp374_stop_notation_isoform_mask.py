#!/usr/bin/env python
"""Run EXP-374: EXP-369 stop notation fix + EXP-313 Ensembl isoform mask.

Parent is EXP-369 (not EXP-334). Model hyperparameters stay at the
EXP-229/EXP-369 defaults; EXP-285's nested-Optuna per-fold parameters are
deliberately not carried over so this experiment isolates the isoform mask's
effect on top of the corrected parser without EXP-334's tuning confound (see
configs/exp374_stop_notation_isoform_mask.yaml notes).
"""

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


CONFIG = ROOT / "configs" / "exp374_stop_notation_isoform_mask.yaml"
MEMBERSHIP = ROOT / "reports" / "exp374_stop_notation_isoform_mask" / "pathway_membership.json"


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
        runner_command=(
            "uv run python scripts/run_exp374_stop_notation_isoform_mask.py"
        ),
    )
