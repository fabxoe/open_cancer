#!/usr/bin/env python
"""Run EXP-521: EXP-374 plus fold-safe parser-v4 class cosine profiles."""

from __future__ import annotations

from scipy import sparse

from open_cancer.class_semantic_profiles import ClassSemanticProfileFamily
from open_cancer.constants import CLASS_LABELS
from open_cancer.feature_family import FoldFeatureBundle
from open_cancer.patient_semantic_vector import PatientSemanticVectorFamily
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
)
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_exp374_stop_isoform_residue_mask import build_fold_features as build_parent_features
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp521_parser_v4_class_cosine.yaml"


class ClassCosineFoldBuilder:
    def __init__(self) -> None:
        self.parent: PathwayMutationTypeFoldBuilder = build_parent_features()
        self.train = self.parent.train
        self.test = self.parent.test
        self.gene_columns = self.parent.gene_columns
        self.vectorizer = PatientSemanticVectorFamily(self.gene_columns).fit(
            self.train.iloc[:1]
        )
        self.train_semantic = self.vectorizer.transform(self.train)
        self.test_semantic = self.vectorizer.transform(self.test)

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
    ):
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
        fitted_profile = ClassSemanticProfileFamily(
            tuple(CLASS_LABELS), method="cosine"
        ).fit(self.train_semantic[train_indices], target)
        profile_train = fitted_profile.transform(self.train_semantic[train_indices])
        profile_valid = fitted_profile.transform(self.train_semantic[valid_indices])
        profile_test = fitted_profile.transform(self.test_semantic)
        profile_registry = fitted_profile.descriptor.to_registry_record()
        profile_registry["profile_audit"] = fitted_profile.audit_record()
        vector_registry = self.vectorizer.descriptor.to_registry_record(enabled=True)
        vector_registry["included_directly_in_model"] = False
        return FoldFeatureBundle(
            train=sparse.hstack([parent.train, profile_train], format="csr"),
            validation=sparse.hstack([parent.validation, profile_valid], format="csr"),
            test=sparse.hstack([parent.test, profile_test], format="csr"),
            fitted_families=parent.fitted_families + (fitted_profile,),
            feature_names=parent.feature_names + fitted_profile.descriptor.feature_names,
            registry={
                **parent.registry,
                self.vectorizer.descriptor.name: vector_registry,
                fitted_profile.descriptor.name: profile_registry,
            },
            base_feature_names_to_drop=parent.base_feature_names_to_drop,
        )


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=ClassCosineFoldBuilder(),
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        runner_command="uv run python scripts/run_exp521_parser_v4_class_cosine.py",
    )
