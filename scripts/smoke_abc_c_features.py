#!/usr/bin/env python
"""Run a score-free smoke check of both disabled-by-default C families."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from open_cancer.abc_c_features import fixed_pathway_burden_family, functional_role_burden_family
from open_cancer.feature_family import fit_transform_family_set

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, default=ROOT / "data/raw/train.csv")
    parser.add_argument("--rows", type=int, default=200)
    args = parser.parse_args()
    frame = pd.read_csv(args.train, dtype=str, keep_default_na=False, nrows=args.rows)
    genes = tuple(frame.columns[2:])
    split_at = int(len(frame) * 0.75)
    knowledge = ROOT / "knowledge/abc_c_compact_groups_v1.json"
    bundle = fit_transform_family_set(
        [
            fixed_pathway_burden_family(genes, knowledge),
            functional_role_burden_family(genes, knowledge),
        ],
        fold_train=frame.iloc[:split_at],
        validation=frame.iloc[split_at:],
        test=frame.iloc[split_at:],
    )
    print(json.dumps({
        "status": "SMOKE_PASSED",
        "score_computed": False,
        "competition_use_enabled": False,
        "registry": bundle.registry,
        "validation_shape": list(bundle.validation.shape),
        "intersections": {
            family.descriptor.name: {
                name: len(genes) for name, genes in family.intersections.items()
            }
            for family in bundle.fitted_families
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
