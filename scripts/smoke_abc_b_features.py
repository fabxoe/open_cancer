#!/usr/bin/env python
"""Run a score-free smoke check of both ABC B feature families."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from open_cancer.abc_b_features import ComplexMorphologyFamily, FrequencyTierSpectrumFamily
from open_cancer.feature_family import fit_transform_family_set

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, default=ROOT / "data/raw/train.csv")
    parser.add_argument("--rows", type=int, default=200)
    args = parser.parse_args()
    if args.rows < 20:
        raise ValueError("smoke rows는 20 이상이어야 합니다.")
    frame = pd.read_csv(args.train, dtype=str, keep_default_na=False, nrows=args.rows)
    genes = tuple(frame.columns[2:])
    split_at = int(len(frame) * 0.75)
    fold_train = frame.iloc[:split_at].reset_index(drop=True)
    validation = frame.iloc[split_at:].reset_index(drop=True)
    bundle = fit_transform_family_set(
        [ComplexMorphologyFamily(genes), FrequencyTierSpectrumFamily(genes)],
        fold_train=fold_train,
        validation=validation,
        test=validation,
    )
    tier_family = bundle.fitted_families[1]
    print(
        json.dumps(
            {
                "status": "SMOKE_PASSED",
                "score_computed": False,
                "fold_train_rows": len(fold_train),
                "validation_rows": len(validation),
                "gene_columns": len(genes),
                "registry": bundle.registry,
                "validation_shape": list(bundle.validation.shape),
                "tier_gene_counts": {
                    str(tier + 1): sum(value == tier for value in tier_family.gene_tiers.values())
                    for tier in range(4)
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
