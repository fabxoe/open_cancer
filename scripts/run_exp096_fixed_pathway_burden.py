#!/usr/bin/env python
"""Run EXP-096: Feature Spec v1 plus fixed canonical-pathway burden."""

from __future__ import annotations

import json

import pandas as pd

from open_cancer.abc_c_features import fixed_pathway_burden_family, load_fixed_groups
from open_cancer.feature_family import (
    FoldFeatureBundle,
    build_family_registry,
    remove_semantically_equivalent_features,
    transform_checked,
)
from open_cancer.hashing import sha256_file
from run_hotspot_xgb import ROOT, TEST_PATH, TRAIN_PATH, main


KNOWLEDGE_PATH = ROOT / "knowledge" / "canonical_pathways_sanchez_vega_v1.json"
MEMBERSHIP_PATH = (
    ROOT / "reports" / "exp096_fixed_pathway_burden" / "pathway_membership.json"
)


class FixedPathwayBurdenFoldBuilder:
    """Cache a stateless pathway matrix and align it to each canonical fold."""

    def __init__(self) -> None:
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
        family = fixed_pathway_burden_family(self.gene_columns, KNOWLEDGE_PATH)
        self.fitted = family.fit(self.train.iloc[:1])
        self.train_matrix = transform_checked(self.fitted, self.train)
        self.test_matrix = transform_checked(self.fitted, self.test)
        groups, document = load_fixed_groups(KNOWLEDGE_PATH, kind="pathways")
        MEMBERSHIP_PATH.parent.mkdir(parents=True, exist_ok=True)
        MEMBERSHIP_PATH.write_text(
            json.dumps(
                {
                    "knowledge_file": str(KNOWLEDGE_PATH.relative_to(ROOT)),
                    "knowledge_sha256": sha256_file(KNOWLEDGE_PATH),
                    "source_url": document["source_url"],
                    "source_commit": document["source_commit"],
                    "source_sha256": document["source_sha256"],
                    "extraction_policy": document["extraction_policy"],
                    "organizer_approval_reference": document[
                        "organizer_approval_reference"
                    ],
                    "competition_gene_count": len(self.gene_columns),
                    "pathways": {
                        name: {
                            "source_gene_nodes": list(genes),
                            "panel_intersection": list(self.fitted.intersections[name]),
                            "excluded_non_panel_nodes": [
                                gene
                                for gene in genes
                                if gene not in self.fitted.intersections[name]
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
        bundle = FoldFeatureBundle(
            train=self.train_matrix[train_indices],
            validation=self.train_matrix[valid_indices],
            test=self.test_matrix,
            fitted_families=(self.fitted,),
            feature_names=self.fitted.descriptor.feature_names,
            registry=build_family_registry((self.fitted,)),
        )
        bundle, _ = remove_semantically_equivalent_features(
            bundle,
            base_train,
            base_feature_names,
        )
        return bundle


if __name__ == "__main__":
    main(
        ROOT / "configs" / "exp096_fixed_pathway_burden.yaml",
        fold_feature_builder=FixedPathwayBurdenFoldBuilder(),
        runner_command="uv run python scripts/run_exp096_fixed_pathway_burden.py",
    )
