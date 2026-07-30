#!/usr/bin/env python
"""Validate History and all committed experiment/reproducibility JSON records."""

from __future__ import annotations

import json
from pathlib import Path

from open_cancer.validation import validate_history, validate_json_document


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    metrics_schema = root / "schemas/experiment_metrics.schema.json"
    reproducibility_schema = root / "schemas/reproducibility_manifest.schema.json"

    history_summary = validate_history(root / "EXPERIMENT_HISTORY.md")
    metrics_files = sorted((root / "reports").glob("exp*/metrics.json"))
    manifest_files = sorted((root / "reproducibility").glob("exp*/artifact_manifest.json"))

    for path in metrics_files:
        validate_json_document(path, metrics_schema)
    for path in manifest_files:
        validate_json_document(path, reproducibility_schema)

    print(
        json.dumps(
            {
                "history": history_summary,
                "metrics_files": len(metrics_files),
                "reproducibility_manifests": len(manifest_files),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
