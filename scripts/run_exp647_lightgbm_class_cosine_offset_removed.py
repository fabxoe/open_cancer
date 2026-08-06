#!/usr/bin/env python
"""Run EXP-647: EXP-567 (LightGBM) with row-mean-centered class-cosine scores.

Re-checks EXP-645's single-variable ablation (EXP-527/XGBoost with the 26
class-cosine scores row-mean-centered) on a different model family. EXP-645
found Macro F1 regressed (-0.0083) while fold std and Log Loss both
improved -- evidence the common offset carries real discriminative signal,
not pure noise, on XGBoost. This checks whether LightGBM's leaf-wise growth
reacts the same way as XGBoost's level-wise growth to the same transform,
rather than concluding from a single model's Local F1 alone.

The centering logic here is identical to
scripts/run_exp645_class_cosine_offset_removed.py (row-wise mean
subtraction, no fitted parameters, no cross-row statistics -- so no
leakage risk beyond what EXP-567 already has). Adoption is judged on
canonical OOF Macro F1 vs EXP-567 only; test AUC and Public LB are not
used to select or tune this transform.
"""

from __future__ import annotations

import numpy as np
from scipy import sparse

import run_exp449_lightgbm_exp374 as runner
from open_cancer.class_semantic_profiles import ClassSemanticProfileFamily
from open_cancer.constants import CLASS_LABELS
from open_cancer.feature_family import FoldFeatureBundle
from open_cancer.patient_semantic_vector import PatientSemanticVectorFamily
from run_exp374_stop_isoform_residue_mask import build_fold_features as build_parent_features


def _center_rows(matrix: sparse.csr_matrix) -> sparse.csr_matrix:
    """Subtract each row's own mean across its columns (no cross-row stats)."""
    dense = np.asarray(matrix.todense(), dtype=np.float64)
    row_mean = dense.mean(axis=1, keepdims=True)
    centered = dense - row_mean
    return sparse.csr_matrix(centered.astype(np.float32))


class OffsetRemovedClassCosineFoldBuilder:
    """Identical to run_exp527_parser_v4_class_cosine_loo's
    LeaveOneOutClassCosineFoldBuilder, except the 26 raw cosine scores are
    additionally row-mean-centered before being appended to the model
    input. Duplicated (not imported cross-branch) to keep this experiment's
    PR self-contained, matching run_exp645_class_cosine_offset_removed.py.
    """

    def __init__(self) -> None:
        self.parent = build_parent_features()
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


runner.CONFIG_PATH = runner.ROOT / "configs/exp647_lightgbm_class_cosine_offset_removed.yaml"
runner.SLUG = "exp647_lightgbm_class_cosine_offset_removed"
runner.FOLD_BUILDER_FACTORY = OffsetRemovedClassCosineFoldBuilder
runner.RUNNER_COMMAND = "uv run python scripts/run_exp647_lightgbm_class_cosine_offset_removed.py"


if __name__ == "__main__":
    runner.main()
