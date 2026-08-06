#!/usr/bin/env python
"""Run EXP-645: EXP-527 with row-mean-centered class-cosine scores.

Single-variable ablation motivated by Issue #530's EXP-527 generalization
audit (reports/analysis/exp527_generalization_audit/README.md), which found
all 26 class-cosine scores rise together on test (domain classifier OOF AUC
0.647015) -- a common per-row shift, not a class-specific one. This runner
is byte-identical to run_exp527_parser_v4_class_cosine_loo.py except that
the 26 raw cosine scores (train/validation/test alike) are additionally
centered by subtracting each row's own mean across the 26 scores before
being appended to the model input.

The centering is a deterministic function of that row alone -- no fitted
parameters, no cross-row statistics -- so it introduces no leakage risk
beyond what EXP-527 already has. Adoption is judged on canonical OOF Macro
F1 vs EXP-527 only; test AUC and Public LB are not used to select or tune
this transform, per the #530 report's explicit instruction.
"""

from __future__ import annotations

import numpy as np
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


CONFIG = ROOT / "configs" / "exp645_class_cosine_offset_removed.yaml"


def _center_rows(matrix: sparse.csr_matrix) -> sparse.csr_matrix:
    """Subtract each row's own mean across its columns (no cross-row stats)."""
    dense = np.asarray(matrix.todense(), dtype=np.float64)
    row_mean = dense.mean(axis=1, keepdims=True)
    centered = dense - row_mean
    return sparse.csr_matrix(centered.astype(np.float32))


class OffsetRemovedClassCosineFoldBuilder:
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
        profile_train = _center_rows(
            fitted_profile.transform_train_leave_one_out(
                self.train_semantic[train_indices], target
            )
        )
        profile_valid = _center_rows(fitted_profile.transform(self.train_semantic[valid_indices]))
        profile_test = _center_rows(fitted_profile.transform(self.test_semantic))
        profile_registry = fitted_profile.descriptor.to_registry_record()
        profile_registry["profile_audit"] = {
            **fitted_profile.audit_record(),
            "train_transform": "leave_one_out_target_class",
            "validation_test_transform": "full_outer_train_centroid",
            "post_transform": "row_wise_mean_centering",
        }
        vector_registry = self.vectorizer.descriptor.to_registry_record(enabled=True)
        vector_registry["included_directly_in_model"] = False
        feature_names = tuple(
            f"{name}__offset_removed" for name in fitted_profile.descriptor.feature_names
        )
        return FoldFeatureBundle(
            train=sparse.hstack([parent.train, profile_train], format="csr"),
            validation=sparse.hstack([parent.validation, profile_valid], format="csr"),
            test=sparse.hstack([parent.test, profile_test], format="csr"),
            fitted_families=parent.fitted_families + (fitted_profile,),
            feature_names=parent.feature_names + feature_names,
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
        fold_feature_builder=OffsetRemovedClassCosineFoldBuilder(),
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        runner_command="uv run python scripts/run_exp645_class_cosine_offset_removed.py",
    )
