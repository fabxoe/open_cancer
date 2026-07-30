"""Issue-derived experiment identity shared by notebooks, scripts, and CI."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

RunMode = Literal["explore", "experiment"]

_BRANCH_PATTERNS = (
    re.compile(r"^(?P<issue>[1-9][0-9]*)$"),
    re.compile(r"^(?P<issue>[1-9][0-9]*)-.+$"),
    re.compile(r"^issue-(?P<issue>[1-9][0-9]*)$"),
    re.compile(r"^issue-(?P<issue>[1-9][0-9]*)-.+$"),
)
_EXPERIMENT_ID_PATTERN = re.compile(r"^EXP-(?P<issue>[0-9]{3,})$")


@dataclass(frozen=True)
class ExperimentContext:
    """Resolved branch, Issue, and optional official experiment identity."""

    run_mode: RunMode
    branch: str
    issue_number: int | None
    experiment_id: str | None

    @property
    def is_experiment(self) -> bool:
        return self.run_mode == "experiment"

    @property
    def artifact_prefix(self) -> str | None:
        if self.issue_number is None or not self.is_experiment:
            return None
        return f"exp{self.issue_number:03d}"


def extract_issue_number(branch: str) -> int | None:
    """Extract an Issue number from supported local and team branch names."""
    normalized = branch.strip()
    for pattern in _BRANCH_PATTERNS:
        match = pattern.fullmatch(normalized)
        if match:
            return int(match.group("issue"))
    return None


def experiment_id_from_issue(issue_number: int) -> str:
    """Convert GitHub Issue #N to the canonical EXP-NNN identifier."""
    if issue_number < 1:
        raise ValueError("Issue 번호는 1 이상이어야 합니다.")
    return f"EXP-{issue_number:03d}"


def issue_number_from_experiment_id(experiment_id: str) -> int:
    """Return the Issue number encoded in a canonical experiment ID."""
    match = _EXPERIMENT_ID_PATTERN.fullmatch(experiment_id)
    if not match:
        raise ValueError(f"올바르지 않은 실험 ID입니다: {experiment_id}")
    return int(match.group("issue"))


def current_git_branch(cwd: str | Path | None = None) -> str:
    """Resolve the PR head branch in CI or the current local Git branch."""
    for variable in ("GITHUB_HEAD_REF", "GITHUB_REF_NAME"):
        value = os.environ.get(variable, "").strip()
        if value:
            return value

    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    branch = result.stdout.strip()
    if not branch:
        raise ValueError("현재 Git 브랜치를 확인할 수 없습니다.")
    return branch


def resolve_experiment_context(
    run_mode: RunMode,
    *,
    branch: str | None = None,
    cwd: str | Path | None = None,
) -> ExperimentContext:
    """Resolve an Issue and create EXP-NNN only for an official experiment."""
    if run_mode not in {"explore", "experiment"}:
        raise ValueError("RUN_MODE는 explore 또는 experiment여야 합니다.")

    resolved_branch = branch or current_git_branch(cwd)
    issue_number = extract_issue_number(resolved_branch)
    if run_mode == "experiment" and issue_number is None:
        raise ValueError(
            "공식 실험은 Issue 번호가 있는 브랜치에서 실행해야 합니다. "
            "허용 예: 12, 12-xgb, issue-12, issue-12-exp-xgb"
        )

    experiment_id = (
        experiment_id_from_issue(issue_number)
        if run_mode == "experiment" and issue_number is not None
        else None
    )
    return ExperimentContext(
        run_mode=run_mode,
        branch=resolved_branch,
        issue_number=issue_number,
        experiment_id=experiment_id,
    )


def validate_experiment_issue_pair(experiment_id: str, issue_number: int) -> None:
    """Reject records whose EXP-NNN and GitHub Issue #N do not match."""
    encoded_issue = issue_number_from_experiment_id(experiment_id)
    if encoded_issue != issue_number:
        raise ValueError(
            f"{experiment_id}는 Issue #{encoded_issue}를 뜻하지만 "
            f"기록에는 Issue #{issue_number}가 지정되었습니다."
        )
