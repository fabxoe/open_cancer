from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

from open_cancer.isoform_semantics import TranscriptAnnotation


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "audit_isoform_stop_normalization_impact.py"
)
SPEC = importlib.util.spec_from_file_location("isoform_stop_audit", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
audit_token_table = MODULE.audit_token_table


def _annotation() -> TranscriptAnnotation:
    return TranscriptAnnotation(
        gene_id="ENSG1",
        gene_symbol="GENE1",
        gene_biotype="protein_coding",
        transcript_id="ENST1",
        transcript_biotype="protein_coding",
        protein_id="ENSP1",
        is_mane_select=True,
        is_canonical=True,
        sequence="MAAA",
    )


def test_x_stop_moves_from_unmappable_to_mane(tmp_path: Path) -> None:
    path = tmp_path / "tokens.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("dataset", "ID", "gene", "token", "category"),
        )
        writer.writeheader()
        writer.writerow(
            {
                "dataset": "test",
                "ID": "S1",
                "gene": "GENE1",
                "token": "A2X",
                "category": "COMPLEX_OR_UNMAPPABLE",
            }
        )

    result = audit_token_table(path, {"GENE1": (_annotation(),)})
    assert result["normalized_token_count"] == 1
    assert result["before"]["MANE_MATCH"]["count"] == 0
    assert result["after"]["MANE_MATCH"]["count"] == 1
    assert result["changed_transitions"] == [
        {"from": "COMPLEX_OR_UNMAPPABLE", "to": "MANE_MATCH", "count": 1}
    ]
