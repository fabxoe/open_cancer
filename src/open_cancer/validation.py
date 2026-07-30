"""Validation functions shared by local scripts, tests, and CI."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
from jsonschema import Draft202012Validator, FormatChecker
from sklearn.model_selection import StratifiedKFold

from open_cancer.constants import (
    CLASS_LABELS,
    EXPECTED_GENE_COLUMNS,
    EXPECTED_TEST_ROWS,
    EXPECTED_TRAIN_ROWS,
)
from open_cancer.hashing import sha256_file, sha256_lines


class ValidationError(ValueError):
    """Raised when a project data or artifact contract is violated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate_competition_data(
    train_path: str | Path,
    test_path: str | Path,
    sample_submission_path: str | Path,
    *,
    strict_shape: bool = True,
    expected_classes: tuple[str, ...] = CLASS_LABELS,
) -> dict[str, Any]:
    """Validate the competition CSV contract and return a serializable summary."""
    train_path = Path(train_path)
    test_path = Path(test_path)
    sample_submission_path = Path(sample_submission_path)

    for path in (train_path, test_path, sample_submission_path):
        _require(path.is_file(), f"필수 파일이 없습니다: {path}")

    train = pd.read_csv(train_path, dtype=str, keep_default_na=False)
    test = pd.read_csv(test_path, dtype=str, keep_default_na=False)
    sample = pd.read_csv(sample_submission_path, dtype=str, keep_default_na=False)

    _require(list(train.columns[:2]) == ["ID", "SUBCLASS"], "train 앞 열은 ID,SUBCLASS여야 합니다.")
    _require(test.columns[0] == "ID", "test 첫 열은 ID여야 합니다.")
    _require(list(sample.columns) == ["ID", "SUBCLASS"], "sample 제출 열은 ID,SUBCLASS여야 합니다.")

    train_genes = list(train.columns[2:])
    test_genes = list(test.columns[1:])
    _require(train_genes == test_genes, "train/test 유전자 열 이름 또는 순서가 다릅니다.")
    _require(not train["ID"].duplicated().any(), "train ID가 중복됩니다.")
    _require(not test["ID"].duplicated().any(), "test ID가 중복됩니다.")
    _require(test["ID"].equals(sample["ID"]), "sample ID가 test와 값 또는 순서가 다릅니다.")
    _require(
        set(train["SUBCLASS"]) == set(expected_classes),
        "학습 클래스 집합이 고정 클래스와 다릅니다.",
    )

    if strict_shape:
        _require(len(train) == EXPECTED_TRAIN_ROWS, "train 행 수가 6,201이 아닙니다.")
        _require(len(test) == EXPECTED_TEST_ROWS, "test 행 수가 2,546이 아닙니다.")
        _require(len(train_genes) == EXPECTED_GENE_COLUMNS, "유전자 열 수가 4,384가 아닙니다.")

    return {
        "train_rows": len(train),
        "test_rows": len(test),
        "gene_columns": len(train_genes),
        "class_count": train["SUBCLASS"].nunique(),
        "classes": list(expected_classes),
        "feature_order_sha256": sha256_lines(train_genes),
        "files": {
            "train": {"path": str(train_path), "sha256": sha256_file(train_path)},
            "test": {"path": str(test_path), "sha256": sha256_file(test_path)},
            "sample_submission": {
                "path": str(sample_submission_path),
                "sha256": sha256_file(sample_submission_path),
            },
        },
    }


def validate_submission(
    submission_path: str | Path,
    test_path: str | Path,
    *,
    expected_classes: tuple[str, ...] = CLASS_LABELS,
) -> dict[str, Any]:
    """Validate a leaderboard submission against test IDs and allowed labels."""
    submission_path = Path(submission_path)
    test_path = Path(test_path)
    _require(submission_path.is_file(), f"제출 파일이 없습니다: {submission_path}")
    _require(test_path.is_file(), f"test 파일이 없습니다: {test_path}")

    submission = pd.read_csv(submission_path, dtype=str, keep_default_na=False)
    test_ids = pd.read_csv(test_path, usecols=["ID"], dtype=str, keep_default_na=False)["ID"]

    _require(list(submission.columns) == ["ID", "SUBCLASS"], "제출 열은 ID,SUBCLASS여야 합니다.")
    _require(len(submission) == len(test_ids), "제출 행 수가 test와 다릅니다.")
    _require(submission["ID"].equals(test_ids), "제출 ID가 test와 값 또는 순서가 다릅니다.")
    _require(not submission["ID"].duplicated().any(), "제출 ID가 중복됩니다.")
    _require(not (submission["SUBCLASS"] == "").any(), "제출 SUBCLASS에 빈 값이 있습니다.")
    invalid = sorted(set(submission["SUBCLASS"]) - set(expected_classes))
    _require(not invalid, f"허용되지 않은 SUBCLASS가 있습니다: {invalid}")

    return {
        "rows": len(submission),
        "columns": list(submission.columns),
        "label_counts": submission["SUBCLASS"].value_counts().sort_index().to_dict(),
        "sha256": sha256_file(submission_path),
    }


def create_stratified_folds(
    train_path: str | Path,
    output_path: str | Path,
    *,
    n_splits: int = 5,
    seed: int = 42,
) -> dict[str, Any]:
    """Create the canonical ID/fold map in original train row order."""
    train_path = Path(train_path)
    output_path = Path(output_path)
    train = pd.read_csv(train_path, usecols=["ID", "SUBCLASS"], dtype=str)
    _require(not train["ID"].duplicated().any(), "train ID가 중복됩니다.")

    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    folds = pd.Series(index=train.index, dtype="int64")
    for fold, (_, valid_idx) in enumerate(splitter.split(train["ID"], train["SUBCLASS"])):
        folds.iloc[valid_idx] = fold

    result = pd.DataFrame({"ID": train["ID"], "fold": folds.astype(int)})
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False, lineterminator="\n")
    return {
        "path": str(output_path),
        "sha256": sha256_file(output_path),
        "rows": len(result),
        "n_splits": n_splits,
        "seed": seed,
        "fold_counts": result["fold"].value_counts().sort_index().to_dict(),
        "train_sha256": sha256_file(train_path),
    }


def validate_json_document(document_path: Path, schema_path: Path) -> None:
    """Validate one JSON document and include every schema error in the exception."""
    document = json.loads(document_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    if errors:
        details = "; ".join(
            f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}" for error in errors
        )
        raise ValidationError(f"{document_path}: {details}")


def validate_history(history_path: str | Path) -> dict[str, int]:
    """Check experiment counts, IDs, and next-ID bookkeeping in History."""
    history_path = Path(history_path)
    text = history_path.read_text(encoding="utf-8")

    declared_match = re.search(r"^- 실제 실험 수: (\d+)$", text, flags=re.MULTILINE)
    next_match = re.search(r"^- 다음 실험 ID: EXP-(\d+)$", text, flags=re.MULTILINE)
    _require(declared_match is not None, "History의 실제 실험 수를 찾을 수 없습니다.")
    _require(next_match is not None, "History의 다음 실험 ID를 찾을 수 없습니다.")

    summary_ids = re.findall(r"^\| (EXP-\d+) \|", text, flags=re.MULTILINE)
    detail_ids = re.findall(r"^### \[(EXP-\d+)\]", text, flags=re.MULTILINE)
    _require(len(summary_ids) == len(set(summary_ids)), "실험 요약 ID가 중복됩니다.")
    _require(len(detail_ids) == len(set(detail_ids)), "상세 로그 ID가 중복됩니다.")
    _require(set(summary_ids) == set(detail_ids), "요약표와 상세 로그의 EXP-ID가 다릅니다.")

    declared_count = int(declared_match.group(1))
    _require(declared_count == len(summary_ids), "실제 실험 수와 요약표 행 수가 다릅니다.")
    expected_next = max((int(item.split("-")[1]) for item in summary_ids), default=0) + 1
    _require(int(next_match.group(1)) == expected_next, "다음 실험 ID가 실제 최대 ID+1이 아닙니다.")
    return {"declared": declared_count, "summary": len(summary_ids), "details": len(detail_ids)}
