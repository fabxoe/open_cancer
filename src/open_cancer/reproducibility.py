"""Build deterministic reproducibility bundles and update their manifests."""

from __future__ import annotations

import gzip
import json
import os
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urldefrag, urlparse
from urllib.request import Request, urlopen

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


DEFAULT_SHARED_ARTIFACT_KINDS = (
    "checkpoint",
    "oof_probability",
    "test_probability",
    "resolved_config",
)


def find_artifact_manifest(root: Path, experiment_id: str) -> Path:
    """Find the one manifest whose recorded EXP-ID matches ``experiment_id``."""
    normalized = experiment_id.strip().upper()
    _require(normalized.startswith("EXP-"), "실험 ID는 EXP-NNN 형식이어야 합니다.")
    matches: list[Path] = []
    for path in sorted((root / "reproducibility").glob("exp*/artifact_manifest.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if str(manifest.get("experiment_id", "")).upper() == normalized:
            matches.append(path)
    _require(matches, f"artifact manifest를 찾을 수 없습니다: {normalized}")
    _require(len(matches) == 1, f"artifact manifest가 여러 개입니다: {normalized}")
    return matches[0]


def _safe_relative_artifact_path(value: str) -> Path:
    path = Path(value)
    _require(not path.is_absolute(), f"절대경로 artifact는 복원할 수 없습니다: {value}")
    _require(".." not in path.parts, f"상위 경로 artifact는 복원할 수 없습니다: {value}")
    _require(
        path.parts and path.parts[:2] != ("data", "raw"),
        "raw data는 복원 대상이 아닙니다.",
    )
    return path


def _download_bundle(url: str, destination: Path) -> None:
    parsed = urlparse(url)
    _require(parsed.scheme == "https", "Release bundle URL은 HTTPS여야 합니다.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "open-cancer-artifact-fetcher/1"})
    with urlopen(request, timeout=120) as response, destination.open("wb") as target:
        shutil.copyfileobj(response, target)


def restore_reproducibility_artifacts(
    *,
    root: Path,
    experiment_id: str,
    kinds: Iterable[str] = DEFAULT_SHARED_ARTIFACT_KINDS,
    download_dir: Path,
    overwrite: bool = False,
    archive_path: Path | None = None,
) -> dict[str, Any]:
    """Restore selected, hash-verified artifacts from a Release bundle.

    ``archive_path`` is an injection point for offline verification and tests. The
    normal CLI omits it and downloads the manifest's HTTPS Release asset.
    """
    root = root.resolve()
    manifest_path = find_artifact_manifest(root, experiment_id)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts")
    _require(isinstance(artifacts, list), "manifest artifacts는 목록이어야 합니다.")

    requested = tuple(dict.fromkeys(kinds))
    _require(requested, "artifact kind를 하나 이상 지정해야 합니다.")
    selected = [artifact for artifact in artifacts if artifact.get("kind") in requested]
    missing = sorted(set(requested) - {str(item.get("kind")) for item in selected})
    _require(not missing, f"manifest에 요청 artifact kind가 없습니다: {', '.join(missing)}")

    bundles = _artifact_by_kind(artifacts, "release_bundle")
    _require(len(bundles) == 1, "release_bundle artifact가 정확히 하나여야 합니다.")
    bundle = bundles[0]
    bundle_url, _ = urldefrag(str(bundle.get("storage_uri") or ""))
    _require(bundle_url, "release_bundle storage_uri가 비어 있습니다.")

    download_dir = download_dir.resolve()
    download_dir.mkdir(parents=True, exist_ok=True)
    downloaded = False
    if archive_path is None:
        archive_name = Path(urlparse(bundle_url).path).name
        _require(archive_name, "Release bundle 파일명을 해석할 수 없습니다.")
        archive_path = download_dir / archive_name
        if not archive_path.is_file() or sha256_file(archive_path) != bundle.get("sha256"):
            _download_bundle(bundle_url, archive_path)
            downloaded = True
    else:
        archive_path = archive_path.resolve()
    _require(archive_path.is_file(), f"Release bundle이 없습니다: {archive_path}")
    _require(
        archive_path.stat().st_size == bundle.get("size_bytes"),
        "Release bundle 크기가 manifest와 다릅니다.",
    )
    _require(
        sha256_file(archive_path) == bundle.get("sha256"),
        "Release bundle SHA-256이 manifest와 다릅니다.",
    )

    expected = {
        _safe_relative_artifact_path(str(item["path"])).as_posix(): item
        for item in selected
    }
    restored: list[str] = []
    reused: list[str] = []
    with tarfile.open(archive_path, mode="r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}
        _require(set(expected) <= set(members), "Release bundle에 요청 artifact가 누락되었습니다.")
        with tempfile.TemporaryDirectory(dir=download_dir, prefix="restore-") as stage_name:
            stage_root = Path(stage_name)
            staged: list[tuple[Path, Path]] = []
            for relative_name, artifact in expected.items():
                member = members[relative_name]
                _require(
                    member.isfile() and not member.issym() and not member.islnk(),
                    f"일반 파일이 아닌 archive member입니다: {relative_name}",
                )
                target = (root / relative_name).resolve()
                _require(
                    target == root or root in target.parents,
                    f"저장소 밖 artifact 경로입니다: {relative_name}",
                )
                if target.is_file():
                    if sha256_file(target) == artifact.get("sha256"):
                        reused.append(relative_name)
                        continue
                    _require(
                        overwrite,
                        "기존 artifact 해시가 다릅니다. --overwrite가 필요합니다: "
                        f"{relative_name}",
                    )
                source = archive.extractfile(member)
                _require(source is not None, f"archive member를 읽을 수 없습니다: {relative_name}")
                staged_path = stage_root / relative_name
                staged_path.parent.mkdir(parents=True, exist_ok=True)
                with source, staged_path.open("wb") as output:
                    shutil.copyfileobj(source, output)
                _require(
                    staged_path.stat().st_size == artifact.get("size_bytes"),
                    f"artifact 크기가 manifest와 다릅니다: {relative_name}",
                )
                _require(
                    sha256_file(staged_path) == artifact.get("sha256"),
                    f"artifact SHA-256이 manifest와 다릅니다: {relative_name}",
                )
                staged.append((staged_path, target))
            for staged_path, target in staged:
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged_path, target)
                restored.append(target.relative_to(root).as_posix())

    return {
        "experiment_id": manifest["experiment_id"],
        "manifest": manifest_path.relative_to(root).as_posix(),
        "release_url": manifest.get("release_url"),
        "bundle": archive_path.as_posix(),
        "downloaded": downloaded,
        "requested_kinds": list(requested),
        "restored": restored,
        "reused": reused,
    }


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

    optional_component_kinds = (
        "component_oof_probability",
        "component_test_probability",
        "component_resolved_config",
        "feature_spec_manifest",
        "checkpoint_iteration_audit",
    )
    for kind in optional_component_kinds:
        selected.extend(_artifact_by_kind(artifacts, kind))

    local_paths: list[Path] = []
    for artifact in selected:
        relative_path = _safe_relative_artifact_path(str(artifact["path"]))
        local_path = (root / relative_path).resolve()
        _require(
            local_path == root or root in local_path.parents,
            f"저장소 밖 artifact 경로입니다: {relative_path.as_posix()}",
        )
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
