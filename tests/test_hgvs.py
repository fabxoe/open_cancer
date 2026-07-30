from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from open_cancer.hgvs import normalize_protein_cell, normalize_protein_token, normalize_train


def test_normalize_supported_protein_substitutions() -> None:
    assert normalize_protein_token("S27N").value == "p.Ser27Asn"
    assert normalize_protein_token("R895R").value == "p.Arg895="
    assert normalize_protein_token("R1538*").value == "p.Arg1538Ter"


def test_normalize_multiple_variants_and_wt() -> None:
    assert normalize_protein_cell("F157L S1042F") == (
        "p.Phe157Leu p.Ser1042Phe",
        ["converted", "converted"],
    )
    assert normalize_protein_cell("WT") == ("WT", [])
    assert normalize_protein_cell("") == ("", [])


def test_normalize_single_residue_frameshift_to_predicted_short_form() -> None:
    result = normalize_protein_token("L1854fs")
    assert result.value == "p.(Leu1854fs)"
    assert result.status == "converted_short_frameshift"


def test_normalize_train_writes_copy_and_audit_report(tmp_path: Path) -> None:
    source = tmp_path / "train.csv"
    output = tmp_path / "processed.csv"
    report_path = tmp_path / "report.json"
    source.write_text(
        "ID,SUBCLASS,GENE1,GENE2\n"
        "TRAIN_1,A,S27N,WT\n"
        'TRAIN_2,B,"R895R L1854fs",R1538*\n',
        encoding="utf-8",
    )

    report = normalize_train(source, output, report_path)

    with output.open(encoding="utf-8", newline="") as file:
        rows = list(csv.reader(file))
    assert rows == [
        ["ID", "SUBCLASS", "GENE1", "GENE2"],
        ["TRAIN_1", "A", "p.Ser27Asn", "WT"],
        ["TRAIN_2", "B", "p.Arg895= p.(Leu1854fs)", "p.Arg1538Ter"],
    ]
    assert report["token_counts"] == {
        "converted": 3,
        "converted_short_frameshift": 1,
    }
    assert json.loads(report_path.read_text(encoding="utf-8"))["rows"] == 2


def test_refuse_to_overwrite_source(tmp_path: Path) -> None:
    source = tmp_path / "train.csv"
    source.write_text("ID,SUBCLASS,GENE\n", encoding="utf-8")

    with pytest.raises(ValueError, match="덮어쓸 수 없습니다"):
        normalize_train(source, source, tmp_path / "report.json")
