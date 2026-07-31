from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from open_cancer.validation import (
    ValidationError,
    create_stratified_folds,
    validate_competition_data,
    validate_experiment_record_identity,
    validate_history,
    validate_json_document,
    validate_portable_artifact_paths,
    validate_split_metadata,
    validate_submission,
    validate_submission_storage_policy,
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
        "experiment_id": "EXP-012",
        "status": "COMPLETED",
        "owner": "tester",
        "issue_number": 12,
        "parent_experiment": None,
        "git_commit": "0123456789abcdef",
        "started_at": "2026-07-30T01:00:00Z",
        "finished_at": "2026-07-30T02:00:00Z",
        "primary_metric": "macro_f1",
        "split_id": "stratified_5fold_seed42",
        "folds": [{"fold": 0, "macro_f1": 0.5}],
        "oof": {"macro_f1": 0.5},
        "artifacts": {"report": "reports/exp012_test/report.md"},
    }
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    validate_json_document(path, root / "schemas/experiment_metrics.schema.json")
    assert validate_experiment_record_identity(path)["issue_number"] == 12


def test_reproducibility_schema(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    document = {
        "experiment_id": "EXP-012",
        "issue_number": 12,
        "reproducibility_status": "MANIFEST_COMPLETE",
        "source_commit": "0123456789abcdef",
        "dirty_worktree": False,
        "data_manifest": "reproducibility/exp012_test/data_manifest.json",
        "environment": "reproducibility/exp012_test/environment.json",
        "artifacts": [
            {
                "kind": "submission",
                "path": "submissions/exp012_test.csv",
                "size_bytes": 10,
                "sha256": "a" * 64,
                "storage_uri": None,
            }
        ],
    }
    path = tmp_path / "artifact_manifest.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    validate_json_document(path, root / "schemas/reproducibility_manifest.schema.json")
    assert validate_experiment_record_identity(path)["issue_number"] == 12


def test_experiment_record_rejects_mismatched_issue(tmp_path: Path) -> None:
    path = tmp_path / "metrics.json"
    path.write_text(
        json.dumps({"experiment_id": "EXP-012", "issue_number": 13}),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="Issue #12"):
        validate_experiment_record_identity(path)


def test_portable_artifact_paths_reject_windows_separator(tmp_path: Path) -> None:
    path = tmp_path / "metrics.json"
    path.write_text(
        json.dumps({"artifacts": {"submission": "submissions\\exp012_test.csv"}}),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="경로는 '/'"):
        validate_portable_artifact_paths(path)


def test_split_metadata_rejects_modified_split(tmp_path: Path) -> None:
    split_path = tmp_path / "split.csv"
    split_path.write_text("ID,fold\nA,0\n", encoding="utf-8")
    metadata_path = tmp_path / "split.meta.json"
    metadata_path.write_text(
        json.dumps(
            {
                "path": "data/splits/split.csv",
                "sha256": "0" * 64,
                "rows": 1,
                "n_splits": 2,
                "seed": 42,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="공용 split SHA-256"):
        validate_split_metadata(split_path, metadata_path)


def _write_storage_policy_fixture(tmp_path: Path, *, storage_uri: str | None) -> tuple[Path, Path, Path]:
    history_path = tmp_path / "EXPERIMENT_HISTORY.md"
    history_path.write_text(
        """# 실험 기록

## 리더보드 제출 이력

| 제출 시각 | 실험 ID | Issue |
|---|---|---|
| 2026-07-31T00:00:00Z | EXP-012 | #12 |

## 재현성 검증 이력
""",
        encoding="utf-8",
    )
    reproducibility_root = tmp_path / "reproducibility"
    manifest_dir = reproducibility_root / "exp012_test"
    manifest_dir.mkdir(parents=True)
    artifact_kinds = (
        "checkpoint",
        "oof_probability",
        "test_probability",
        "submission",
        "resolved_config",
        "release_bundle",
    )
    (manifest_dir / "artifact_manifest.json").write_text(
        json.dumps(
            {
                "experiment_id": "EXP-012",
                "reproducibility_status": "INFERENCE_VERIFIED",
                "release_url": "https://github.com/test/repo/releases/tag/exp-012-repro-v1",
                "artifacts": [
                    {"kind": kind, "storage_uri": storage_uri} for kind in artifact_kinds
                ],
            }
        ),
        encoding="utf-8",
    )
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        """required_artifact_kinds:
  - checkpoint
  - oof_probability
  - test_probability
  - submission
  - resolved_config
  - release_bundle
accepted_kind_aliases: {}
legacy_exceptions: {}
""",
        encoding="utf-8",
    )
    return history_path, reproducibility_root, policy_path


def test_submission_storage_policy_accepts_published_bundle(tmp_path: Path) -> None:
    paths = _write_storage_policy_fixture(
        tmp_path,
        storage_uri="https://github.com/test/repo/releases/download/v1/bundle.tar.gz",
    )
    summary = validate_submission_storage_policy(*paths)
    assert summary["storage_verified"] == ["EXP-012"]


def test_submission_storage_policy_rejects_missing_storage_uri(tmp_path: Path) -> None:
    paths = _write_storage_policy_fixture(tmp_path, storage_uri=None)
    with pytest.raises(ValidationError, match="storage_uri"):
        validate_submission_storage_policy(*paths)


def test_history_accepts_issue_derived_id_and_numeric_branch(tmp_path: Path) -> None:
    history = tmp_path / "EXPERIMENT_HISTORY.md"
    history.write_text(
        """# 실험 기록

- 실제 실험 수: 1

| ID | 상태 | 담당자 | Issue | 모델 |
|---|---|---|---|---|
| EXP-012 | COMPLETED | tester | #12 | baseline |

### [EXP-012] baseline

- Issue/브랜치: #12 / 12
""",
        encoding="utf-8",
    )
    summary = validate_history(history)
    assert summary == {
        "declared": 1,
        "summary": 1,
        "details": 1,
        "issue_aligned": 1,
    }


def test_history_rejects_mismatched_issue_id(tmp_path: Path) -> None:
    history = tmp_path / "EXPERIMENT_HISTORY.md"
    history.write_text(
        """# 실험 기록

- 실제 실험 수: 1

| ID | 상태 | 담당자 | Issue | 모델 |
|---|---|---|---|---|
| EXP-012 | COMPLETED | tester | #13 | baseline |

### [EXP-012] baseline

- Issue/브랜치: #13 / issue-13-exp-baseline
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="Issue #12"):
        validate_history(history)
