#!/usr/bin/env python
"""Run EXP-652: EXP-527 plus a fold-safe ordinary range_replacement gene indicator."""

from __future__ import annotations

from scipy import sparse

from open_cancer.feature_family import FoldFeatureBundle
from open_cancer.range_replacement_features import OrdinaryRangeReplacementGeneFamily
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
)
from run_exp527_parser_v4_class_cosine_loo import LeaveOneOutClassCosineFoldBuilder
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp652_range_replacement_any_exp527.yaml"


class RangeReplacementFoldBuilder:
    def __init__(self) -> None:
        self.parent = LeaveOneOutClassCosineFoldBuilder()
        self.train = self.parent.train
        self.test = self.parent.test
        self.gene_columns = self.parent.gene_columns
        self.family = OrdinaryRangeReplacementGeneFamily(self.gene_columns)

    def __call__(self, **kwargs) -> FoldFeatureBundle:
        parent = self.parent(**kwargs)
        train_indices = kwargs["train_indices"]
        valid_indices = kwargs["valid_indices"]
        fitted = self.family.fit(self.train.iloc[train_indices])
        train_features = fitted.transform(self.train.iloc[train_indices])
        valid_features = fitted.transform(self.train.iloc[valid_indices])
        test_features = fitted.transform(self.test)
        registry_record = fitted.descriptor.to_registry_record()
        return FoldFeatureBundle(
            train=sparse.hstack([parent.train, train_features], format="csr"),
            validation=sparse.hstack(
                [parent.validation, valid_features], format="csr"
            ),
            test=sparse.hstack([parent.test, test_features], format="csr"),
            fitted_families=parent.fitted_families + (fitted,),
            feature_names=parent.feature_names + fitted.descriptor.feature_names,
            registry={
                **parent.registry,
                fitted.descriptor.name: registry_record,
            },
            base_feature_names_to_drop=parent.base_feature_names_to_drop,
        )


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=RangeReplacementFoldBuilder(),
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        runner_command="uv run python scripts/run_exp652_range_replacement_any_exp527.py",
    )
