#!/usr/bin/env python
"""Verify EXP-005 inference from saved checkpoints and write evidence."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
import xgboost as xgb
import yaml
from scipy import sparse

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.hashing import sha256_file
from open_cancer.validation import validate_json_document, validate_submission


ROOT = Path(__file__).resolve().parents[1]
SLUG = "exp005_xgb_mutation_features"
REPRO_DIR = ROOT / "reproducibility" / SLUG
RESOLVED_CONFIG_PATH = REPRO_DIR / "config.resolved.yaml"
SUBMISSION_PATH = ROOT / "submissions" / f"{SLUG}.csv"
TEST_PROBABILITY_PATH = ROOT / "preds" / f"{SLUG}_test_proba.csv"
MODEL_DIR = ROOT / "models" / SLUG


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def git_output(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def main() -> None:
    config = yaml.safe_load(RESOLVED_CONFIG_PATH.read_text(encoding="utf-8"))
    expected_submission_sha = json.loads(
        (ROOT / "reports" / SLUG / "metrics.json").read_text(encoding="utf-8")
    )["artifacts"]["submission_sha256"]

    data_paths = [
        ROOT / config["data"]["train"]["path"],
        ROOT / config["data"]["test"]["path"],
        ROOT / config["data"]["sample_submission"]["path"],
        ROOT / config["split"]["path"],
    ]
    expected_hashes = [
        config["data"]["train"]["sha256"],
        config["data"]["test"]["sha256"],
        config["data"]["sample_submission"]["sha256"],
        config["split"]["sha256"],
    ]
    feature_paths = [
        ROOT / metadata["path"] for metadata in config["feature_outputs"].values()
    ]
    feature_hashes = [
        metadata["sha256"] for metadata in config["feature_outputs"].values()
    ]
    data_hashes_match = all(
        sha256_file(path) == expected
        for path, expected in zip(
            [*data_paths, *feature_paths],
            [*expected_hashes, *feature_hashes],
            strict=True,
        )
    )
    if not data_hashes_match:
        raise ValueError("원본·split·피처 해시가 resolved config와 다릅니다.")

    test_features = sparse.load_npz(
        ROOT / config["feature_outputs"]["test_features.npz"]["path"]
    )
    test_ids = pd.read_csv(
        ROOT / config["feature_outputs"]["test_ids.csv"]["path"], dtype=str
    )["ID"]
    test_meta = pd.read_csv(
        ROOT / config["data"]["test"]["path"], usecols=["ID"], dtype=str
    )
    if not test_ids.equals(test_meta["ID"]):
        raise ValueError("저장 피처와 test ID 순서가 다릅니다.")

    fold_count = config["split"]["n_splits"]
    probabilities = np.zeros(
        (len(test_ids), len(CLASS_LABELS)), dtype=np.float32
    )
    model_paths = [MODEL_DIR / f"fold_{fold:02d}.json" for fold in range(fold_count)]
    for model_path in model_paths:
        if not model_path.is_file():
            raise FileNotFoundError(f"체크포인트가 없습니다: {model_path}")
        model = xgb.XGBClassifier()
        model.load_model(model_path)
        probabilities += model.predict_proba(test_features).astype(np.float32) / fold_count

    reproduced_probability = pd.DataFrame({"ID": test_ids})
    reproduced_probability.loc[:, list(PROBABILITY_COLUMNS)] = probabilities
    original_probability = pd.read_csv(TEST_PROBABILITY_PATH)
    probability_max_abs_diff = float(
        np.max(
            np.abs(
                reproduced_probability[list(PROBABILITY_COLUMNS)].to_numpy()
                - original_probability[list(PROBABILITY_COLUMNS)].to_numpy()
            )
        )
    )

    sample_submission = pd.read_csv(
        ROOT / config["data"]["sample_submission"]["path"],
        dtype=str,
        keep_default_na=False,
    )
    reproduced_submission = sample_submission.copy()
    reproduced_submission["SUBCLASS"] = np.asarray(CLASS_LABELS)[
        probabilities.argmax(axis=1)
    ]
    with tempfile.TemporaryDirectory(prefix="exp005_inference_") as temporary:
        reproduced_path = Path(temporary) / SUBMISSION_PATH.name
        reproduced_submission.to_csv(reproduced_path, index=False, lineterminator="\n")
        validate_submission(reproduced_path, ROOT / config["data"]["test"]["path"])
        reproduced_sha = sha256_file(reproduced_path)

    original_sha = sha256_file(SUBMISSION_PATH)
    submission_sha_match = (
        reproduced_sha == original_sha == expected_submission_sha
    )
    test_label_agreement = float(
        (
            reproduced_submission["SUBCLASS"]
            == pd.read_csv(SUBMISSION_PATH, dtype=str)["SUBCLASS"]
        ).mean()
    )
    passed = (
        data_hashes_match
        and submission_sha_match
        and test_label_agreement == 1.0
        and probability_max_abs_diff <= 1e-6
    )
    if not passed:
        raise ValueError("체크포인트 추론 결과가 기존 제출과 일치하지 않습니다.")

    verified_at = datetime.now(timezone.utc).isoformat()
    environment = {
        "verified_at": verified_at,
        "platform": platform.platform(),
        "python": sys.version,
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
        "xgboost": xgb.__version__,
        "uv_lock_sha256": sha256_file(ROOT / "uv.lock"),
    }
    data_manifest = {
        "verified_at": verified_at,
        "files": [
            {
                **file_record(path),
                "shape": list(pd.read_csv(path).shape)
                if path.suffix == ".csv" and "features" not in path.name
                else None,
            }
            for path in [*data_paths, *feature_paths]
        ],
    }
    comparison = {
        "verified_at": verified_at,
        "data_hashes_match": data_hashes_match,
        "original_submission_sha256": original_sha,
        "reproduced_submission_sha256": reproduced_sha,
        "submission_sha256_match": submission_sha_match,
        "test_label_agreement": test_label_agreement,
        "test_probability_max_abs_diff": probability_max_abs_diff,
        "probability_atol": 1e-6,
        "probability_rtol": 1e-6,
        "passed": passed,
    }
    reproduction_metrics = {
        "experiment_id": "EXP-005",
        "verification_type": "checkpoint_inference",
        **comparison,
    }
    original_metrics = json.loads(
        (ROOT / "reports" / SLUG / "metrics.json").read_text(encoding="utf-8")
    )
    write_json(REPRO_DIR / "environment.json", environment)
    write_json(REPRO_DIR / "data_manifest.json", data_manifest)
    write_json(REPRO_DIR / "original_metrics.json", original_metrics)
    write_json(REPRO_DIR / "reproduction_metrics.json", reproduction_metrics)
    write_json(REPRO_DIR / "comparison.json", comparison)

    artifacts = [
        {"kind": "checkpoint", **file_record(path), "storage_uri": None}
        for path in model_paths
    ]
    artifacts.extend(
        [
            {"kind": "submission", **file_record(SUBMISSION_PATH), "storage_uri": None},
            {
                "kind": "test_probability",
                **file_record(TEST_PROBABILITY_PATH),
                "storage_uri": None,
            },
            {
                "kind": "resolved_config",
                **file_record(RESOLVED_CONFIG_PATH),
                "storage_uri": None,
            },
        ]
    )
    manifest = {
        "experiment_id": "EXP-005",
        "issue_number": 5,
        "reproducibility_status": "INFERENCE_VERIFIED",
        "source_commit": config["experiment"]["source_commit"],
        "source_tag": None,
        "dirty_worktree": config["experiment"]["dirty_worktree"],
        "data_manifest": str(
            (REPRO_DIR / "data_manifest.json").relative_to(ROOT)
        ),
        "environment": str((REPRO_DIR / "environment.json").relative_to(ROOT)),
        "release_url": None,
        "verifier": git_output("config", "user.name"),
        "verified_at": verified_at,
        "artifacts": artifacts,
        "verification": {
            "data_hashes_match": data_hashes_match,
            "submission_sha256_match": submission_sha_match,
            "test_label_agreement": test_label_agreement,
            "probability_atol": 1e-6,
            "probability_rtol": 1e-6,
            "passed": passed,
        },
    }
    write_json(REPRO_DIR / "artifact_manifest.json", manifest)
    validate_json_document(
        REPRO_DIR / "artifact_manifest.json",
        ROOT / "schemas" / "reproducibility_manifest.schema.json",
    )

    checksum_paths = [
        RESOLVED_CONFIG_PATH,
        REPRO_DIR / "environment.json",
        REPRO_DIR / "data_manifest.json",
        REPRO_DIR / "artifact_manifest.json",
        REPRO_DIR / "original_metrics.json",
        REPRO_DIR / "reproduction_metrics.json",
        REPRO_DIR / "comparison.json",
    ]
    checksum_lines = [
        f"{sha256_file(path)}  {path.name}" for path in checksum_paths
    ]
    (REPRO_DIR / "checksums.sha256").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8"
    )
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
