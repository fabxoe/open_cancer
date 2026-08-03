#!/usr/bin/env python
"""Run EXP-229: EXP-223 plus pathway mutation-type composition counts."""

from __future__ import annotations

import json

import pandas as pd
from scipy import sparse

from open_cancer.abc_c_features import (
    fixed_pathway_burden_family,
    load_fixed_groups,
    pathway_mutation_type_family,
)
from open_cancer.feature_family import (
    FoldFeatureBundle,
    build_family_registry,
    remove_semantically_equivalent_features,
    transform_checked,
)
from open_cancer.hashing import sha256_file
from run_exp096_fixed_pathway_burden import KNOWLEDGE_PATH
from run_hotspot_xgb import ROOT, TEST_PATH, TRAIN_PATH, main


CONFIG = ROOT / "configs" / "exp229_pathway_mutation_types.yaml"
MEMBERSHIP = ROOT / "reports" / "exp229_pathway_mutation_types" / "pathway_membership.json"


class PathwayMutationTypeFoldBuilder:
    """Materialize the parent pathway family and the new 50-column candidate."""

    def __init__(self, membership_path=MEMBERSHIP) -> None:
        self.membership_path = membership_path
        self.train = pd.read_csv(TRAIN_PATH, dtype=str, keep_default_na=False)
        self.test = pd.read_csv(TEST_PATH, dtype=str, keep_default_na=False)
        self.gene_columns = tuple(
            column for column in self.train.columns if column not in {"ID", "SUBCLASS"}
        )
        self.fitted = None
        self.train_matrix = None
        self.test_matrix = None

    def _prepare(self) -> None:
        if self.fitted is not None:
            return
        families = (
            fixed_pathway_burden_family(self.gene_columns, KNOWLEDGE_PATH),
            pathway_mutation_type_family(self.gene_columns, KNOWLEDGE_PATH),
        )
        self.fitted = tuple(family.fit(self.train.iloc[:1]) for family in families)
        self.train_matrix = sparse.hstack(
            [transform_checked(fitted, self.train) for fitted in self.fitted], format="csr"
        )
        self.test_matrix = sparse.hstack(
            [transform_checked(fitted, self.test) for fitted in self.fitted], format="csr"
        )
        groups, document = load_fixed_groups(KNOWLEDGE_PATH, kind="pathways")
        intersections = self.fitted[0].intersections
        self.membership_path.parent.mkdir(parents=True, exist_ok=True)
        self.membership_path.write_text(
            json.dumps(
                {
                    "knowledge_file": str(KNOWLEDGE_PATH.relative_to(ROOT)),
                    "knowledge_sha256": sha256_file(KNOWLEDGE_PATH),
                    "source_url": document["source_url"],
                    "source_commit": document["source_commit"],
                    "source_sha256": document["source_sha256"],
                    "extraction_policy": document["extraction_policy"],
                    "organizer_approval_reference": document["organizer_approval_reference"],
                    "competition_gene_count": len(self.gene_columns),
                    "pathways": {
                        name: {
                            "source_gene_nodes": list(genes),
                            "panel_intersection": list(intersections[name]),
                            "excluded_non_panel_nodes": [
                                gene for gene in genes if gene not in intersections[name]
                            ],
                        }
                        for name, genes in groups.items()
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
        del fold, base_validation, base_test, target
        self._prepare()
        feature_names = tuple(
            name for fitted in self.fitted for name in fitted.descriptor.feature_names
        )
        bundle = FoldFeatureBundle(
            train=self.train_matrix[train_indices],
            validation=self.train_matrix[valid_indices],
            test=self.test_matrix,
            fitted_families=self.fitted,
            feature_names=feature_names,
            registry=build_family_registry(self.fitted),
        )
        bundle, _ = remove_semantically_equivalent_features(
            bundle, base_train, base_feature_names
        )
        return bundle


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=PathwayMutationTypeFoldBuilder(),
        runner_command="uv run python scripts/run_exp229_pathway_mutation_types.py",
    )
