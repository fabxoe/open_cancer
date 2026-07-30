from __future__ import annotations

import pytest

from open_cancer.experiment import (
    experiment_id_from_issue,
    extract_issue_number,
    issue_number_from_experiment_id,
    resolve_experiment_context,
    validate_experiment_issue_pair,
)


@pytest.mark.parametrize(
    ("branch", "expected"),
    [
        ("12", 12),
        ("12-xgb-baseline", 12),
        ("issue-12", 12),
        ("issue-12-xgb-baseline", 12),
        ("issue-12-exp-xgb-baseline", 12),
        ("main", None),
        ("feature/xgb", None),
        ("issue-no-number", None),
        ("0", None),
    ],
)
def test_extract_issue_number(branch: str, expected: int | None) -> None:
    assert extract_issue_number(branch) == expected


def test_issue_number_derives_experiment_identity() -> None:
    context = resolve_experiment_context("experiment", branch="12")
    assert context.issue_number == 12
    assert context.experiment_id == "EXP-012"
    assert context.artifact_prefix == "exp012"
    assert experiment_id_from_issue(1234) == "EXP-1234"
    assert issue_number_from_experiment_id("EXP-012") == 12


def test_explore_mode_does_not_create_experiment() -> None:
    context = resolve_experiment_context("explore", branch="issue-10-notebook")
    assert context.issue_number == 10
    assert context.experiment_id is None
    assert context.artifact_prefix is None


def test_experiment_mode_requires_issue_branch() -> None:
    with pytest.raises(ValueError, match="Issue 번호"):
        resolve_experiment_context("experiment", branch="main")


def test_experiment_and_issue_must_match() -> None:
    validate_experiment_issue_pair("EXP-012", 12)
    with pytest.raises(ValueError, match="Issue #12"):
        validate_experiment_issue_pair("EXP-012", 13)
