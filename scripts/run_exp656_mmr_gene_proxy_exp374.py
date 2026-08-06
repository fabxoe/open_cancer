#!/usr/bin/env python
"""Run EXP-656: EXP-374 (legacy) plus an isolated MMR-gene mutation proxy.

EXP-653 tested the identical MLH1/MSH2/MSH6/PMS2 panel on the EXP-527
(class-cosine native) parent: the aggregate Macro F1 gate passed but LGG
(-0.1304) and KIRC (-0.1071) collapsed well past the -0.05 threshold. This
reruns the same panel on the legacy EXP-374 parent, which has shown no
KIPAN/KIRC or GBMLGG/LGG collapse in prior direct interventions on that axis
(EXP-514, EXP-515, EXP-604) and a much lower Local-Public shift_gap.
"""

from __future__ import annotations

from scipy import sparse

from open_cancer.feature_family import (
    FoldFeatureBundle,
    remove_semantically_equivalent_features,
)
from open_cancer.observable_marker_features import ObservableMarkerFamily
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
)
from run_exp374_stop_isoform_residue_mask import build_fold_features
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp656_mmr_gene_proxy_exp374.yaml"
MARKER_KNOWLEDGE = ROOT / "knowledge" / "mmr_gene_proxy_v1.json"


class MmrGeneProxyFoldBuilder:
    def __init__(self) -> None:
        self.parent = build_fold_features()
        self.train = self.parent.train
        self.test = self.parent.test
        self.gene_columns = self.parent.gene_columns
        self.family = ObservableMarkerFamily(self.gene_columns, MARKER_KNOWLEDGE)
        self.fitted = self.family.fit(self.train.iloc[:1])
        self.train_features = self.fitted.transform(self.train)
        self.test_features = self.fitted.transform(self.test)

    def __call__(self, **kwargs) -> FoldFeatureBundle:
        parent = self.parent(**kwargs)
        train_indices = kwargs["train_indices"]
        valid_indices = kwargs["valid_indices"]
        base_train = kwargs["base_train"]
        base_feature_names = kwargs["base_feature_names"]
        registry_record = self.fitted.descriptor.to_registry_record()
        registry_record["catalog_panels"] = self.fitted.catalog_panels
        registry_record["competition_intersections"] = self.fitted.intersections
        registry_record["missing_catalog_genes"] = self.fitted.missing_catalog_genes

        # Check the new MMR-only candidate against the raw base Feature Spec
        # (not yet merged with parent), matching the EXP-302/EXP-229
        # precedent, so genuine duplicates are removed without ever
        # comparing the merged bundle against itself.
        candidate = FoldFeatureBundle(
            train=self.train_features[train_indices],
            validation=self.train_features[valid_indices],
            test=self.test_features,
            fitted_families=(self.fitted,),
            feature_names=self.fitted.descriptor.feature_names,
            registry={self.fitted.descriptor.name: registry_record},
        )
        candidate, equivalents = remove_semantically_equivalent_features(
            candidate, base_train, base_feature_names
        )

        bundle = FoldFeatureBundle(
            train=sparse.hstack([parent.train, candidate.train], format="csr"),
            validation=sparse.hstack(
                [parent.validation, candidate.validation], format="csr"
            ),
            test=sparse.hstack([parent.test, candidate.test], format="csr"),
            fitted_families=parent.fitted_families + candidate.fitted_families,
            feature_names=parent.feature_names + candidate.feature_names,
            registry={**parent.registry, **candidate.registry},
        )
        if equivalents:
            bundle.registry["mmr_semantic_equivalence_filter"] = {
                "definition_version": "1.0.0",
                "enabled": True,
                "output_dimension": len(bundle.feature_names),
                "fit_scope": "fold_train",
                "external_knowledge": None,
                "dropped": equivalents,
            }
        return bundle


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=MmrGeneProxyFoldBuilder(),
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        runner_command="uv run python scripts/run_exp656_mmr_gene_proxy_exp374.py",
    )
