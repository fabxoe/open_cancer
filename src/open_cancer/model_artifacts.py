"""Shared OOF/test probability and run-record contracts for ABC models."""

from __future__ import annotations

import json
import platform
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.experiment import validate_experiment_issue_pair
from open_cancer.hashing import sha256_file


class ModelArtifactError(ValueError):
    """Raised when model outputs or run records violate the shared contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ModelArtifactError(message)


def _validate_probability_matrix(probabilities: np.ndarray, rows: int) -> np.ndarray:
    matrix = np.asarray(probabilities, dtype=np.float64)
    _require(matrix.shape == (rows, len(CLASS_LABELS)), "확률 matrix shape가 고정 클래스 순서와 다릅니다.")
    _require(np.isfinite(matrix).all(), "확률에 NaN 또는 무한대가 있습니다.")
    _require(((matrix >= 0) & (matrix <= 1)).all(), "확률이 [0, 1] 범위를 벗어났습니다.")
    _require(
        np.allclose(matrix.sum(axis=1), 1.0, atol=1e-6, rtol=1e-6),
        "확률의 행 합이 1이 아닙니다.",
    )
    return matrix


def build_oof_probability_frame(
    *,
    ids: Sequence[str],
    true_labels: Sequence[str],
    folds: Sequence[int],
    probabilities: np.ndarray,
) -> pd.DataFrame:
    """Create the canonical OOF frame in immutable 26-class order."""
    row_count = len(ids)
    _require(len(true_labels) == row_count and len(folds) == row_count, "OOF 메타데이터 길이가 다릅니다.")
    matrix = _validate_probability_matrix(probabilities, row_count)
    labels = np.asarray(CLASS_LABELS)
    frame = pd.DataFrame(
        {
            "ID": list(ids),
            "SUBCLASS_TRUE": list(true_labels),
            "SUBCLASS_PRED": labels[matrix.argmax(axis=1)],
            "FOLD": np.asarray(folds, dtype=np.int64),
        }
    )
    frame.loc[:, list(PROBABILITY_COLUMNS)] = matrix
    validate_oof_probability_frame(frame, expected_ids=ids, expected_true_labels=true_labels)
    return frame


def build_test_probability_frame(
    *,
    ids: Sequence[str],
    probabilities: np.ndarray,
) -> pd.DataFrame:
    """Create the canonical test probability frame in immutable 26-class order."""
    matrix = _validate_probability_matrix(probabilities, len(ids))
    frame = pd.DataFrame({"ID": list(ids)})
    frame.loc[:, list(PROBABILITY_COLUMNS)] = matrix
    validate_test_probability_frame(frame, expected_ids=ids)
    return frame


def validate_oof_probability_frame(
    frame: pd.DataFrame,
    *,
    expected_ids: Sequence[str],
    expected_true_labels: Sequence[str],
    expected_folds: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Validate OOF IDs, labels, folds, prediction labels, and probabilities."""
    expected_columns = ["ID", "SUBCLASS_TRUE", "SUBCLASS_PRED", "FOLD", *PROBABILITY_COLUMNS]
    _require(list(frame.columns) == expected_columns, "OOF 열 또는 열 순서가 공통 계약과 다릅니다.")
    _require(frame["ID"].tolist() == list(expected_ids), "OOF ID 값 또는 순서가 다릅니다.")
    _require(not frame["ID"].duplicated().any(), "OOF ID가 중복됩니다.")
    _require(
        frame["SUBCLASS_TRUE"].tolist() == list(expected_true_labels),
        "OOF 정답 값 또는 순서가 다릅니다.",
    )
    if expected_folds is not None:
        _require(frame["FOLD"].tolist() == list(expected_folds), "OOF fold 값 또는 순서가 다릅니다.")
    _require(pd.api.types.is_integer_dtype(frame["FOLD"]), "OOF FOLD는 정수여야 합니다.")
    matrix = _validate_probability_matrix(
        frame.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(), len(frame)
    )
    predicted = np.asarray(CLASS_LABELS)[matrix.argmax(axis=1)].tolist()
    _require(frame["SUBCLASS_PRED"].tolist() == predicted, "OOF 예측 라벨이 확률 argmax와 다릅니다.")
    invalid_true = sorted(set(frame["SUBCLASS_TRUE"]) - set(CLASS_LABELS))
    _require(not invalid_true, f"OOF에 허용되지 않은 정답 클래스가 있습니다: {invalid_true}")
    return {"rows": len(frame), "class_order": list(CLASS_LABELS), "folds": sorted(frame["FOLD"].unique().tolist())}


def validate_test_probability_frame(
    frame: pd.DataFrame,
    *,
    expected_ids: Sequence[str],
) -> dict[str, Any]:
    """Validate test IDs and immutable 26-class probability columns."""
    expected_columns = ["ID", *PROBABILITY_COLUMNS]
    _require(list(frame.columns) == expected_columns, "test 확률 열 또는 열 순서가 공통 계약과 다릅니다.")
    _require(frame["ID"].tolist() == list(expected_ids), "test 확률 ID 값 또는 순서가 다릅니다.")
    _require(not frame["ID"].duplicated().any(), "test 확률 ID가 중복됩니다.")
    _validate_probability_matrix(frame.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(), len(frame))
    return {"rows": len(frame), "class_order": list(CLASS_LABELS)}


def _relative_file_record(path: Path, root: Path) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(root.resolve()).as_posix()
    except ValueError as error:
        raise ModelArtifactError(f"저장소 밖의 파일은 manifest에 기록할 수 없습니다: {path}") from error
    _require(resolved.is_file(), f"manifest 대상 파일이 없습니다: {relative}")
    return {"path": relative, "size_bytes": resolved.stat().st_size, "sha256": sha256_file(resolved)}


def write_model_run_records(
    *,
    root: Path,
    output_dir: Path,
    experiment_id: str,
    issue_number: int,
    source_commit: str,
    resolved_config: Mapping[str, Any],
    metrics: Mapping[str, Any],
    data_files: Mapping[str, Path],
    artifacts: Mapping[str, Path],
    environment: Mapping[str, Any] | None = None,
) -> dict[str, Path]:
    """Write resolved config, metrics, data and artifact manifests together."""
    validate_experiment_issue_pair(experiment_id, issue_number)
    _require(
        re.fullmatch(r"[0-9a-f]{7,40}", source_commit) is not None,
        "Git commit SHA가 올바르지 않습니다.",
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_path = output_dir / "config.resolved.yaml"
    metrics_path = output_dir / "metrics.json"
    environment_path = output_dir / "environment.json"
    data_manifest_path = output_dir / "data_manifest.json"
    artifact_manifest_path = output_dir / "artifact_manifest.json"

    resolved_path.write_text(
        yaml.safe_dump(dict(resolved_config), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    metrics_path.write_text(json.dumps(dict(metrics), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    environment_document = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        **dict(environment or {}),
    }
    environment_path.write_text(
        json.dumps(environment_document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    data_document = {
        "experiment_id": experiment_id,
        "files": [
            {"kind": kind, **_relative_file_record(path, root)}
            for kind, path in sorted(data_files.items())
        ],
    }
    data_manifest_path.write_text(
        json.dumps(data_document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    artifact_records = [
        {"kind": kind, **_relative_file_record(path, root), "storage_uri": None}
        for kind, path in sorted(artifacts.items())
    ]
    artifact_records.extend(
        [
            {"kind": "resolved_config", **_relative_file_record(resolved_path, root), "storage_uri": None},
            {"kind": "metrics", **_relative_file_record(metrics_path, root), "storage_uri": None},
        ]
    )
    artifact_document = {
        "experiment_id": experiment_id,
        "issue_number": issue_number,
        "reproducibility_status": "MANIFEST_COMPLETE",
        "source_commit": source_commit,
        "source_tag": None,
        "dirty_worktree": False,
        "data_manifest": _relative_file_record(data_manifest_path, root)["path"],
        "environment": _relative_file_record(environment_path, root)["path"],
        "release_url": None,
        "artifacts": artifact_records,
    }
    artifact_manifest_path.write_text(
        json.dumps(artifact_document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "resolved_config": resolved_path,
        "metrics": metrics_path,
        "environment": environment_path,
        "data_manifest": data_manifest_path,
        "artifact_manifest": artifact_manifest_path,
    }
