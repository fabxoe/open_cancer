#!/usr/bin/env python
"""Write a deterministic residue-position QC report from sparse artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from open_cancer.position_diagnostics import diagnose_position_artifacts


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--feature-dir",
        type=Path,
        default=(
            ROOT
            / "data"
            / "processed"
            / "feature_factory"
            / "v1"
            / "exp078_max_residue_indicator"
        ),
    )
    parser.add_argument(
        "--position-feature",
        default="max_residue_position",
        choices=("min_residue_position", "max_residue_position"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports" / "analysis" / "residue_position_semantics_qc.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = diagnose_position_artifacts(
        args.feature_dir,
        position_feature=args.position_feature,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
