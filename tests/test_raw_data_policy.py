from __future__ import annotations

import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_only_gitkeep_is_tracked_in_raw_directory() -> None:
    result = _git("ls-files", "data/raw")

    assert result.returncode == 0
    assert result.stdout.splitlines() == ["data/raw/.gitkeep"]


def test_competition_raw_files_are_ignored() -> None:
    for filename in (
        "train.csv",
        "test.csv",
        "sample_submission.csv",
        "train_data_report.pdf",
    ):
        result = _git("check-ignore", f"data/raw/{filename}")
        assert result.returncode == 0, filename
