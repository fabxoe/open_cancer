"""Fold builders for the EXP-527 LightGBM redundancy ablation."""

from __future__ import annotations

from scipy import sparse

from open_cancer.class_semantic_profiles import ClassSemanticProfileFamily
from open_cancer.constants import CLASS_LABELS
from open_cancer.feature_family import FoldFeatureBundle
from open_cancer.patient_semantic_vector import PatientSemanticVectorFamily
from run_exp374_stop_isoform_residue_mask import build_fold_features as build_parent_features
from run_exp527_parser_v4_class_cosine_loo import LeaveOneOutClassCosineFoldBuilder


def build_parser_only_features():
    """Return EXP-527's parser-v4 parent without its 26 class-cosine columns."""

    return build_parent_features()


def build_parser_plus_cosine_features():
    """Return EXP-527's complete leakage-safe feature builder."""

    return LeaveOneOutClassCosineFoldBuilder()


class CosineOnlyFoldBuilder:
    """Build only the 26 leakage-safe class-cosine columns."""

    def __init__(self) -> None:
        source = LeaveOneOutClassCosineFoldBuilder()
        self.train = source.train
        self.test = source.test
        self.gene_columns = source.gene_columns
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
        del fold, base_train, base_validation, base_test
        fitted = ClassSemanticProfileFamily(
            tuple(CLASS_LABELS), method="cosine"
        ).fit(self.train_semantic[train_indices], target)
        profile_train = fitted.transform_train_leave_one_out(
            self.train_semantic[train_indices], target
        )
        profile_valid = fitted.transform(self.train_semantic[valid_indices])
        profile_test = fitted.transform(self.test_semantic)
        profile_registry = fitted.descriptor.to_registry_record()
        profile_registry["profile_audit"] = {
            **fitted.audit_record(),
            "train_transform": "leave_one_out_target_class",
            "validation_test_transform": "full_outer_train_centroid",
        }
        vector_registry = self.vectorizer.descriptor.to_registry_record(enabled=True)
        vector_registry["included_directly_in_model"] = False
        return FoldFeatureBundle(
            train=sparse.csr_matrix(profile_train),
            validation=sparse.csr_matrix(profile_valid),
            test=sparse.csr_matrix(profile_test),
            fitted_families=(fitted,),
            feature_names=fitted.descriptor.feature_names,
            registry={
                self.vectorizer.descriptor.name: vector_registry,
                fitted.descriptor.name: profile_registry,
            },
            base_feature_names_to_drop=tuple(base_feature_names),
        )


def build_cosine_only_features():
    return CosineOnlyFoldBuilder()
