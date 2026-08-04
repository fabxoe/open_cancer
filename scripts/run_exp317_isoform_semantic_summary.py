#!/usr/bin/env python
"""Run EXP-317: EXP-229 plus 12 isoform-semantic sample summaries."""

from __future__ import annotations

import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FoldFeatureBundle, build_family_registry, transform_checked
from open_cancer.isoform_summary_features import IsoformSemanticSummaryFamily
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, TEST_PATH, TRAIN_PATH, main


CONFIG = ROOT / "configs" / "exp317_isoform_semantic_summary.yaml"
MEMBERSHIP = ROOT / "reports" / "exp317_isoform_semantic_summary" / "pathway_membership.json"
MANIFEST = ROOT / "knowledge" / "ensembl_isoform_annotation_b2_summary_v1.json"
CACHE = ROOT / "data" / "external" / "ensembl_release_116" / "competition_gene_isoform_index.json"
MANIFEST_SHA = "5848aca1106803f23288283aae7f01ece498534a769d3aaadbd0ca7259bae729"
CACHE_SHA = "b9565339f1755d5b07e782c39064207310fa6c254b2e915a15492f4f38903daa"


class IsoformSummaryFoldBuilder:
    def __init__(self) -> None:
        self.parent = PathwayMutationTypeFoldBuilder(membership_path=MEMBERSHIP)
        self.train = pd.read_csv(TRAIN_PATH, dtype=str, keep_default_na=False)
        self.test = pd.read_csv(TEST_PATH, dtype=str, keep_default_na=False)
        self.fitted = None
        self.train_matrix = None
        self.test_matrix = None

    def _prepare(self) -> None:
        if self.fitted is not None:
            return
        family = IsoformSemanticSummaryFamily(
            MANIFEST, CACHE, MANIFEST_SHA, CACHE_SHA
        )
        self.fitted = family.fit(self.train.iloc[:1])
        self.train_matrix = transform_checked(self.fitted, self.train)
        self.test_matrix = transform_checked(self.fitted, self.test)

    def __call__(self, **kwargs) -> FoldFeatureBundle:
        parent_bundle = self.parent(**kwargs)
        self._prepare()
        train_indices = kwargs["train_indices"]
        valid_indices = kwargs["valid_indices"]
        assert self.fitted is not None
        return FoldFeatureBundle(
            train=sparse.hstack(
                [parent_bundle.train, self.train_matrix[train_indices]], format="csr"
            ),
            validation=sparse.hstack(
                [parent_bundle.validation, self.train_matrix[valid_indices]], format="csr"
            ),
            test=sparse.hstack([parent_bundle.test, self.test_matrix], format="csr"),
            fitted_families=(*parent_bundle.fitted_families, self.fitted),
            feature_names=(*parent_bundle.feature_names, *self.fitted.descriptor.feature_names),
            registry={
                **parent_bundle.registry,
                **build_family_registry((self.fitted,)),
            },
        )


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=IsoformSummaryFoldBuilder(),
        runner_command="uv run python scripts/run_exp317_isoform_semantic_summary.py",
    )
