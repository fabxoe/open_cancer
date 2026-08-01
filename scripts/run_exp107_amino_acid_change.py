#!/usr/bin/env python
"""Run EXP-107: Feature Spec v1 plus amino-acid property changes."""

from __future__ import annotations

import pandas as pd

from open_cancer.abc_a_features import AminoAcidChangeFamily
from open_cancer.feature_family import (
    FoldFeatureBundle,
    build_family_registry,
    remove_semantically_equivalent_features,
    transform_checked,
)
from run_hotspot_xgb import ROOT, TEST_PATH, TRAIN_PATH, main


class AminoAcidChangeFoldBuilder:
    """Cache the stateless family once, then align it to every outer fold."""

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
        family = AminoAcidChangeFamily(
            gene_columns=self.gene_columns,
            property_path=ROOT / "knowledge" / "amino_acid_properties_v1.json",
        )
        self.fitted = family.fit(self.train.iloc[:1])
        self.train_matrix = transform_checked(self.fitted, self.train)
        self.test_matrix = transform_checked(self.fitted, self.test)

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
        ROOT / "configs" / "exp107_amino_acid_change.yaml",
        fold_feature_builder=AminoAcidChangeFoldBuilder(),
        runner_command="uv run python scripts/run_exp107_amino_acid_change.py",
    )
