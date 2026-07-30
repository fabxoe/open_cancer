#!/usr/bin/env python
"""Validate one submission CSV against the local test file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from open_cancer.validation import validate_submission


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("submission", type=Path)
    parser.add_argument("--test", type=Path, default=Path("data/raw/test.csv"))
    args = parser.parse_args()
    summary = validate_submission(args.submission, args.test)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
