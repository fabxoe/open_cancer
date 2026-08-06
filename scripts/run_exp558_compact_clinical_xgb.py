#!/usr/bin/env python
"""Run EXP-558: parser-v4 compact clinical feature XGBoost baseline."""

from __future__ import annotations

import json

import pandas as pd

from open_cancer.compact_clinical_features import CompactClinicalMutationFamily
from open_cancer.feature_family import FoldFeatureBundle, build_family_registry
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp558_compact_clinical_xgb.yaml"
METADATA_DIR = ROOT / "data" / "processed" / "exp558_compact_clinical_xgb_features"


class CompactClinicalFoldBuilder:
    def __init__(self) -> None:
        self.train = pd.read_csv(ROOT / "data" / "raw" / "train.csv", dtype=str)
        self.test = pd.read_csv(ROOT / "data" / "raw" / "test.csv", dtype=str)
        self.gene_columns = tuple(
            column for column in self.train.columns if column not in {"ID", "SUBCLASS"}
        )
        self.family = CompactClinicalMutationFamily(
            self.gene_columns, hotspot_min_patient_count=5
        )

    def __call__(
        self, *, fold, train_indices, valid_indices, base_train,
        base_validation, base_test, base_feature_names, target,
    ) -> FoldFeatureBundle:
        del base_train, base_validation, base_test, target
        fitted = self.family.fit(self.train.iloc[train_indices])
        train_matrix = fitted.transform(self.train.iloc[train_indices])
        validation_matrix = fitted.transform(self.train.iloc[valid_indices])
        test_matrix = fitted.transform(self.test)
        METADATA_DIR.mkdir(parents=True, exist_ok=True)
        (METADATA_DIR / f"fold_{int(fold):02d}_compact_metadata.json").write_text(
            json.dumps(fitted.metadata(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return FoldFeatureBundle(
            train=train_matrix,
            validation=validation_matrix,
            test=test_matrix,
            fitted_families=(fitted,),
            feature_names=fitted.descriptor.feature_names,
            registry=build_family_registry((fitted,)),
            base_feature_names_to_drop=tuple(base_feature_names),
        )


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=CompactClinicalFoldBuilder(),
        runner_command=(
            "uv run python scripts/run_exp558_compact_clinical_xgb.py"
        ),
    )
