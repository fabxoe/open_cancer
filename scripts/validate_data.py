#!/usr/bin/env python
"""Validate local competition files and print a JSON summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from open_cancer.validation import validate_competition_data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path("data/raw"))
    args = parser.parse_args()
    summary = validate_competition_data(
        args.data_dir / "train.csv",
        args.data_dir / "test.csv",
        args.data_dir / "sample_submission.csv",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
