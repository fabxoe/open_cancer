"""Validation for explicitly approved small OOF probability files tracked in Git."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from open_cancer.constants import CLASS_LABELS

MAX_MANIFEST_BYTES = 25 * 1024 * 1024
MAX_REPOSITORY_BYTES = 100 * 1024 * 1024
SOURCE_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
REQUIRED_MANIFEST_KEYS = {
    "policy_version",
    "issue_number",
    "approval_url",
    "source_commit",
    "release_url",
    "generation_command",
    "class_order",
    "artifacts",
}


class SharedOofValidationError(ValueError):
    """Raised when a tracked shared OOF violates the repository contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SharedOofValidationError(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_manifest(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(document, dict), f"{path}: manifest는 JSON object여야 합니다.")
    missing = REQUIRED_MANIFEST_KEYS - set(document)
    _require(not missing, f"{path}: 필수 키 누락: {sorted(missing)}")
    return document


def validate_shared_oof_manifest(manifest_path: Path, repository_root: Path) -> dict[str, Any]:
    """Validate one approved shared-OOF manifest and every referenced CSV."""

    root = repository_root.resolve()
    shared_root = (root / "reports" / "shared_oof").resolve()
    manifest_path = manifest_path.resolve()
    _require(manifest_path.is_relative_to(shared_root), f"{manifest_path}: 허용 경로 밖입니다.")
    manifest = _load_manifest(manifest_path)

    _require(manifest["policy_version"] == 1, f"{manifest_path}: policy_version은 1이어야 합니다.")
    _require(int(manifest["issue_number"]) > 0, f"{manifest_path}: issue_number가 잘못됐습니다.")
    _require(str(manifest["approval_url"]).startswith("https://github.com/"), "approval_url은 GitHub HTTPS URL이어야 합니다.")
    _require(SOURCE_COMMIT_PATTERN.fullmatch(str(manifest["source_commit"])) is not None, "source_commit은 40자리 SHA여야 합니다.")
    _require(str(manifest["release_url"]).startswith("https://github.com/"), "release_url은 GitHub HTTPS URL이어야 합니다.")
    _require(bool(str(manifest["generation_command"]).strip()), "generation_command가 비어 있습니다.")
    _require(list(manifest["class_order"]) == list(CLASS_LABELS), "manifest class_order가 고정 26개 순서와 다릅니다.")

    artifacts = manifest["artifacts"]
    _require(isinstance(artifacts, list) and artifacts, f"{manifest_path}: artifacts가 비어 있습니다.")
    manifest_bytes = 0
    validated: list[dict[str, Any]] = []
    expected_probability_columns = list(CLASS_LABELS)

    for artifact in artifacts:
        _require(isinstance(artifact, dict), f"{manifest_path}: artifact는 object여야 합니다.")
        for key in ("path", "size_bytes", "sha256", "rows"):
            _require(key in artifact, f"{manifest_path}: artifact.{key} 누락")
        relative = Path(str(artifact["path"]))
        _require(not relative.is_absolute() and ".." not in relative.parts, f"{relative}: 안전하지 않은 경로")
        path = (root / relative).resolve()
        _require(path.is_relative_to(shared_root), f"{relative}: reports/shared_oof 밖의 파일")
        _require(path.suffix.lower() == ".csv", f"{relative}: CSV만 허용합니다.")
        _require(path.is_file(), f"{relative}: 파일이 없습니다.")
        size = path.stat().st_size
        _require(size == int(artifact["size_bytes"]), f"{relative}: size_bytes 불일치")
        _require(_sha256(path) == artifact["sha256"], f"{relative}: SHA-256 불일치")

        frame = pd.read_csv(path)
        _require(len(frame) == int(artifact["rows"]), f"{relative}: 행 수 불일치")
        _require("ID" in frame.columns, f"{relative}: ID 컬럼 누락")
        _require(frame["ID"].notna().all() and frame["ID"].is_unique, f"{relative}: ID는 비결측·고유여야 합니다.")
        probability_columns = [column for column in frame.columns if column != "ID"]
        _require(probability_columns == expected_probability_columns, f"{relative}: 26개 클래스 순서 불일치")
        forbidden = {"SUBCLASS", "SUBCLASS_TRUE", "TARGET", "LABEL", "fold"}
        _require(not forbidden.intersection(frame.columns), f"{relative}: 정답·fold 컬럼 포함 금지")
        values = frame[probability_columns].to_numpy(dtype=np.float64)
        _require(np.isfinite(values).all(), f"{relative}: NaN/Inf 확률")
        _require(((0.0 <= values) & (values <= 1.0)).all(), f"{relative}: 확률 범위 위반")
        _require(np.allclose(values.sum(axis=1), 1.0, atol=1e-5, rtol=1e-5), f"{relative}: 행 확률합이 1이 아님")

        manifest_bytes += size
        validated.append({"path": relative.as_posix(), "size_bytes": size, "rows": len(frame)})

    _require(manifest_bytes <= MAX_MANIFEST_BYTES, f"{manifest_path}: Issue/manifest 합계 25 MiB 초과")
    return {"manifest": manifest_path.relative_to(root).as_posix(), "bytes": manifest_bytes, "artifacts": validated}


def validate_shared_oof_repository(repository_root: Path) -> dict[str, Any]:
    """Validate every tracked shared OOF and the repository-wide size ceiling."""

    root = repository_root.resolve()
    shared_root = root / "reports" / "shared_oof"
    if not shared_root.exists():
        return {"manifests": 0, "artifacts": 0, "bytes": 0}
    manifests = sorted(shared_root.glob("*/manifest.json"))
    csv_files = sorted(shared_root.rglob("*.csv"))
    _require(manifests or not csv_files, "reports/shared_oof의 CSV에는 manifest.json이 필요합니다.")
    results = [validate_shared_oof_manifest(path, root) for path in manifests]
    referenced = {
        str(item["path"])
        for result in results
        for item in result["artifacts"]
    }
    actual = {path.relative_to(root).as_posix() for path in csv_files}
    _require(referenced == actual, f"shared OOF manifest 참조 불일치: missing={sorted(actual-referenced)}, stale={sorted(referenced-actual)}")
    total_bytes = sum(result["bytes"] for result in results)
    _require(total_bytes <= MAX_REPOSITORY_BYTES, "shared OOF 저장소 누적 100 MiB 한도 초과")
    return {
        "manifests": len(results),
        "artifacts": sum(len(result["artifacts"]) for result in results),
        "bytes": total_bytes,
    }
