#!/usr/bin/env python
"""Validate History and all committed experiment/reproducibility JSON records."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from open_cancer.validation import (
    validate_experiment_record_identity,
    validate_history,
    validate_json_document,
    validate_portable_artifact_paths,
    validate_repository_contract,
    validate_split_metadata,
    validate_submission_storage_policy,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check-remote-storage",
        action="store_true",
        help="Release asset URL에 실제로 접근할 수 있는지 확인합니다.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    metrics_schema = root / "schemas/experiment_metrics.schema.json"
    reproducibility_schema = root / "schemas/reproducibility_manifest.schema.json"

    history_summary = validate_history(root / "EXPERIMENT_HISTORY.md")
    repository_contract_summary = validate_repository_contract(
        root,
        root / "EXPERIMENT_HISTORY.md",
    )
    split_summary = validate_split_metadata(
        root / "data/splits/stratified_5fold_seed42.csv",
        root / "data/splits/stratified_5fold_seed42.meta.json",
    )
    storage_summary = validate_submission_storage_policy(
        root / "EXPERIMENT_HISTORY.md",
        root / "reproducibility",
        root / "configs/reproducibility_policy.yaml",
        check_remote=args.check_remote_storage,
    )
    metrics_files = sorted((root / "reports").glob("exp*/metrics.json"))
    manifest_files = sorted((root / "reproducibility").glob("exp*/artifact_manifest.json"))

    for path in metrics_files:
        validate_json_document(path, metrics_schema)
        validate_experiment_record_identity(path)
        validate_portable_artifact_paths(path)
    for path in manifest_files:
        validate_json_document(path, reproducibility_schema)
        validate_experiment_record_identity(path)
        validate_portable_artifact_paths(path)

    print(
        json.dumps(
            {
                "history": history_summary,
                "repository_contract": repository_contract_summary,
                "canonical_split": split_summary,
                "submission_storage": storage_summary,
                "metrics_files": len(metrics_files),
                "reproducibility_manifests": len(manifest_files),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
