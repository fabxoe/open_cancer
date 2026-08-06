from __future__ import annotations

import pandas as pd

from open_cancer.patient_semantic_vector import (
    PatientSemanticVectorFamily,
    patient_semantic_feature_names,
)


def test_patient_vector_preserves_gene_event_and_amino_acid_change() -> None:
    genes = ("IDH1", "TP53")
    frame = pd.DataFrame(
        {
            "IDH1": ["R132H R132R", "WT"],
            "TP53": ["Y120*", "S261_P262insQE"],
        }
    )
    fitted = PatientSemanticVectorFamily(genes).fit(frame)
    matrix = fitted.transform(frame)
    names = fitted.descriptor.feature_names

    def value(row: int, name: str) -> float:
        return float(matrix[row, names.index(name)])

    assert value(0, "gene__IDH1__parser_v4_missense_token_count") == 1
    assert value(0, "gene__IDH1__parser_v4_no_change_token_count") == 1
    assert value(0, "gene__TP53__parser_v4_nonsense_token_count") == 1
    assert value(0, "sample__parser_v4_substitution_count__R_to_H") == 1
    assert value(0, "sample__parser_v4_substitution_count__R_to_R") == 1
    assert value(0, "sample__parser_v4_alternate_aa_count__STOP") == 1
    assert value(1, "gene__TP53__parser_v4_insertion_token_count") == 1
    assert value(1, "sample__parser_v4_inserted_or_new_aa_count__Q") == 1
    assert value(1, "sample__parser_v4_inserted_or_new_aa_count__E") == 1


def test_patient_vector_is_alias_invariant_for_stop_notation() -> None:
    genes = ("TP53",)
    frame = pd.DataFrame({"TP53": ["R582X", "R582Ter", "R582*"]})
    matrix = PatientSemanticVectorFamily(genes).fit(frame).transform(frame)
    assert (matrix[0] != matrix[1]).nnz == 0
    assert (matrix[1] != matrix[2]).nnz == 0


def test_patient_vector_schema_is_deterministic() -> None:
    names = patient_semantic_feature_names(("A", "B"))
    assert names == patient_semantic_feature_names(("A", "B"))
    assert len(names) == len(set(names))


def test_multiletter_frameshift_candidate_is_not_counted_as_confirmed_peptide() -> None:
    genes = ("ELF3",)
    frame = pd.DataFrame({"ELF3": ["SDEL133fs", "SQ133fs"]})
    fitted = PatientSemanticVectorFamily(genes).fit(frame)
    matrix = fitted.transform(frame)
    names = fitted.descriptor.feature_names
    for aa in ("D", "E", "L", "Q"):
        column = names.index(f"sample__parser_v4_inserted_or_new_aa_count__{aa}")
        assert float(matrix[0, column]) == 0.0
        assert float(matrix[1, column]) == (1.0 if aa == "Q" else 0.0)


def test_vectorized_scan_preserves_empty_and_mixed_case_wt_rows() -> None:
    genes = ("TP53", "IDH1")
    frame = pd.DataFrame(
        {"TP53": [" wt ", "R582X", None], "IDH1": ["", "WT", "R132H"]}
    )
    fitted = PatientSemanticVectorFamily(genes).fit(frame)
    matrix = fitted.transform(frame)
    assert matrix[0].nnz == 0
    assert matrix[1].nnz > 0
    assert matrix[2].nnz > 0
