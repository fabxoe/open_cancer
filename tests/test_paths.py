from __future__ import annotations

from pathlib import Path, PureWindowsPath

from open_cancer.paths import relative_posix


def test_relative_posix_uses_forward_slashes(tmp_path: Path) -> None:
    artifact = tmp_path / "reports" / "exp001_test" / "metrics.json"
    artifact.parent.mkdir(parents=True)
    artifact.touch()

    assert relative_posix(artifact, tmp_path) == "reports/exp001_test/metrics.json"


def test_windows_path_parts_can_be_persisted_as_posix() -> None:
    windows_path = PureWindowsPath(
        "reproducibility",
        "exp001_test",
        "config.resolved.yaml",
    )

    assert windows_path.as_posix() == (
        "reproducibility/exp001_test/config.resolved.yaml"
    )
