#!/usr/bin/env python
"""Verify EXP-003 inference by reproducing its submission from checkpoints."""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import scipy
import sklearn
import xgboost as xgb
import yaml
from scipy import sparse

from open_cancer.constants import CLASS_LABELS
from open_cancer.hashing import sha256_file
from open_cancer.validation import (
    validate_competition_data,
    validate_json_document,
    validate_submission,
)
from open_cancer.xgb_baseline import mutation_presence_matrix

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESOLVED_CONFIG = Path(
    "reproducibility/exp003_xgb_baseline/config.resolved.yaml"
)
DEFAULT_OUTPUT_DIR = Path("reproducibility/exp003_xgb_baseline")
PROBABILITY_ATOL = 1e-6
PROBABILITY_RTOL = 1e-6


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _relative(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _artifact(kind: str, path: Path, storage_uri: str | None = None) -> dict[str, Any]:
    return {
        "kind": kind,
        "path": _relative(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "storage_uri": storage_uri,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--resolved-config",
        type=Path,
        default=DEFAULT_RESOLVED_CONFIG,
        help="원본 실행에서 저장한 resolved config",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="재현 검증 증빙을 저장할 디렉터리",
    )
    return parser


def _load_config(path: Path) -> dict[str, Any]:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("resolved config는 mapping이어야 합니다.")
    if config.get("identity", {}).get("experiment_id") != "EXP-003":
        raise ValueError("이 검증기는 EXP-003 resolved config만 지원합니다.")
    if config.get("issue_number", config.get("identity", {}).get("issue_number")) != 3:
        raise ValueError("EXP-003의 Issue 번호는 3이어야 합니다.")
    return config


def _verify_data(
    config: dict[str, Any],
) -> tuple[pd.DataFrame, list[str], dict[str, Any]]:
    data_config = config["data"]
    paths = {
        key: (PROJECT_ROOT / value).resolve()
        for key, value in data_config.items()
    }
    actual_summary = validate_competition_data(
        paths["train_path"],
        paths["test_path"],
        paths["sample_submission_path"],
    )
    expected_manifest = config["data_manifest"]

    file_records: dict[str, Any] = {}
    all_match = True
    for key, config_key in (
        ("train", "train_path"),
        ("test", "test_path"),
        ("sample_submission", "sample_submission_path"),
    ):
        path = paths[config_key]
        expected_sha256 = expected_manifest["files"][key]["sha256"]
        actual_sha256 = actual_summary["files"][key]["sha256"]
        matches = actual_sha256 == expected_sha256
        all_match = all_match and matches
        file_records[key] = {
            "path": _relative(path),
            "size_bytes": path.stat().st_size,
            "expected_sha256": expected_sha256,
            "actual_sha256": actual_sha256,
            "matches": matches,
        }

    split_path = paths["split_path"]
    expected_split_sha256 = expected_manifest["split"]["sha256"]
    actual_split_sha256 = sha256_file(split_path)
    split_matches = actual_split_sha256 == expected_split_sha256
    all_match = all_match and split_matches
    file_records["split"] = {
        "path": _relative(split_path),
        "size_bytes": split_path.stat().st_size,
        "expected_sha256": expected_split_sha256,
        "actual_sha256": actual_split_sha256,
        "matches": split_matches,
    }

    feature_order_matches = (
        actual_summary["feature_order_sha256"]
        == expected_manifest["feature_order_sha256"]
    )
    all_match = all_match and feature_order_matches
    if not all_match:
        raise RuntimeError("원본 데이터, split 또는 feature 순서 해시가 일치하지 않습니다.")

    test = pd.read_csv(paths["test_path"], dtype=str, keep_default_na=False)
    gene_columns = list(test.columns[1:])
    return test, gene_columns, {
        "experiment_id": "EXP-003",
        "verified_at": _utc_now(),
        "train_rows": actual_summary["train_rows"],
        "test_rows": actual_summary["test_rows"],
        "gene_columns": actual_summary["gene_columns"],
        "feature_order": {
            "expected_sha256": expected_manifest["feature_order_sha256"],
            "actual_sha256": actual_summary["feature_order_sha256"],
            "matches": feature_order_matches,
        },
        "files": file_records,
        "all_match": all_match,
    }


def _predict_from_checkpoints(
    checkpoint_paths: list[Path],
    test_matrix: sparse.csr_matrix,
) -> np.ndarray:
    probabilities = np.zeros(
        (test_matrix.shape[0], len(CLASS_LABELS)),
        dtype=np.float32,
    )
    for checkpoint_path in checkpoint_paths:
        if not checkpoint_path.is_file():
            raise FileNotFoundError(f"체크포인트가 없습니다: {checkpoint_path}")
        model = xgb.XGBClassifier()
        model.load_model(checkpoint_path)
        if not np.array_equal(model.classes_, np.arange(len(CLASS_LABELS))):
            raise RuntimeError(f"클래스 순서가 다릅니다: {checkpoint_path}")
        fold_probabilities = model.predict_proba(test_matrix).astype(np.float32)
        probabilities += fold_probabilities / len(checkpoint_paths)

    if not np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-5):
        raise RuntimeError("재생성한 test 클래스 확률 합이 1이 아닙니다.")
    return probabilities


def _write_reproduce_guide(
    path: Path,
    *,
    source_commit: str,
    verification_commit: str,
    expected_submission_sha256: str,
) -> None:
    path.write_text(
        f"""# EXP-003 checkpoint 추론 재현

이 검증은 모델을 다시 학습하지 않고 저장된 fold checkpoint 5개로 test 추론만
다시 수행한다.

## 기준

- 학습 소스 commit: `{source_commit}`
- 검증 스크립트 commit: `{verification_commit}`
- 기대 제출 SHA-256: `{expected_submission_sha256}`

## 실행

```bash
uv sync --frozen

# artifact_manifest.json에 적힌 SHA-256과 일치하는 checkpoint 5개를
# models/exp003_xgb_baseline/에 배치한다.
uv run python scripts/verify_xgb_baseline_inference.py
```

성공하면 `reproduced_submission.csv`의 SHA-256이 원본
`submissions/exp003_xgb_baseline.csv`와 byte 단위로 같고,
`comparison.json`의 `passed`가 `true`가 된다.

현재 checkpoint의 `storage_uri`가 `null`이면 이 로컬 검증에는 사용되었지만 아직
GitHub Release에 업로드되지 않았다는 뜻이다. 실제 리더보드 제출 모델로 확정할 때
Release asset을 만들고 `artifact_manifest.json`에 URL을 기록한다.
""",
        encoding="utf-8",
    )


def main() -> None:
    started = time.perf_counter()
    args = _build_parser().parse_args()
    config_path = (PROJECT_ROOT / args.resolved_config).resolve()
    output_dir = (PROJECT_ROOT / args.output_dir).resolve()
    config = _load_config(config_path)

    dirty_at_start = bool(_git_output("status", "--porcelain"))
    if dirty_at_start:
        raise RuntimeError(
            "재현 검증은 clean worktree에서만 실행합니다. 변경을 먼저 커밋하세요."
        )
    verification_commit = _git_output("rev-parse", "HEAD")
    source_commit = config["identity"]["git_commit"]
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", source_commit, verification_commit],
        cwd=PROJECT_ROOT,
        check=True,
    )

    verified_at = _utc_now()
    test, gene_columns, data_manifest = _verify_data(config)
    test_matrix = mutation_presence_matrix(test, gene_columns)
    if bool(config["features"]["include_mutation_burden"]):
        test_burden = np.asarray(test_matrix.sum(axis=1), dtype=np.float32)
        test_matrix = sparse.hstack(
            [test_matrix, test_burden],
            format="csr",
            dtype=np.float32,
        )

    checkpoint_paths = [
        (PROJECT_ROOT / path).resolve() for path in config["outputs"]["checkpoints"]
    ]
    probabilities = _predict_from_checkpoints(checkpoint_paths, test_matrix)
    predictions = probabilities.argmax(axis=1)

    output_dir.mkdir(parents=True, exist_ok=True)
    reproduced_submission_path = output_dir / "reproduced_submission.csv"
    reproduced_probability_path = output_dir / "reproduced_test_probabilities.npy"
    pd.DataFrame(
        {
            "ID": test["ID"],
            "SUBCLASS": [CLASS_LABELS[index] for index in predictions],
        }
    ).to_csv(reproduced_submission_path, index=False, lineterminator="\n")
    np.save(reproduced_probability_path, probabilities)

    original_submission_path = (
        PROJECT_ROOT / config["outputs"]["submission"]
    ).resolve()
    submission_summary = validate_submission(
        reproduced_submission_path,
        PROJECT_ROOT / config["data"]["test_path"],
    )
    expected_submission_sha256 = config["outputs"]["submission_sha256"]
    original_submission_sha256 = sha256_file(original_submission_path)
    reproduced_submission_sha256 = submission_summary["sha256"]
    submission_sha256_match = (
        original_submission_sha256
        == reproduced_submission_sha256
        == expected_submission_sha256
    )

    original_submission = pd.read_csv(
        original_submission_path,
        dtype=str,
        keep_default_na=False,
    )
    reproduced_submission = pd.read_csv(
        reproduced_submission_path,
        dtype=str,
        keep_default_na=False,
    )
    test_label_agreement = float(
        (
            original_submission["SUBCLASS"]
            == reproduced_submission["SUBCLASS"]
        ).mean()
    )

    original_probability_path = (
        PROJECT_ROOT / config["outputs"]["test_probabilities"]
    ).resolve()
    probability_comparison: dict[str, Any]
    if original_probability_path.is_file():
        original_probabilities = np.load(original_probability_path)
        if original_probabilities.shape != probabilities.shape:
            raise RuntimeError("원본과 재생성 test 확률 shape이 다릅니다.")
        probability_comparison = {
            "available": True,
            "original_path": _relative(original_probability_path),
            "original_sha256": sha256_file(original_probability_path),
            "reproduced_path": _relative(reproduced_probability_path),
            "reproduced_sha256": sha256_file(reproduced_probability_path),
            "max_absolute_difference": float(
                np.max(np.abs(original_probabilities - probabilities))
            ),
            "atol": PROBABILITY_ATOL,
            "rtol": PROBABILITY_RTOL,
            "allclose": bool(
                np.allclose(
                    original_probabilities,
                    probabilities,
                    atol=PROBABILITY_ATOL,
                    rtol=PROBABILITY_RTOL,
                )
            ),
        }
    else:
        probability_comparison = {
            "available": False,
            "reason": "원본 test probability는 Git 제외 산출물이며 현재 환경에 없음",
            "reproduced_path": _relative(reproduced_probability_path),
            "reproduced_sha256": sha256_file(reproduced_probability_path),
        }

    passed = (
        data_manifest["all_match"]
        and submission_sha256_match
        and test_label_agreement == 1.0
        and probability_comparison.get("allclose", True)
    )
    if not passed:
        raise RuntimeError("체크포인트 추론이 원본 제출과 일치하지 않습니다.")

    environment_path = output_dir / "environment.json"
    data_manifest_path = output_dir / "data_manifest.json"
    original_metrics_path = output_dir / "original_metrics.json"
    reproduction_metrics_path = output_dir / "reproduction_metrics.json"
    comparison_path = output_dir / "comparison.json"
    reproduce_path = output_dir / "REPRODUCE.md"
    artifact_manifest_path = output_dir / "artifact_manifest.json"
    checksums_path = output_dir / "checksums.sha256"

    environment = {
        "verified_at": verified_at,
        "verification_commit": verification_commit,
        "os": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
        "scikit_learn": sklearn.__version__,
        "xgboost": xgb.__version__,
        "uv_lock_sha256": sha256_file(PROJECT_ROOT / "uv.lock"),
    }
    _write_json(environment_path, environment)
    _write_json(data_manifest_path, data_manifest)
    shutil.copyfile(
        PROJECT_ROOT / config["outputs"]["metrics"],
        original_metrics_path,
    )

    reproduction_metrics = {
        "experiment_id": "EXP-003",
        "verification_type": "checkpoint_inference",
        "verified_at": verified_at,
        "runtime_seconds": float(time.perf_counter() - started),
        "test_rows": len(test),
        "checkpoint_count": len(checkpoint_paths),
        "submission_sha256": reproduced_submission_sha256,
        "test_label_agreement": test_label_agreement,
        "probability_comparison": probability_comparison,
    }
    comparison = {
        "experiment_id": "EXP-003",
        "verification_type": "checkpoint_inference",
        "original_submission": {
            "path": _relative(original_submission_path),
            "sha256": original_submission_sha256,
        },
        "reproduced_submission": {
            "path": _relative(reproduced_submission_path),
            "sha256": reproduced_submission_sha256,
        },
        "expected_submission_sha256": expected_submission_sha256,
        "submission_byte_match": submission_sha256_match,
        "test_label_agreement": test_label_agreement,
        "probabilities": probability_comparison,
        "data_hashes_match": data_manifest["all_match"],
        "passed": passed,
    }
    _write_json(reproduction_metrics_path, reproduction_metrics)
    _write_json(comparison_path, comparison)
    _write_reproduce_guide(
        reproduce_path,
        source_commit=source_commit,
        verification_commit=verification_commit,
        expected_submission_sha256=expected_submission_sha256,
    )

    verifier = _git_output("config", "user.name") or "unknown"
    evidence_artifacts = [
        _artifact("checkpoint", path) for path in checkpoint_paths
    ] + [
        _artifact("resolved_config", config_path),
        _artifact("original_metrics", original_metrics_path),
        _artifact("original_submission", original_submission_path),
        _artifact("reproduced_submission", reproduced_submission_path),
        _artifact("reproduced_test_probabilities", reproduced_probability_path),
        _artifact("data_manifest", data_manifest_path),
        _artifact("environment", environment_path),
        _artifact("reproduction_metrics", reproduction_metrics_path),
        _artifact("comparison", comparison_path),
        _artifact("reproduce_guide", reproduce_path),
    ]
    artifact_manifest = {
        "experiment_id": "EXP-003",
        "issue_number": 3,
        "reproducibility_status": "INFERENCE_VERIFIED",
        "source_commit": source_commit,
        "source_tag": None,
        "dirty_worktree": dirty_at_start,
        "data_manifest": _relative(data_manifest_path),
        "environment": _relative(environment_path),
        "release_url": None,
        "verifier": verifier,
        "verified_at": verified_at,
        "artifacts": evidence_artifacts,
        "verification": {
            "data_hashes_match": data_manifest["all_match"],
            "submission_sha256_match": submission_sha256_match,
            "test_label_agreement": test_label_agreement,
            "probability_atol": PROBABILITY_ATOL,
            "probability_rtol": PROBABILITY_RTOL,
            "passed": passed,
        },
    }
    _write_json(artifact_manifest_path, artifact_manifest)
    validate_json_document(
        artifact_manifest_path,
        PROJECT_ROOT / "schemas" / "reproducibility_manifest.schema.json",
    )

    checksum_targets = [
        *checkpoint_paths,
        config_path,
        original_metrics_path,
        original_submission_path,
        reproduced_submission_path,
        reproduced_probability_path,
        data_manifest_path,
        environment_path,
        reproduction_metrics_path,
        comparison_path,
        reproduce_path,
        artifact_manifest_path,
    ]
    checksums_path.write_text(
        "".join(
            f"{sha256_file(path)}  {_relative(path)}\n"
            for path in checksum_targets
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "experiment_id": "EXP-003",
                "status": "INFERENCE_VERIFIED",
                "data_hashes_match": data_manifest["all_match"],
                "submission_sha256_match": submission_sha256_match,
                "test_label_agreement": test_label_agreement,
                "submission_sha256": reproduced_submission_sha256,
                "comparison": _relative(comparison_path),
                "artifact_manifest": _relative(artifact_manifest_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
