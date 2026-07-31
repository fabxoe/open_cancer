#!/usr/bin/env python
"""Validate History and all committed experiment/reproducibility JSON records."""

from __future__ import annotations

import json
from pathlib import Path

from open_cancer.validation import (
    validate_experiment_record_identity,
    validate_history,
    validate_json_document,
    validate_portable_artifact_paths,
    validate_split_metadata,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    metrics_schema = root / "schemas/experiment_metrics.schema.json"
    reproducibility_schema = root / "schemas/reproducibility_manifest.schema.json"

    history_summary = validate_history(root / "EXPERIMENT_HISTORY.md")
    split_summary = validate_split_metadata(
        root / "data/splits/stratified_5fold_seed42.csv",
        root / "data/splits/stratified_5fold_seed42.meta.json",
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
                "canonical_split": split_summary,
                "metrics_files": len(metrics_files),
                "reproducibility_manifests": len(manifest_files),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
