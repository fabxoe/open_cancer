#!/usr/bin/env python
"""Create the canonical stratified fold map and metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from open_cancer.validation import create_stratified_folds


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, default=Path("data/raw/train.csv"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/splits/stratified_5fold_seed42.csv"),
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("data/splits/stratified_5fold_seed42.meta.json"),
    )
    parser.add_argument("--n-splits", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    metadata = create_stratified_folds(
        args.train,
        args.output,
        n_splits=args.n_splits,
        seed=args.seed,
    )
    args.metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
