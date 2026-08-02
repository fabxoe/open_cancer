from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.model_artifacts import (
    ModelArtifactError,
    build_oof_probability_frame,
    build_test_probability_frame,
    validate_oof_probability_frame,
    write_model_run_records,
)
from open_cancer.validation import validate_json_document


def probabilities(rows: int) -> np.ndarray:
    values = np.full((rows, len(CLASS_LABELS)), 0.1 / (len(CLASS_LABELS) - 1))
    for row in range(rows):
        values[row, row % len(CLASS_LABELS)] = 0.9
    return values


def test_probability_builders_enforce_canonical_columns() -> None:
    oof = build_oof_probability_frame(
        ids=["A", "B"],
        true_labels=[CLASS_LABELS[0], CLASS_LABELS[1]],
        folds=[0, 1],
        probabilities=probabilities(2),
    )
    test = build_test_probability_frame(ids=["T1", "T2"], probabilities=probabilities(2))

    assert list(oof.columns) == [
        "ID",
        "SUBCLASS_TRUE",
        "SUBCLASS_PRED",
        "FOLD",
        *PROBABILITY_COLUMNS,
    ]
    assert list(test.columns) == ["ID", *PROBABILITY_COLUMNS]


def test_oof_validation_rejects_probability_column_reordering() -> None:
    frame = build_oof_probability_frame(
        ids=["A"],
        true_labels=[CLASS_LABELS[0]],
        folds=[0],
        probabilities=probabilities(1),
    )
    columns = list(frame.columns)
    columns[-1], columns[-2] = columns[-2], columns[-1]
    with pytest.raises(ModelArtifactError, match="열 또는 열 순서"):
        validate_oof_probability_frame(
            frame.loc[:, columns],
            expected_ids=["A"],
            expected_true_labels=[CLASS_LABELS[0]],
        )


def test_write_model_run_records_creates_schema_valid_manifest(tmp_path) -> None:
    root = tmp_path
    data_path = root / "data" / "fixture.csv"
    artifact_path = root / "oof" / "exp100_oof.csv"
    data_path.parent.mkdir(parents=True)
    artifact_path.parent.mkdir(parents=True)
    data_path.write_text("ID\nA\n", encoding="utf-8")
    artifact_path.write_text("ID\nA\n", encoding="utf-8")

    paths = write_model_run_records(
        root=root,
        output_dir=root / "reproducibility" / "exp100_contract",
        experiment_id="EXP-100",
        issue_number=100,
        source_commit="a" * 40,
        resolved_config={"experiment": {"id": "EXP-100"}},
        metrics={"experiment_id": "EXP-100", "macro_f1": 0.1},
        data_files={"fixture": data_path},
        artifacts={"oof_probability": artifact_path},
    )

    manifest = json.loads(paths["artifact_manifest"].read_text(encoding="utf-8"))
    assert manifest["reproducibility_status"] == "MANIFEST_COMPLETE"
    assert {item["kind"] for item in manifest["artifacts"]} == {
        "oof_probability",
        "resolved_config",
        "metrics",
    }
    validate_json_document(
        paths["artifact_manifest"],
        Path(__file__).resolve().parents[1] / "schemas" / "reproducibility_manifest.schema.json",
    )


def test_write_model_run_records_normalizes_fold_artifact_kinds(tmp_path) -> None:
    root = tmp_path
    data_path = root / "data.csv"
    checkpoint_path = root / "fold_00.json"
    oof_path = root / "oof.csv"
    test_path = root / "test.csv"
    for path in (data_path, checkpoint_path, oof_path, test_path):
        path.write_text("fixture\n", encoding="utf-8")

    paths = write_model_run_records(
        root=root,
        output_dir=root / "reproducibility" / "exp101_contract",
        experiment_id="EXP-101",
        issue_number=101,
        source_commit="b" * 40,
        resolved_config={"experiment": {"id": "EXP-101"}},
        metrics={"experiment_id": "EXP-101"},
        data_files={"fixture": data_path},
        artifacts={
            "checkpoint_fold_0": checkpoint_path,
            "oof_probabilities": oof_path,
            "test_probabilities": test_path,
        },
    )

    manifest = json.loads(paths["artifact_manifest"].read_text(encoding="utf-8"))
    kinds = [item["kind"] for item in manifest["artifacts"]]
    assert "checkpoint" in kinds
    assert "oof_probability" in kinds
    assert "test_probability" in kinds
