"""Upgrade legacy LightGBM reproducibility manifests to the current schema."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from open_cancer.validation import validate_json_document


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_VERIFICATION_FIELDS = (
    "data_hashes_match",
    "submission_sha256_match",
    "oof_label_agreement",
    "test_label_agreement",
    "probability_atol",
    "probability_rtol",
    "oof_macro_f1_delta",
    "passed",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _artifact(kind: str, path: Path) -> dict[str, Any]:
    return {
        "kind": kind,
        "path": path.relative_to(ROOT).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "storage_uri": None,
    }


def repair_lightgbm_manifest(
    *, slug: str, experiment_id: str, issue_number: int, verifier: str
) -> Path:
    reproducibility_dir = ROOT / "reproducibility" / slug
    manifest_path = reproducibility_dir / "artifact_manifest.json"
    comparison_path = reproducibility_dir / "comparison.json"
    resolved_path = reproducibility_dir / "config.resolved.yaml"
    legacy = json.loads(manifest_path.read_text())
    comparison = json.loads(comparison_path.read_text())
    resolved = yaml.safe_load(resolved_path.read_text())

    data_paths = (
        ("train", ROOT / "data/raw/train.csv"),
        ("test", ROOT / "data/raw/test.csv"),
        ("sample_submission", ROOT / "data/raw/sample_submission.csv"),
        ("split", ROOT / "data/splits/stratified_5fold_seed42.csv"),
    )
    data_manifest_path = reproducibility_dir / "data_manifest.json"
    _write_json(
        data_manifest_path,
        {
            "experiment_id": experiment_id,
            "files": [
                {
                    "kind": kind,
                    "path": path.relative_to(ROOT).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
                for kind, path in data_paths
            ],
        },
    )
    environment_path = reproducibility_dir / "environment.json"
    environment = resolved.get("environment", {})
    _write_json(
        environment_path,
        {
            "python": str(environment.get("python", "unknown")),
            "platform": str(environment.get("platform", "unknown")),
        },
    )
    candidates: list[tuple[str, Path]] = [
        *(('checkpoint', path) for path in sorted((ROOT / 'models' / slug).glob('fold_*.txt'))),
        ("oof_probability", ROOT / "oof" / f"{slug}.csv"),
        ("test_probability", ROOT / "preds" / f"{slug}_test_proba.csv"),
        ("submission", ROOT / "submissions" / f"{slug}.csv"),
        ("metrics", ROOT / "reports" / slug / "metrics.json"),
        ("resolved_config", resolved_path),
    ]
    artifacts = [_artifact(kind, path) for kind, path in candidates if path.is_file()]
    verification = {
        key: comparison[key]
        for key in ALLOWED_VERIFICATION_FIELDS
        if key in comparison
    }
    manifest = {
        "experiment_id": experiment_id,
        "issue_number": issue_number,
        "reproducibility_status": legacy["reproducibility_status"],
        "source_commit": legacy["source_commit"],
        "source_tag": None,
        "dirty_worktree": False,
        "data_manifest": data_manifest_path.relative_to(ROOT).as_posix(),
        "environment": environment_path.relative_to(ROOT).as_posix(),
        "release_url": None,
        "verifier": str(legacy.get("verifier", verifier)),
        "verified_at": legacy.get("verified_at"),
        "artifacts": artifacts,
        "verification": verification,
    }
    _write_json(manifest_path, manifest)
    validate_json_document(
        manifest_path, ROOT / "schemas/reproducibility_manifest.schema.json"
    )
    return manifest_path
