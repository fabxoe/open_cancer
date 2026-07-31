"""Build deterministic reproducibility bundles and update their manifests."""

from __future__ import annotations

import gzip
import json
import tarfile
from pathlib import Path
from typing import Any

from open_cancer.hashing import sha256_file


class ReproducibilityBundleError(ValueError):
    """Raised when a reproducibility bundle cannot be prepared safely."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ReproducibilityBundleError(message)


def _artifact_by_kind(
    artifacts: list[dict[str, Any]],
    kind: str,
) -> list[dict[str, Any]]:
    return [artifact for artifact in artifacts if artifact.get("kind") == kind]


def _write_deterministic_tar_gz(
    archive_path: Path,
    root: Path,
    artifact_paths: list[Path],
) -> None:
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with archive_path.open("wb") as raw_file:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_file, mtime=0) as gzip_file:
            with tarfile.open(fileobj=gzip_file, mode="w") as archive:
                for path in sorted(artifact_paths, key=lambda item: item.as_posix()):
                    arcname = path.relative_to(root).as_posix()
                    info = archive.gettarinfo(str(path), arcname=arcname)
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    info.mode = 0o644
                    with path.open("rb") as source:
                        archive.addfile(info, source)


def prepare_reproducibility_bundle(
    *,
    root: Path,
    slug: str,
    tag: str,
    repository: str,
    output_dir: Path,
) -> dict[str, Any]:
    """Create a deterministic archive and populate Release locations in a manifest."""
    root = root.resolve()
    manifest_path = root / "reproducibility" / slug / "artifact_manifest.json"
    _require(manifest_path.is_file(), f"artifact manifest가 없습니다: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts")
    _require(isinstance(artifacts, list), "manifest artifacts는 목록이어야 합니다.")

    required_kinds = (
        "checkpoint",
        "oof_probability",
        "test_probability",
        "submission",
        "resolved_config",
    )
    selected: list[dict[str, Any]] = []
    for kind in required_kinds:
        matches = _artifact_by_kind(artifacts, kind)
        _require(matches, f"재현 번들 필수 artifact가 없습니다: {kind}")
        selected.extend(matches)

    local_paths: list[Path] = []
    for artifact in selected:
        relative_path = Path(artifact["path"])
        _require(not relative_path.is_absolute(), f"절대경로는 사용할 수 없습니다: {relative_path}")
        local_path = root / relative_path
        _require(local_path.is_file(), f"artifact 파일이 없습니다: {relative_path.as_posix()}")
        actual_sha256 = sha256_file(local_path)
        _require(
            actual_sha256 == artifact.get("sha256"),
            f"artifact SHA-256이 manifest와 다릅니다: {relative_path.as_posix()}",
        )
        local_paths.append(local_path)

    archive_name = f"{slug}_repro.tar.gz"
    archive_path = output_dir.resolve() / archive_name
    _write_deterministic_tar_gz(archive_path, root, local_paths)

    release_url = f"https://github.com/{repository}/releases/tag/{tag}"
    download_url = f"https://github.com/{repository}/releases/download/{tag}/{archive_name}"
    for artifact in selected:
        artifact["storage_uri"] = f"{download_url}#{artifact['path']}"

    bundle_record = {
        "kind": "release_bundle",
        "path": f"release-assets/{archive_name}",
        "size_bytes": archive_path.stat().st_size,
        "sha256": sha256_file(archive_path),
        "storage_uri": download_url,
    }
    artifacts[:] = [
        artifact for artifact in artifacts if artifact.get("kind") != "release_bundle"
    ]
    artifacts.append(bundle_record)
    manifest["source_tag"] = tag
    manifest["release_url"] = release_url
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "manifest": manifest_path.relative_to(root).as_posix(),
        "archive": archive_path.as_posix(),
        "archive_name": archive_name,
        "size_bytes": bundle_record["size_bytes"],
        "sha256": bundle_record["sha256"],
        "release_url": release_url,
        "download_url": download_url,
    }
