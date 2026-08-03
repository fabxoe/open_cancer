from __future__ import annotations

import json
import tarfile
from pathlib import Path

from open_cancer.hashing import sha256_file
from open_cancer.reproducibility import prepare_reproducibility_bundle


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
