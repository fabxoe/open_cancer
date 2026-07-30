"""Create a protein-HGVS-normalized copy of train.csv without editing raw data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from open_cancer.hgvs import normalize_train


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("data/raw/train.csv"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/train_protein_hgvs.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("data/processed/train_protein_hgvs.report.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = normalize_train(args.input, args.output, args.report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
