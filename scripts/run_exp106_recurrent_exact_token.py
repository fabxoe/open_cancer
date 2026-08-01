#!/usr/bin/env python
"""Run EXP-106: Feature Spec v1 plus fold-train recurrent exact tokens."""

from __future__ import annotations

import json

import pandas as pd

from open_cancer.abc_a_features import RecurrentExactTokenFamily
from open_cancer.feature_family import (
    fit_transform_family_set,
    remove_semantically_equivalent_features,
)
from run_hotspot_xgb import ROOT, TEST_PATH, TRAIN_PATH, main


class RecurrentExactTokenFoldBuilder:
    """Fit a fresh exact-token vocabulary inside every outer fold."""

    def __init__(self, *, min_support: int, max_features: int) -> None:
        self.train = pd.read_csv(TRAIN_PATH, dtype=str, keep_default_na=False)
        self.test = pd.read_csv(TEST_PATH, dtype=str, keep_default_na=False)
        self.gene_columns = tuple(
            column for column in self.train.columns if column not in {"ID", "SUBCLASS"}
        )
        self.min_support = min_support
        self.max_features = max_features

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
    ):
        family = RecurrentExactTokenFamily(
            gene_columns=self.gene_columns,
            min_support=self.min_support,
            max_features=self.max_features,
        )
        bundle = fit_transform_family_set(
            [family],
            fold_train=self.train.iloc[train_indices],
            validation=self.train.iloc[valid_indices],
            test=self.test,
            target=pd.Series(target),
        )
        bundle, equivalents = remove_semantically_equivalent_features(
            bundle,
            base_train,
            base_feature_names,
        )
        fitted = bundle.fitted_families[0]
        vocabulary_path = (
            ROOT
            / "reports"
            / "exp106_recurrent_exact_token"
            / "fold_vocabularies"
            / f"fold_{fold:02d}.json"
        )
        vocabulary_path.parent.mkdir(parents=True, exist_ok=True)
        vocabulary_path.write_text(
            json.dumps(
                {
                    "fold": fold,
                    "min_support": self.min_support,
                    "max_features": self.max_features,
                    "semantic_duplicates_dropped": equivalents,
                    "vocabulary": [
                        {"gene": gene, "token": token, "support": support}
                        for (gene, token), support in zip(
                            fitted.vocabulary, fitted.support, strict=True
                        )
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return bundle


if __name__ == "__main__":
    main(
        ROOT / "configs" / "exp106_recurrent_exact_token.yaml",
        fold_feature_builder=RecurrentExactTokenFoldBuilder(
            min_support=5,
            max_features=512,
        ),
    )
