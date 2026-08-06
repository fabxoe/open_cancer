#!/usr/bin/env python
"""Run EXP-653: EXP-527 plus an isolated MMR-gene (MLH1/MSH2/MSH6/PMS2) proxy."""

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
from run_exp527_parser_v4_class_cosine_loo import LeaveOneOutClassCosineFoldBuilder
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp653_mmr_gene_proxy_exp527.yaml"
MARKER_KNOWLEDGE = ROOT / "knowledge" / "mmr_gene_proxy_v1.json"


class MmrGeneProxyFoldBuilder:
    def __init__(self) -> None:
        self.parent = LeaveOneOutClassCosineFoldBuilder()
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
        registry_record = self.fitted.descriptor.to_registry_record()
        registry_record["catalog_panels"] = self.fitted.catalog_panels
        registry_record["competition_intersections"] = self.fitted.intersections
        registry_record["missing_catalog_genes"] = self.fitted.missing_catalog_genes
        bundle = FoldFeatureBundle(
            train=sparse.hstack(
                [parent.train, self.train_features[train_indices]], format="csr"
            ),
            validation=sparse.hstack(
                [parent.validation, self.train_features[valid_indices]], format="csr"
            ),
            test=sparse.hstack([parent.test, self.test_features], format="csr"),
            fitted_families=parent.fitted_families + (self.fitted,),
            feature_names=parent.feature_names + self.fitted.descriptor.feature_names,
            registry={
                **parent.registry,
                self.fitted.descriptor.name: registry_record,
            },
            base_feature_names_to_drop=parent.base_feature_names_to_drop,
        )
        bundle, equivalents = remove_semantically_equivalent_features(
            bundle, parent.train, parent.feature_names
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
        runner_command="uv run python scripts/run_exp653_mmr_gene_proxy_exp527.py",
    )
