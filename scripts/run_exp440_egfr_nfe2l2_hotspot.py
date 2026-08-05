#!/usr/bin/env python
"""Run EXP-440: EXP-374 + EGFR A289/G598 + NFE2L2 E79 hotspot columns.

Parent is EXP-374 (stop notation normalization + Ensembl isoform mask).
Adds three additive-only, stateless hotspot columns (position-level match,
alternate amino acid ignored, same convention as EXTENDED_HOTSPOTS and
ctnnb1_hotspot_features.py): hotspot__EGFR_289, hotspot__EGFR_598,
hotspot__NFE2L2_79. Burden-clean confirmed in
reports/analysis/hotspot_screening_burden_control.md ("결과 4 -- 대기열").
"""

from __future__ import annotations

from functools import partial

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.abc_c_features import (
    fixed_pathway_burden_family,
    pathway_mutation_type_family,
)
from open_cancer.egfr_nfe2l2_hotspot_features import (
    CANDIDATES,
    egfr_289_family,
    egfr_598_family,
    nfe2l2_79_family,
)
from open_cancer.feature_family import FoldFeatureBundle, remove_semantically_equivalent_features
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
    parse_stop_notation_invariant_token,
)
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, TEST_PATH, TRAIN_PATH, main


CONFIG = ROOT / "configs" / "exp440_egfr_nfe2l2_hotspot.yaml"
ARTIFACT_SLUG = "exp440_egfr_nfe2l2_hotspot"
MEMBERSHIP = ROOT / "reports" / ARTIFACT_SLUG / "pathway_membership.json"

_FAMILY_FACTORIES = (egfr_289_family, egfr_598_family, nfe2l2_79_family)


class EgfrNfe2l2FoldBuilder:
    """Stateless per-candidate hotspot columns, additive-only on top of base."""

    def __init__(self) -> None:
        self.train = pd.read_csv(TRAIN_PATH, dtype=str, keep_default_na=False)
        self.test = pd.read_csv(TEST_PATH, dtype=str, keep_default_na=False)
        self.fitted = tuple(factory().fit(self.train) for factory in _FAMILY_FACTORIES)
        self.feature_names = tuple(
            name for fitted in self.fitted for name in fitted.descriptor.feature_names
        )
        self.train_matrix = sparse.hstack(
            [fitted.transform(self.train) for fitted in self.fitted], format="csr"
        )
        self.test_matrix = sparse.hstack(
            [fitted.transform(self.test) for fitted in self.fitted], format="csr"
        )

    def __call__(
        self,
        *,
        fold,
        train_indices,
        valid_indices,
        base_train,
        base_validation,
        base_test,
        base_feature_names,
        target,
    ) -> FoldFeatureBundle:
        del fold, base_validation, base_test, target
        bundle = FoldFeatureBundle(
            train=self.train_matrix[train_indices],
            validation=self.train_matrix[valid_indices],
            test=self.test_matrix,
            fitted_families=self.fitted,
            feature_names=self.feature_names,
            registry={
                "egfr_nfe2l2_hotspot": {
                    "definition_version": "1.0.0",
                    "fit_scope": "stateless",
                    "candidates": [
                        {"gene": gene, "position": position, "reference_aa": reference_aa}
                        for gene, position, reference_aa in CANDIDATES
                    ],
                    "source_issue": 440,
                }
            },
        )
        bundle, _ = remove_semantically_equivalent_features(bundle, base_train, base_feature_names)
        return bundle


class CombinedFoldBuilder:
    def __init__(self, *builders) -> None:
        self.builders = builders

    def __call__(self, **kwargs) -> FoldFeatureBundle:
        bundles = [builder(**kwargs) for builder in self.builders]
        train = sparse.hstack([bundle.train for bundle in bundles], format="csr", dtype=np.float32)
        validation = sparse.hstack(
            [bundle.validation for bundle in bundles], format="csr", dtype=np.float32
        )
        test = sparse.hstack([bundle.test for bundle in bundles], format="csr", dtype=np.float32)
        feature_names = tuple(name for bundle in bundles for name in bundle.feature_names)
        registry: dict = {}
        for bundle in bundles:
            registry.update(bundle.registry)
        fitted_families = tuple(
            family for bundle in bundles for family in bundle.fitted_families
        )
        base_feature_names_to_drop = tuple(
            dict.fromkeys(
                name for bundle in bundles for name in bundle.base_feature_names_to_drop
            )
        )
        return FoldFeatureBundle(
            train=train,
            validation=validation,
            test=test,
            fitted_families=fitted_families,
            feature_names=feature_names,
            registry=registry,
            base_feature_names_to_drop=base_feature_names_to_drop,
        )


def build_fold_features() -> CombinedFoldBuilder:
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
    pathway_builder = PathwayMutationTypeFoldBuilder(
        membership_path=MEMBERSHIP,
        burden_factory=burden,
        composition_factory=composition,
    )
    hotspot_builder = EgfrNfe2l2FoldBuilder()
    return CombinedFoldBuilder(pathway_builder, hotspot_builder)


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=build_fold_features(),
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        runner_command="uv run python scripts/run_exp440_egfr_nfe2l2_hotspot.py",
    )
