#!/usr/bin/env python
"""Run EXP-512: EXP-374 plus patient-level parser-v4 semantic token counts."""

from __future__ import annotations

from scipy import sparse

from open_cancer.feature_family import FoldFeatureBundle, build_family_registry, transform_checked
from open_cancer.parser_v4_semantic_counts import ParserV4SemanticCountFamily
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
)
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_exp374_stop_isoform_residue_mask import build_fold_features as build_parent_features
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp512_parser_v4_semantic_counts.yaml"


class SemanticCountFoldBuilder:
    def __init__(self) -> None:
        self.parent: PathwayMutationTypeFoldBuilder = build_parent_features()
        self.train = self.parent.train
        self.test = self.parent.test
        self.gene_columns = self.parent.gene_columns
        family = ParserV4SemanticCountFamily(self.gene_columns)
        self.fitted = family.fit(self.train.iloc[:1])
        self.train_matrix = transform_checked(self.fitted, self.train)
        self.test_matrix = transform_checked(self.fitted, self.test)

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
        return FoldFeatureBundle(
            train=sparse.hstack([parent.train, self.train_matrix[train_indices]], format="csr"),
            validation=sparse.hstack([parent.validation, self.train_matrix[valid_indices]], format="csr"),
            test=sparse.hstack([parent.test, self.test_matrix], format="csr"),
            fitted_families=parent.fitted_families + (self.fitted,),
            feature_names=parent.feature_names + self.fitted.descriptor.feature_names,
            registry={**parent.registry, **build_family_registry((self.fitted,))},
            base_feature_names_to_drop=parent.base_feature_names_to_drop,
        )


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=SemanticCountFoldBuilder(),
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        runner_command="uv run python scripts/run_exp512_parser_v4_semantic_counts.py",
    )
