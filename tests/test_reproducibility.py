from __future__ import annotations

import json
import tarfile
from pathlib import Path

import pytest

from open_cancer.hashing import sha256_file
from open_cancer.reproducibility import (
    ReproducibilityBundleError,
    prepare_reproducibility_bundle,
    restore_reproducibility_artifacts,
)


def test_prepare_reproducibility_bundle_is_deterministic(tmp_path: Path) -> None:
    slug = "exp012_test"
    artifact_paths = {
        "checkpoint": "models/exp012_test/fold_00.json",
        "oof_probability": "oof/exp012_test.csv",
        "test_probability": "preds/exp012_test.csv",
        "submission": "submissions/exp012_test.csv",
        "resolved_config": "reproducibility/exp012_test/config.resolved.yaml",
    }
    artifacts = []
    for kind, relative in artifact_paths.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{kind}\n", encoding="utf-8")
        artifacts.append(
            {
                "kind": kind,
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "storage_uri": None,
            }
        )
    component_oof = tmp_path / "oof" / "exp010_component.csv"
    component_oof.write_text("component oof\n", encoding="utf-8")
    artifacts.append(
        {
            "kind": "component_oof_probability",
            "path": "oof/exp010_component.csv",
            "size_bytes": component_oof.stat().st_size,
            "sha256": sha256_file(component_oof),
            "storage_uri": None,
        }
    )
    audit = tmp_path / "models" / "exp012_test" / "fold_00_checkpoint_audit.json"
    audit.write_text("audit\n", encoding="utf-8")
    artifacts.append(
        {
            "kind": "checkpoint_iteration_audit",
            "path": "models/exp012_test/fold_00_checkpoint_audit.json",
            "size_bytes": audit.stat().st_size,
            "sha256": sha256_file(audit),
            "storage_uri": None,
        }
    )
    feature_manifest = tmp_path / "data" / "processed" / "exp012_test" / "feature_spec_manifest.json"
    feature_manifest.parent.mkdir(parents=True, exist_ok=True)
    feature_manifest.write_text("{}\n", encoding="utf-8")
    artifacts.append(
        {
            "kind": "feature_spec_manifest",
            "path": "data/processed/exp012_test/feature_spec_manifest.json",
            "size_bytes": feature_manifest.stat().st_size,
            "sha256": sha256_file(feature_manifest),
            "storage_uri": None,
        }
    )
    manifest_path = tmp_path / "reproducibility" / slug / "artifact_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "experiment_id": "EXP-012",
                "source_commit": "a" * 40,
                "source_tag": None,
                "release_url": None,
                "artifacts": artifacts,
            }
        ),
        encoding="utf-8",
    )

    first = prepare_reproducibility_bundle(
        root=tmp_path,
        slug=slug,
        tag="exp-012-repro-v1",
        repository="test/repo",
        output_dir=tmp_path / "dist",
    )
    second = prepare_reproducibility_bundle(
        root=tmp_path,
        slug=slug,
        tag="exp-012-repro-v1",
        repository="test/repo",
        output_dir=tmp_path / "dist",
    )

    assert first["sha256"] == second["sha256"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_tag"] == "exp-012-repro-v1"
    assert manifest["release_url"].endswith("/exp-012-repro-v1")
    assert all(
        artifact["storage_uri"].startswith("https://")
        for artifact in manifest["artifacts"]
    )
    with tarfile.open(first["archive"], mode="r:gz") as archive:
        assert "oof/exp010_component.csv" in archive.getnames()
        assert "models/exp012_test/fold_00_checkpoint_audit.json" in archive.getnames()
        assert "data/processed/exp012_test/feature_spec_manifest.json" in archive.getnames()


def _prepared_bundle(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    slug = "exp253_blend"
    files = {
        "checkpoint": "models/exp253_blend/fold_00.json",
        "oof_probability": "oof/exp253_blend.csv",
        "test_probability": "preds/exp253_blend_test_proba.csv",
        "submission": "submissions/exp253_blend.csv",
        "resolved_config": "reproducibility/exp253_blend/config.resolved.yaml",
    }
    artifacts = []
    for kind, relative in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"verified {kind}\n", encoding="utf-8")
        artifacts.append(
            {
                "kind": kind,
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "storage_uri": None,
            }
        )
    manifest_path = tmp_path / "reproducibility" / slug / "artifact_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "experiment_id": "EXP-253",
                "source_commit": "b" * 40,
                "source_tag": None,
                "release_url": None,
                "artifacts": artifacts,
            }
        ),
        encoding="utf-8",
    )
    summary = prepare_reproducibility_bundle(
        root=tmp_path,
        slug=slug,
        tag="exp-253-repro-v1",
        repository="test/repo",
        output_dir=tmp_path / "dist",
    )
    return Path(summary["archive"]), files


def test_restore_reproducibility_artifacts_selects_and_verifies(tmp_path: Path) -> None:
    archive_path, files = _prepared_bundle(tmp_path)
    checkpoint = tmp_path / files["checkpoint"]
    oof = tmp_path / files["oof_probability"]
    checkpoint.unlink()
    oof.unlink()

    summary = restore_reproducibility_artifacts(
        root=tmp_path,
        experiment_id="exp-253",
        kinds=("checkpoint", "oof_probability"),
        download_dir=tmp_path / "downloads",
        archive_path=archive_path,
    )

    assert summary["experiment_id"] == "EXP-253"
    assert sorted(summary["restored"]) == sorted(
        (files["checkpoint"], files["oof_probability"])
    )
    assert checkpoint.read_text(encoding="utf-8") == "verified checkpoint\n"
    assert oof.read_text(encoding="utf-8") == "verified oof_probability\n"
    assert (tmp_path / files["test_probability"]).is_file()


def test_restore_refuses_existing_mismatched_artifact_without_overwrite(
    tmp_path: Path,
) -> None:
    archive_path, files = _prepared_bundle(tmp_path)
    oof = tmp_path / files["oof_probability"]
    oof.write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ReproducibilityBundleError, match="--overwrite"):
        restore_reproducibility_artifacts(
            root=tmp_path,
            experiment_id="EXP-253",
            kinds=("oof_probability",),
            download_dir=tmp_path / "downloads",
            archive_path=archive_path,
        )


def test_restore_rejects_raw_data_path_before_extraction(tmp_path: Path) -> None:
    archive_path, _ = _prepared_bundle(tmp_path)
    manifest_path = (
        tmp_path / "reproducibility" / "exp253_blend" / "artifact_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"].append(
        {
            "kind": "oof_probability",
            "path": "data/raw/train.csv",
            "size_bytes": 1,
            "sha256": "0" * 64,
            "storage_uri": "https://example.invalid/bundle#data/raw/train.csv",
        }
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ReproducibilityBundleError, match="raw data"):
        restore_reproducibility_artifacts(
            root=tmp_path,
            experiment_id="EXP-253",
            kinds=("oof_probability",),
            download_dir=tmp_path / "downloads",
            archive_path=archive_path,
        )
