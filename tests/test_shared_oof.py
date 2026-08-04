from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from open_cancer.constants import CLASS_LABELS
from open_cancer.shared_oof import SharedOofValidationError, validate_shared_oof_repository


def _fixture(tmp_path: Path, *, with_label: bool = False) -> Path:
    root = tmp_path
    directory = root / "reports" / "shared_oof" / "issue1"
    directory.mkdir(parents=True)
    frame = pd.DataFrame({label: [1.0 if index == 0 else 0.0] for index, label in enumerate(CLASS_LABELS)})
    frame["ID"] = ["TRAIN_0001"]
    if with_label:
        frame["SUBCLASS_TRUE"] = ["ACC"]
    csv_path = directory / "probability.csv"
    frame.to_csv(csv_path, index=False)
    manifest = {
        "policy_version": 1,
        "issue_number": 1,
        "approval_url": "https://github.com/example/repo/issues/1",
        "source_commit": "a" * 40,
        "release_url": "https://github.com/example/repo/releases/tag/v1",
        "generation_command": "uv run python example.py",
        "class_order": list(CLASS_LABELS),
        "artifacts": [
            {
                "path": "reports/shared_oof/issue1/probability.csv",
                "size_bytes": csv_path.stat().st_size,
                "sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
                "rows": 1,
            }
        ],
    }
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root


def test_validate_shared_oof_repository_accepts_probability_only_csv(tmp_path: Path) -> None:
    summary = validate_shared_oof_repository(_fixture(tmp_path))
    assert summary["manifests"] == 1
    assert summary["artifacts"] == 1


def test_validate_shared_oof_repository_rejects_true_label(tmp_path: Path) -> None:
    with pytest.raises(SharedOofValidationError, match="클래스 순서 불일치|정답"):
        validate_shared_oof_repository(_fixture(tmp_path, with_label=True))
