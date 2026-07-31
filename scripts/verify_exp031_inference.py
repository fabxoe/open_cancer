#!/usr/bin/env python
"""Verify EXP-031 attempt 5 from checkpoints and write reproducibility evidence."""

from __future__ import annotations

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
from open_cancer.paths import relative_posix
from open_cancer.validation import validate_json_document, validate_submission


ROOT = Path(__file__).resolve().parents[1]
SLUG = "exp031_hotspot_extended"
REPRO_DIR = ROOT / "reproducibility" / SLUG
RESOLVED_CONFIG_PATH = REPRO_DIR / "config.resolved.yaml"
METRICS_PATH = ROOT / "reports" / SLUG / "metrics.json"
SUBMISSION_PATH = ROOT / "submissions" / f"{SLUG}.csv"
OOF_PATH = ROOT / "oof" / f"{SLUG}.csv"
TEST_PROBABILITY_PATH = ROOT / "preds" / f"{SLUG}_test_proba.csv"
MODEL_DIR = ROOT / "models" / SLUG
FEATURE_DIR = ROOT / "data" / "processed" / "hotspot_extended_features"


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": relative_posix(path, ROOT),
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
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    feature_report = json.loads(
        (FEATURE_DIR / "feature_report.json").read_text(encoding="utf-8")
    )

    input_hash_records = [
        (
            ROOT / config["data"]["train"]["path"],
            config["data"]["train"]["sha256"],
        ),
        (
            ROOT / config["data"]["test"]["path"],
            config["data"]["test"]["sha256"],
        ),
        (
            ROOT / config["data"]["sample_submission"]["path"],
            config["data"]["sample_submission"]["sha256"],
        ),
        (
            ROOT / config["split"]["path"],
            config["split"]["sha256"],
        ),
    ]
    feature_hash_records = [
        (Path(metadata["path"]), metadata["sha256"])
        for metadata in feature_report["outputs"].values()
    ]
    hash_records = [*input_hash_records, *feature_hash_records]
    data_hashes_match = all(
        path.is_file() and sha256_file(path) == expected
        for path, expected in hash_records
    )
    if not data_hashes_match:
        raise ValueError("원본·split·피처 해시가 실행 기록과 다릅니다.")

    test_features = sparse.load_npz(FEATURE_DIR / "test_features.npz")
    test_meta = pd.read_csv(
        ROOT / config["data"]["test"]["path"],
        usecols=["ID"],
        dtype=str,
    )
    fold_count = int(config["split"]["n_splits"])
    probabilities = np.zeros(
        (len(test_meta), len(CLASS_LABELS)),
        dtype=np.float32,
    )
    model_paths = [
        MODEL_DIR / f"fold_{fold:02d}.json" for fold in range(fold_count)
    ]
    for model_path in model_paths:
        if not model_path.is_file():
            raise FileNotFoundError(f"체크포인트가 없습니다: {model_path}")
        model = xgb.XGBClassifier()
        model.load_model(model_path)
        probabilities += (
            model.predict_proba(test_features).astype(np.float32) / fold_count
        )

    reproduced_probability = pd.DataFrame({"ID": test_meta["ID"]})
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
    probability_match = bool(
        np.allclose(
            reproduced_probability[list(PROBABILITY_COLUMNS)].to_numpy(),
            original_probability[list(PROBABILITY_COLUMNS)].to_numpy(),
            atol=1e-6,
            rtol=1e-6,
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
    with tempfile.TemporaryDirectory(prefix="exp031_inference_") as temporary:
        reproduced_path = Path(temporary) / SUBMISSION_PATH.name
        reproduced_submission.to_csv(
            reproduced_path,
            index=False,
            lineterminator="\n",
        )
        validate_submission(
            reproduced_path,
            ROOT / config["data"]["test"]["path"],
        )
        reproduced_sha = sha256_file(reproduced_path)

    original_sha = sha256_file(SUBMISSION_PATH)
    expected_sha = metrics["artifacts"]["submission_sha256"]
    submission_sha_match = (
        reproduced_sha == original_sha == expected_sha
    )
    original_submission = pd.read_csv(SUBMISSION_PATH, dtype=str)
    test_label_agreement = float(
        (
            reproduced_submission["SUBCLASS"]
            == original_submission["SUBCLASS"]
        ).mean()
    )
    passed = bool(
        data_hashes_match
        and probability_match
        and submission_sha_match
        and test_label_agreement == 1.0
    )
    if not passed:
        raise ValueError(
            "저장 checkpoint 추론이 원본 확률 또는 제출 파일과 일치하지 않습니다."
        )

    verified_at = datetime.now(timezone.utc).isoformat()
    environment_path = REPRO_DIR / "environment.json"
    data_manifest_path = REPRO_DIR / "data_manifest.json"
    original_metrics_path = REPRO_DIR / "original_metrics.json"
    reproduction_metrics_path = REPRO_DIR / "reproduction_metrics.json"
    comparison_path = REPRO_DIR / "comparison.json"
    manifest_path = REPRO_DIR / "artifact_manifest.json"
    reproduce_path = REPRO_DIR / "REPRODUCE.md"

    write_json(
        environment_path,
        {
            "verified_at": verified_at,
            "platform": platform.platform(),
            "python": sys.version,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "xgboost": xgb.__version__,
            "uv_lock_sha256": sha256_file(ROOT / "uv.lock"),
        },
    )
    write_json(
        data_manifest_path,
        {
            "verified_at": verified_at,
            "files": [
                {**file_record(path), "expected_sha256": expected}
                for path, expected in hash_records
            ],
        },
    )
    write_json(original_metrics_path, metrics)
    comparison = {
        "verified_at": verified_at,
        "data_hashes_match": data_hashes_match,
        "original_submission_sha256": original_sha,
        "reproduced_submission_sha256": reproduced_sha,
        "submission_sha256_match": submission_sha_match,
        "test_label_agreement": test_label_agreement,
        "test_probability_allclose": probability_match,
        "test_probability_max_abs_diff": probability_max_abs_diff,
        "probability_atol": 1e-6,
        "probability_rtol": 1e-6,
        "passed": passed,
    }
    write_json(comparison_path, comparison)
    write_json(
        reproduction_metrics_path,
        {
            "experiment_id": "EXP-031",
            "verification_type": "checkpoint_inference",
            **comparison,
        },
    )
    reproduce_path.write_text(
        (
            "# EXP-031 재현 절차\n\n"
            "원본 CSV를 `data/raw/`에 배치하고 다음 명령을 실행합니다.\n\n"
            "```bash\n"
            "uv sync --frozen\n"
            "uv run python scripts/run_exp031_hotspot_extended.py\n"
            "uv run python scripts/verify_exp031_inference.py\n"
            "```\n\n"
            "두 번째 명령은 저장 checkpoint에서 제출을 다시 생성하고 원본 "
            "제출 SHA-256, 라벨과 확률을 검증합니다.\n"
        ),
        encoding="utf-8",
    )

    artifacts = [
        {"kind": "checkpoint", **file_record(path), "storage_uri": None}
        for path in model_paths
    ]
    artifacts.extend(
        [
            {
                "kind": "oof_probability",
                **file_record(OOF_PATH),
                "storage_uri": None,
            },
            {
                "kind": "test_probability",
                **file_record(TEST_PROBABILITY_PATH),
                "storage_uri": None,
            },
            {
                "kind": "submission",
                **file_record(SUBMISSION_PATH),
                "storage_uri": None,
            },
            {
                "kind": "resolved_config",
                **file_record(RESOLVED_CONFIG_PATH),
                "storage_uri": None,
            },
            {
                "kind": "metrics",
                **file_record(METRICS_PATH),
                "storage_uri": None,
            },
        ]
    )
    manifest = {
        "experiment_id": "EXP-031",
        "issue_number": 31,
        "reproducibility_status": "INFERENCE_VERIFIED",
        "source_commit": config["experiment"]["source_commit"],
        "source_tag": None,
        "dirty_worktree": False,
        "data_manifest": relative_posix(data_manifest_path, ROOT),
        "environment": relative_posix(environment_path, ROOT),
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
    write_json(manifest_path, manifest)
    validate_json_document(
        manifest_path,
        ROOT / "schemas" / "reproducibility_manifest.schema.json",
    )

    checksum_paths = [
        RESOLVED_CONFIG_PATH,
        environment_path,
        data_manifest_path,
        manifest_path,
        original_metrics_path,
        reproduction_metrics_path,
        comparison_path,
    ]
    (REPRO_DIR / "checksums.sha256").write_text(
        "\n".join(
            f"{sha256_file(path)}  {path.name}" for path in checksum_paths
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
