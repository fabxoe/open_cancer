#!/usr/bin/env python
"""Run EXP-392: EXP-374 plus range stop/no-change gene indicators."""

from __future__ import annotations

from scipy import sparse

from open_cancer.feature_family import (
    FoldFeatureBundle,
    build_family_registry,
    find_semantically_equivalent_features,
    transform_checked,
)
from open_cancer.hashing import sha256_lines
from open_cancer.range_semantic_features import (
    FittedRangeSemanticGeneFamily,
    RangeSemanticGeneFamily,
)
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
)
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_exp374_stop_isoform_residue_mask import build_fold_features as build_parent_features
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp392_range_semantic_indicators.yaml"


class RangeSemanticFoldBuilder:
    """Append only non-equivalent range-stop/no-change indicators."""

    def __init__(self) -> None:
        self.parent: PathwayMutationTypeFoldBuilder = build_parent_features()
        self.train = self.parent.train
        self.test = self.parent.test
        self.gene_columns = self.parent.gene_columns

    def __call__(self, *, fold, train_indices, valid_indices, base_train,
                 base_validation, base_test, base_feature_names, target):
        parent = self.parent(
            fold=fold,
            train_indices=train_indices,
            valid_indices=valid_indices,
            base_train=base_train,
            base_validation=base_validation,
            base_test=base_test,
            base_feature_names=base_feature_names,
            target=target,
        )
        fitted = RangeSemanticGeneFamily(self.gene_columns).fit(
            self.train.iloc[train_indices]
        )
        train_matrix = transform_checked(fitted, self.train.iloc[train_indices])
        validation_matrix = transform_checked(fitted, self.train.iloc[valid_indices])
        test_matrix = transform_checked(fitted, self.test)
        reference_train = sparse.hstack([base_train, parent.train], format="csr")
        reference_names = tuple(base_feature_names) + parent.feature_names
        equivalents = find_semantically_equivalent_features(
            train_matrix,
            fitted.descriptor.feature_names,
            reference_train,
            reference_names,
        )
        keep = [
            index
            for index, name in enumerate(fitted.descriptor.feature_names)
            if name not in equivalents
        ]
        if not keep:
            raise RuntimeError(
                f"fold {fold}: range semantic candidate가 모두 기존 피처와 동일합니다."
            )
        kept_pairs = tuple(fitted.selected_gene_semantics[index] for index in keep)
        kept_names = tuple(fitted.descriptor.feature_names[index] for index in keep)
        fitted_kept = FittedRangeSemanticGeneFamily(
            descriptor=type(fitted.descriptor)(
                name=fitted.descriptor.name,
                version=fitted.descriptor.version,
                fit_scope=fitted.descriptor.fit_scope,
                feature_names=kept_names,
            ),
            selected_gene_semantics=kept_pairs,
        )
        registry = {
            **parent.registry,
            **build_family_registry((fitted_kept,)),
            "range_semantic_equivalence_filter": {
                "definition_version": "1.0.0",
                "enabled": True,
                "output_dimension": len(kept_names),
                "feature_names_sha256": sha256_lines(kept_names),
                "fit_scope": "fold_train",
                "external_knowledge": None,
                "dropped": equivalents,
            },
        }
        return FoldFeatureBundle(
            train=sparse.hstack([parent.train, train_matrix[:, keep]], format="csr"),
            validation=sparse.hstack(
                [parent.validation, validation_matrix[:, keep]], format="csr"
            ),
            test=sparse.hstack([parent.test, test_matrix[:, keep]], format="csr"),
            fitted_families=parent.fitted_families + (fitted_kept,),
            feature_names=parent.feature_names + kept_names,
            registry=registry,
            base_feature_names_to_drop=parent.base_feature_names_to_drop,
        )


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=RangeSemanticFoldBuilder(),
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        runner_command="uv run python scripts/run_exp392_range_semantic_indicators.py",
    )
