#!/usr/bin/env python
"""Run a score-free smoke check of both ABC A feature families."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml

from open_cancer.abc_a_features import AminoAcidChangeFamily, RecurrentExactTokenFamily
from open_cancer.feature_family import build_family_registry, transform_checked

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "abc_stack_a_families.yaml"
DEFAULT_TRAIN = ROOT / "data" / "raw" / "train.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--rows", type=int, default=200)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.rows < 20:
        raise ValueError("smoke rows는 20 이상이어야 합니다.")
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    frame = pd.read_csv(
        args.train,
        dtype=str,
        keep_default_na=False,
        nrows=args.rows,
    )
    gene_columns = tuple(frame.columns[2:])
    split_at = max(1, int(len(frame) * 0.75))
    fold_train = frame.iloc[:split_at].reset_index(drop=True)
    validation = frame.iloc[split_at:].reset_index(drop=True)
    exact_config = config["families"]["recurrent_exact_token"]
    amino_config = config["families"]["amino_acid_change"]

    exact = RecurrentExactTokenFamily(
        gene_columns=gene_columns,
        min_support=int(exact_config["min_support"]),
        max_features=int(exact_config["max_features"]),
    ).fit(fold_train)
    amino = AminoAcidChangeFamily(
        gene_columns=gene_columns,
        property_path=ROOT / amino_config["property_file"],
    ).fit(fold_train)
    exact_valid = transform_checked(exact, validation)
    amino_valid = transform_checked(amino, validation)

    print(
        json.dumps(
            {
                "status": "SMOKE_PASSED",
                "score_computed": False,
                "fold_train_rows": len(fold_train),
                "validation_rows": len(validation),
                "gene_columns": len(gene_columns),
                "registry": build_family_registry([exact, amino]),
                "validation_shapes": {
                    "recurrent_exact_token": list(exact_valid.shape),
                    "amino_acid_change": list(amino_valid.shape),
                },
                "exact_token_support": {
                    "minimum": min(exact.support),
                    "maximum": max(exact.support),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
