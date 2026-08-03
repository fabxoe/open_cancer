#!/usr/bin/env python
"""Run EXP-257: EXP-096 (v1 + fixed_pathway_burden) plus gated functional-role
mutated-gene-count views (oncogene/tumor_suppressor x raw/frac/resid/log1p).

Issue #257, extending #176. Baseline is EXP-096 exactly; the only addition is
up to 8 functional-role candidate columns, gated per fold on fold-train-only
statistics (saturation / sparsity / dominance) and filtered for semantic
duplicates against the frozen v1 base plus the 20 fixed_pathway_burden
columns already present in EXP-096.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.abc_c_features import fixed_pathway_burden_family, load_fixed_groups
from open_cancer.feature_family import (
    FoldFeatureBundle,
    build_family_registry,
    remove_semantically_equivalent_features,
    transform_checked,
)
from open_cancer.functional_role_extended_features import (
    functional_role_burden_extended_family,
)
from open_cancer.hashing import sha256_file
from run_hotspot_xgb import ROOT, TEST_PATH, TRAIN_PATH, main

PATHWAY_KNOWLEDGE_PATH = ROOT / "knowledge" / "canonical_pathways_sanchez_vega_v1.json"
ROLE_KNOWLEDGE_PATH = ROOT / "knowledge" / "abc_c_compact_groups_v1.json"
REPORT_DIR = ROOT / "reports" / "exp257_functional_role_burden_extended"
MEMBERSHIP_PATH = REPORT_DIR / "role_membership.json"
GATING_PATH = REPORT_DIR / "fold_gating.json"


class FunctionalRoleBurdenExtendedFoldBuilder:
    """EXP-096 pathway burden (unconditional) + gated functional-role candidates."""

    def __init__(self) -> None:
        self.train = pd.read_csv(TRAIN_PATH, dtype=str, keep_default_na=False)
        self.test = pd.read_csv(TEST_PATH, dtype=str, keep_default_na=False)
        self.gene_columns = tuple(
            column for column in self.train.columns if column not in {"ID", "SUBCLASS"}
        )
        self.pathway_fitted = None
        self.pathway_train_matrix = None
        self.pathway_test_matrix = None
        self.fold_gating_records: list[dict] = []

    def _prepare(self) -> None:
        if self.pathway_fitted is not None:
            return
        pathway_family = fixed_pathway_burden_family(self.gene_columns, PATHWAY_KNOWLEDGE_PATH)
        self.pathway_fitted = pathway_family.fit(self.train.iloc[:1])
        self.pathway_train_matrix = transform_checked(self.pathway_fitted, self.train)
        self.pathway_test_matrix = transform_checked(self.pathway_fitted, self.test)

        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        role_groups, role_document = load_fixed_groups(ROLE_KNOWLEDGE_PATH, kind="functional_roles")
        MEMBERSHIP_PATH.write_text(
            json.dumps(
                {
                    "knowledge_file": str(ROLE_KNOWLEDGE_PATH.relative_to(ROOT)),
                    "knowledge_sha256": sha256_file(ROLE_KNOWLEDGE_PATH),
                    "source": role_document.get("source"),
                    "version": role_document.get("version"),
                    "license": role_document.get("license"),
                    "groups": {name: list(genes) for name, genes in role_groups.items()},
                    "group_sizes": {name: len(genes) for name, genes in role_groups.items()},
                    "candidate_kinds": ["raw", "frac", "resid", "log1p"],
                    "gates": {
                        "saturation_max_zero_rate": 0.05,
                        "sparse_min_nonzero_rate": 0.01,
                        "dominance_max_share": 0.8,
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def __call__(
        self,
        *,
        fold: int,
        train_indices,
        valid_indices,
        base_train,
        base_validation,
        base_test,
        base_feature_names,
        target,
    ) -> FoldFeatureBundle:
        del base_validation
        self._prepare()

        pathway_bundle = FoldFeatureBundle(
            train=self.pathway_train_matrix[train_indices],
            validation=self.pathway_train_matrix[valid_indices],
            test=self.pathway_test_matrix,
            fitted_families=(self.pathway_fitted,),
            feature_names=self.pathway_fitted.descriptor.feature_names,
            registry=build_family_registry((self.pathway_fitted,)),
        )
        pathway_bundle, pathway_dropped = remove_semantically_equivalent_features(
            pathway_bundle, base_train, base_feature_names
        )

        role_family = functional_role_burden_extended_family(self.gene_columns, ROLE_KNOWLEDGE_PATH)
        fold_train_frame = self.train.iloc[train_indices].reset_index(drop=True)
        fold_valid_frame = self.train.iloc[valid_indices].reset_index(drop=True)
        role_fitted = role_family.fit(fold_train_frame, np.asarray(target))
        role_bundle = FoldFeatureBundle(
            train=transform_checked(role_fitted, fold_train_frame),
            validation=transform_checked(role_fitted, fold_valid_frame),
            test=transform_checked(role_fitted, self.test),
            fitted_families=(role_fitted,),
            feature_names=role_fitted.descriptor.feature_names,
            registry=build_family_registry((role_fitted,)),
        )

        combined_reference_train = sparse.hstack(
            [base_train, pathway_bundle.train], format="csr", dtype=np.float32
        )
        combined_reference_names = tuple(base_feature_names) + pathway_bundle.feature_names
        role_bundle, role_dropped = remove_semantically_equivalent_features(
            role_bundle, combined_reference_train, combined_reference_names
        )

        self.fold_gating_records.append(
            {
                "fold": fold,
                "gate_summary": {
                    group: {
                        **stats,
                        "dominant_class_index": stats["dominant_class_index"],
                    }
                    for group, stats in role_fitted.gate_summary.items()
                },
                "resid_coefficients": role_fitted.resid_coefficients,
                "pathway_burden_dropped_duplicates": pathway_dropped,
                "role_dropped_duplicates": role_dropped,
                "surviving_role_features": list(role_bundle.feature_names),
            }
        )
        if fold == 4:
            GATING_PATH.write_text(
                json.dumps(self.fold_gating_records, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        combined_train = sparse.hstack(
            [pathway_bundle.train, role_bundle.train], format="csr", dtype=np.float32
        )
        combined_validation = sparse.hstack(
            [pathway_bundle.validation, role_bundle.validation], format="csr", dtype=np.float32
        )
        combined_test = sparse.hstack(
            [pathway_bundle.test, role_bundle.test], format="csr", dtype=np.float32
        )
        return FoldFeatureBundle(
            train=combined_train,
            validation=combined_validation,
            test=combined_test,
            fitted_families=pathway_bundle.fitted_families + role_bundle.fitted_families,
            feature_names=pathway_bundle.feature_names + role_bundle.feature_names,
            registry={**pathway_bundle.registry, **role_bundle.registry},
        )


if __name__ == "__main__":
    main(
        ROOT / "configs" / "exp257_functional_role_burden_extended.yaml",
        fold_feature_builder=FunctionalRoleBurdenExtendedFoldBuilder(),
        runner_command="uv run python scripts/run_exp257_functional_role_burden_extended.py",
    )
