#!/usr/bin/env python
"""Run EXP-110: Feature Spec v1 plus fold-train frequency-tier spectrum."""

from __future__ import annotations

import json

import pandas as pd

from open_cancer.abc_b_features import FrequencyTierSpectrumFamily
from open_cancer.feature_family import (
    fit_transform_family_set,
    remove_semantically_equivalent_features,
)
from run_hotspot_xgb import ROOT, TEST_PATH, TRAIN_PATH, main


class FrequencyTierSpectrumFoldBuilder:
    """Fit four gene-frequency tiers independently in every outer fold."""

    def __init__(self, *, tier_count: int = 4) -> None:
        self.train = pd.read_csv(TRAIN_PATH, dtype=str, keep_default_na=False)
        self.test = pd.read_csv(TEST_PATH, dtype=str, keep_default_na=False)
        self.gene_columns = tuple(
            column for column in self.train.columns if column not in {"ID", "SUBCLASS"}
        )
        self.tier_count = tier_count

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
        del base_validation, base_test
        family = FrequencyTierSpectrumFamily(
            gene_columns=self.gene_columns,
            tier_count=self.tier_count,
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
        mapping_path = (
            ROOT
            / "reports"
            / "exp110_frequency_tier_spectrum"
            / "fold_tier_mappings"
            / f"fold_{fold:02d}.json"
        )
        mapping_path.parent.mkdir(parents=True, exist_ok=True)
        mapping_path.write_text(
            json.dumps(
                {
                    "fold": fold,
                    "tier_count": self.tier_count,
                    "rule": "mutation_presence_support_then_gene_lexical",
                    "semantic_duplicates_dropped": equivalents,
                    "genes": [
                        {
                            "gene": gene,
                            "tier": fitted.gene_tiers[gene] + 1,
                            "fold_train_support": fitted.gene_support[gene],
                        }
                        for gene in self.gene_columns
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
        ROOT / "configs" / "exp110_frequency_tier_spectrum.yaml",
        fold_feature_builder=FrequencyTierSpectrumFoldBuilder(tier_count=4),
        runner_command="uv run python scripts/run_exp110_frequency_tier_spectrum.py",
    )
