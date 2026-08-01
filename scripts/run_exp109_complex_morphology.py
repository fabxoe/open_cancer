#!/usr/bin/env python
"""Run EXP-109: Feature Spec v1 plus complex-token morphology summaries."""

from __future__ import annotations

import pandas as pd

from open_cancer.abc_b_features import ComplexMorphologyFamily
from open_cancer.feature_family import (
    FoldFeatureBundle,
    build_family_registry,
    remove_semantically_equivalent_features,
    transform_checked,
)
from run_hotspot_xgb import ROOT, TEST_PATH, TRAIN_PATH, main


class ComplexMorphologyFoldBuilder:
    """Cache the stateless morphology matrix and align it to each fold."""

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
        family = ComplexMorphologyFamily(gene_columns=self.gene_columns)
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
        ROOT / "configs" / "exp109_complex_morphology.yaml",
        fold_feature_builder=ComplexMorphologyFoldBuilder(),
        runner_command="uv run python scripts/run_exp109_complex_morphology.py",
    )
