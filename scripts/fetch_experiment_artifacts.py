#!/usr/bin/env python
"""Download and restore hash-verified team experiment artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from open_cancer.reproducibility import (
    DEFAULT_SHARED_ARTIFACT_KINDS,
    restore_reproducibility_artifacts,
)


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", required=True, help="예: EXP-253")
    parser.add_argument(
        "--kinds",
        nargs="+",
        default=list(DEFAULT_SHARED_ARTIFACT_KINDS),
        help="기본값: checkpoint oof_probability test_probability resolved_config",
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=ROOT / "release-assets" / "downloads",
        help="Release archive 임시 보관 경로(Git 제외)",
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = restore_reproducibility_artifacts(
        root=ROOT,
        experiment_id=args.experiment,
        kinds=args.kinds,
        download_dir=args.download_dir,
        overwrite=args.overwrite,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
