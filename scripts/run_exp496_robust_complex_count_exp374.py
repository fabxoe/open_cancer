#!/usr/bin/env python
"""Run EXP-496: EXP-374 with raw sample__complex_count replaced by the
robust non-simple event gene count (EXP-355's R1 family, reused verbatim).

EXP-355 tried this exact swap against EXP-229 and was REJECTED on Local OOF
alone. This re-runs it against the current EXP-374 parent; the mandatory
test-like subset check (scripts/check_exp496_test_like_subset.py) is the
primary judgment criterion, since raw sample__complex_count is the #1 gain
feature in the #292 adversarial-validation domain-shift diagnostic.
"""

from __future__ import annotations

from functools import partial

from scipy import sparse

from open_cancer.abc_c_features import (
    fixed_pathway_burden_family,
    pathway_mutation_type_family,
)
from open_cancer.feature_family import FoldFeatureBundle, build_family_registry
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    RobustNonSimpleGeneCountFamily,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
    parse_stop_notation_invariant_token,
)
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, main

CONFIG = ROOT / "configs" / "exp496_robust_complex_count_exp374.yaml"
MEMBERSHIP = ROOT / "reports" / "exp496_robust_complex_count_exp374" / "pathway_membership.json"


class RobustComplexCountOverExp374FoldBuilder:
    """EXP-374's fold-safe pathway builder plus EXP-355's R1 base-feature swap."""

    def __init__(self) -> None:
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
        self.pathway_builder = PathwayMutationTypeFoldBuilder(
            membership_path=MEMBERSHIP,
            burden_factory=burden,
            composition_factory=composition,
        )
        self.robust_fitted = RobustNonSimpleGeneCountFamily(
            self.pathway_builder.gene_columns
        ).fit(self.pathway_builder.train.iloc[:1])
        self.robust_train = self.robust_fitted.transform(self.pathway_builder.train)
        self.robust_test = self.robust_fitted.transform(self.pathway_builder.test)

    def __call__(self, **kwargs) -> FoldFeatureBundle:
        pathway = self.pathway_builder(**kwargs)
        train_indices = kwargs["train_indices"]
        valid_indices = kwargs["valid_indices"]
        registry = {
            **pathway.registry,
            **build_family_registry((self.robust_fitted,)),
            "base_feature_replacement": {
                "definition_version": "1.0.0",
                "enabled": True,
                "fit_scope": "stateless",
                "output_dimension": 1,
                "drop": ["sample__complex_count"],
                "add": ["sample__robust_non_simple_event_gene_count"],
                "selection_uses_target": False,
                "selection_uses_test_prevalence": False,
            },
        }
        return FoldFeatureBundle(
            train=sparse.hstack(
                [pathway.train, self.robust_train[train_indices]], format="csr"
            ),
            validation=sparse.hstack(
                [pathway.validation, self.robust_train[valid_indices]], format="csr"
            ),
            test=sparse.hstack([pathway.test, self.robust_test], format="csr"),
            fitted_families=(*pathway.fitted_families, self.robust_fitted),
            feature_names=(
                *pathway.feature_names,
                *self.robust_fitted.descriptor.feature_names,
            ),
            registry=registry,
            base_feature_names_to_drop=(
                *pathway.base_feature_names_to_drop,
                *self.robust_fitted.base_feature_names_to_drop,
            ),
        )


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=RobustComplexCountOverExp374FoldBuilder(),
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        runner_command=(
            "uv run python scripts/run_exp496_robust_complex_count_exp374.py"
        ),
    )
