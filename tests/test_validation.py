from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from open_cancer.validation import (
    ValidationError,
    create_stratified_folds,
    validate_competition_data,
    validate_json_document,
    validate_submission,
)


def _write_fixture_data(base: Path) -> tuple[Path, Path, Path]:
    train_path = base / "train.csv"
    test_path = base / "test.csv"
    sample_path = base / "sample_submission.csv"
    genes = ["GENE_A", "GENE_B"]

    train = pd.DataFrame(
        {
            "ID": [f"TRAIN_{index:04d}" for index in range(10)],
            "SUBCLASS": ["A", "B"] * 5,
            genes[0]: ["WT", "R1H"] * 5,
            genes[1]: ["WT"] * 10,
        }
    )
    test = pd.DataFrame(
        {
            "ID": ["TEST_0000", "TEST_0001"],
            genes[0]: ["WT", "R1H"],
            genes[1]: ["WT", ""],
        }
    )
    sample = pd.DataFrame({"ID": test["ID"], "SUBCLASS": ["A", "A"]})
    train.to_csv(train_path, index=False)
    test.to_csv(test_path, index=False)
    sample.to_csv(sample_path, index=False)
    return train_path, test_path, sample_path


def test_data_and_submission_contract(tmp_path: Path) -> None:
    train, test, sample = _write_fixture_data(tmp_path)
    summary = validate_competition_data(
        train,
        test,
        sample,
        strict_shape=False,
        expected_classes=("A", "B"),
    )
    assert summary["train_rows"] == 10
    assert summary["test_rows"] == 2
    assert summary["gene_columns"] == 2

    submission_summary = validate_submission(sample, test, expected_classes=("A", "B"))
    assert submission_summary["rows"] == 2


def test_submission_rejects_wrong_id_order(tmp_path: Path) -> None:
    _, test, sample = _write_fixture_data(tmp_path)
    submission = pd.read_csv(sample).iloc[::-1]
    bad_path = tmp_path / "bad_submission.csv"
    submission.to_csv(bad_path, index=False)
    with pytest.raises(ValidationError, match="순서"):
        validate_submission(bad_path, test, expected_classes=("A", "B"))


def test_stratified_fold_map_is_deterministic(tmp_path: Path) -> None:
    train, _, _ = _write_fixture_data(tmp_path)
    first = tmp_path / "folds_first.csv"
    second = tmp_path / "folds_second.csv"
    first_meta = create_stratified_folds(train, first, n_splits=5, seed=42)
    second_meta = create_stratified_folds(train, second, n_splits=5, seed=42)
    assert first.read_bytes() == second.read_bytes()
    assert first_meta["sha256"] == second_meta["sha256"]
    assert first_meta["fold_counts"] == {0: 2, 1: 2, 2: 2, 3: 2, 4: 2}


def test_experiment_metrics_schema(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    document = {
        "experiment_id": "EXP-001",
        "status": "COMPLETED",
        "owner": "tester",
        "issue_number": 2,
        "parent_experiment": None,
        "git_commit": "0123456789abcdef",
        "started_at": "2026-07-30T01:00:00Z",
        "finished_at": "2026-07-30T02:00:00Z",
        "primary_metric": "macro_f1",
        "split_id": "stratified_5fold_seed42",
        "folds": [{"fold": 0, "macro_f1": 0.5}],
        "oof": {"macro_f1": 0.5},
        "artifacts": {"report": "reports/exp001_test/report.md"},
    }
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    validate_json_document(path, root / "schemas/experiment_metrics.schema.json")


def test_reproducibility_schema(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    document = {
        "experiment_id": "EXP-001",
        "reproducibility_status": "MANIFEST_COMPLETE",
        "source_commit": "0123456789abcdef",
        "dirty_worktree": False,
        "data_manifest": "reproducibility/exp001_test/data_manifest.json",
        "environment": "reproducibility/exp001_test/environment.json",
        "artifacts": [
            {
                "kind": "submission",
                "path": "submissions/exp001_test.csv",
                "size_bytes": 10,
                "sha256": "a" * 64,
                "storage_uri": None,
            }
        ],
    }
    path = tmp_path / "artifact_manifest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    validate_json_document(path, root / "schemas/reproducibility_manifest.schema.json")
