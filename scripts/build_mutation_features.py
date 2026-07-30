"""Build sparse mutation-type features directly from raw train/test strings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from open_cancer.mutation_features import build_mutation_features


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, default=Path("data/raw/train.csv"))
    parser.add_argument("--test", type=Path, default=Path("data/raw/test.csv"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/mutation_type_features"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_mutation_features(args.train, args.test, args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
