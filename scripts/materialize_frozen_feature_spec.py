#!/usr/bin/env python
"""Materialize one frozen ABC Feature Spec without training a model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from open_cancer.frozen_feature_specs import materialize_frozen_feature_spec

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", choices=("v1", "v2-performance", "v2-diversity"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = materialize_frozen_feature_spec(
        root=ROOT,
        name=args.spec,
        output_dir=args.output,
        train_path=ROOT / "data" / "raw" / "train.csv",
        test_path=ROOT / "data" / "raw" / "test.csv",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
