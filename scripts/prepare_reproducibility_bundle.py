#!/usr/bin/env python
"""Prepare a deterministic leaderboard reproducibility bundle."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from open_cancer.reproducibility import prepare_reproducibility_bundle


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True, help="예: exp005_xgb_mutation_features")
    parser.add_argument("--tag", required=True, help="예: exp-005-repro-v1")
    parser.add_argument(
        "--repository",
        default="fabxoe/open_cancer",
        help="GitHub owner/repository",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "dist" / "reproducibility",
    )
    return parser.parse_args()


def git_commit_for_tag(tag: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", f"{tag}^{{commit}}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> None:
    args = parse_args()
    manifest_path = ROOT / "reproducibility" / args.slug / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tag_commit = git_commit_for_tag(args.tag)
    if tag_commit != manifest["source_commit"]:
        raise ValueError(
            "Release tag가 manifest source_commit을 가리키지 않습니다: "
            f"{tag_commit} != {manifest['source_commit']}"
        )
    summary = prepare_reproducibility_bundle(
        root=ROOT,
        slug=args.slug,
        tag=args.tag,
        repository=args.repository,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
