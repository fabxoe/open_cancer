#!/usr/bin/env python
"""Run EXP-391: exact normalized-token deduplication on EXP-374."""

from __future__ import annotations

from functools import partial

from open_cancer.abc_c_features import (
    fixed_pathway_burden_family,
    pathway_mutation_type_family,
)
from open_cancer.exact_duplicate_mutation_parser import (
    EXACT_DUPLICATE_PARSER_CONTRACT,
    normalize_exact_duplicate_hotspot_token,
    parse_exact_duplicate_invariant_cell,
    parse_exact_duplicate_invariant_token,
)
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp391_exact_duplicate_token_normalization.yaml"
MEMBERSHIP = (
    ROOT
    / "reports"
    / "exp391_exact_duplicate_token_normalization"
    / "pathway_membership.json"
)


def build_fold_features() -> PathwayMutationTypeFoldBuilder:
    burden = partial(
        fixed_pathway_burden_family,
        token_parser=parse_exact_duplicate_invariant_token,
        version="3.0.0",
    )
    composition = partial(
        pathway_mutation_type_family,
        token_parser=parse_exact_duplicate_invariant_token,
        version="3.0.0",
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
        mutation_cell_parser=parse_exact_duplicate_invariant_cell,
        mutation_parser_contract=EXACT_DUPLICATE_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_exact_duplicate_hotspot_token,
        runner_command=(
            "uv run python "
            "scripts/run_exp391_exact_duplicate_token_normalization.py"
        ),
    )
