from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_cancer.validation import (
    ValidationError,
    validate_experiment_source_identity,
    validate_repository_contract,
)


def write_history(path: Path, report_path: str = "reports/exp012_model/README.md") -> None:
    path.write_text(
        "# 기록\n\n"
        "| ID | 상태 | 실행자 | Issue | 모델 | OOF | LB | 재현 | 판단 | 상세 기록 |\n"
        "|---|---|---|---|---|---:|---:|---|---|---|\n"
        f"| EXP-012 | COMPLETED | user | #12 | model | 0.1 | 미제출 | "
        f"NOT_STARTED | 채택 | [보고서]({report_path}) |\n",
        encoding="utf-8",
    )


def write_minimum_repository(root: Path) -> Path:
    history = root / "EXPERIMENT_HISTORY.md"
    write_history(history)
    (root / "configs").mkdir()
    (root / "configs" / "exp012_model.yaml").write_text(
        "run_mode: experiment\nrecord_role: official\n",
        encoding="utf-8",
    )
    report_dir = root / "reports" / "exp012_model"
    report_dir.mkdir(parents=True)
    (report_dir / "README.md").write_text("# report\n", encoding="utf-8")
    (report_dir / "metrics.json").write_text(
        json.dumps({"record_role": "official"}),
        encoding="utf-8",
    )
    return history


def test_repository_contract_accepts_one_official_config(tmp_path: Path) -> None:
    history = write_minimum_repository(tmp_path)
    summary = validate_repository_contract(tmp_path, history)
    assert summary["report_links"] == 1
    assert summary["experiment_config_groups"] == 1
    assert summary["role_checked_metrics"] == 1


def test_repository_contract_rejects_missing_report(tmp_path: Path) -> None:
    history = write_minimum_repository(tmp_path)
    (tmp_path / "reports" / "exp012_model" / "README.md").unlink()
    with pytest.raises(ValidationError, match="보고서가 없습니다"):
        validate_repository_contract(tmp_path, history)


def test_repository_contract_rejects_multiple_official_configs(tmp_path: Path) -> None:
    history = write_minimum_repository(tmp_path)
    (tmp_path / "configs" / "exp012_second.yaml").write_text(
        "run_mode: experiment\nrecord_role: official\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="official config가 정확히 하나"):
        validate_repository_contract(tmp_path, history)


def test_dirty_official_record_requires_failed_manifest(tmp_path: Path) -> None:
    history = write_minimum_repository(tmp_path)
    reproduction = tmp_path / "reproducibility" / "exp012_model"
    reproduction.mkdir(parents=True)
    (reproduction / "config.resolved.yaml").write_text(
        "experiment:\n"
        "  record_role: official\n"
        "  dirty_worktree: true\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="FAILED manifest"):
        validate_repository_contract(tmp_path, history)

    (reproduction / "artifact_manifest.json").write_text(
        json.dumps({"reproducibility_status": "FAILED"}),
        encoding="utf-8",
    )
    summary = validate_repository_contract(tmp_path, history)
    assert summary["dirty_failed_records"] == 1


def write_source_identity_repository(tmp_path: Path, runner_source: str) -> Path:
    history = tmp_path / "EXPERIMENT_HISTORY.md"
    write_history(history, "reports/exp158_model/README.md")
    history.write_text(
        history.read_text(encoding="utf-8").replace("EXP-012", "EXP-158").replace("#12", "#158"),
        encoding="utf-8",
    )
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "exp158_model.yaml").write_text(
        "run_mode: experiment\nrecord_role: official\n"
        "experiment_id: EXP-158\nissue_number: 158\n",
        encoding="utf-8",
    )
    (tmp_path / "configs" / "experiment_source_legacy.yaml").write_text(
        "config_without_experiment_id:\n  config_stems: []\n"
        "missing_history_config: []\nmissing_runner: []\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "run_exp158_model.py").write_text(
        runner_source,
        encoding="utf-8",
    )
    report_dir = tmp_path / "reports" / "exp158_model"
    report_dir.mkdir(parents=True)
    (report_dir / "README.md").write_text("# report\n", encoding="utf-8")
    (report_dir / "metrics.json").write_text(
        json.dumps({"experiment_id": "EXP-158", "record_role": "official"}),
        encoding="utf-8",
    )
    return history


def test_source_identity_accepts_matching_runner(tmp_path: Path) -> None:
    history = write_source_identity_repository(
        tmp_path,
        '"""Run EXP-158."""\nfrom open_cancer.experiment import resolve_experiment_context\n',
    )
    summary = validate_experiment_source_identity(tmp_path, history)
    assert summary["source_identity_checked"] == 1


def test_source_identity_rejects_wrong_runner_id(tmp_path: Path) -> None:
    history = write_source_identity_repository(tmp_path, '"""Run EXP-151."""\n')
    with pytest.raises(ValidationError, match="내부 EXP-ID"):
        validate_experiment_source_identity(tmp_path, history)
