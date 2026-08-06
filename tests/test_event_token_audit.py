from __future__ import annotations

from open_cancer.canonical_event_tokenizer import tokenize_patient_event_row
from open_cancer.event_token_audit import (
    integer_quantiles,
    summarize_oov,
    token_document_frequency,
    token_key,
    vocabulary_at_support,
)


def _patients():
    genes = ("A", "B")
    return (
        tokenize_patient_event_row({"A": "R1H", "B": "WT"}, genes),
        tokenize_patient_event_row({"A": "R1H", "B": "G2D"}, genes),
    )


def test_document_frequency_and_support_are_patient_based() -> None:
    patients = _patients()
    frequencies = token_document_frequency(patients)
    assert frequencies["gene=A|aa_transition=R>H"] == 2
    assert frequencies["gene=B|aa_transition=G>D"] == 1
    vocabulary = vocabulary_at_support(frequencies, 2)
    assert "gene=A|aa_transition=R>H" in vocabulary
    assert "gene=B|aa_transition=G>D" not in vocabulary


def test_oov_counts_occurrences_and_affected_patients() -> None:
    patients = _patients()
    vocabulary = frozenset(
        token for token, _ in patients[0].token_counts
    )
    summary = summarize_oov(patients, vocabulary)
    assert summary.patient_count == 2
    assert summary.patients_with_oov == 1
    assert summary.unique_oov_tokens > 0
    assert 0 < summary.oov_occurrence_rate < 1


def test_quantiles_and_token_key() -> None:
    assert integer_quantiles([1, 2, 3])["max"] == 3
    assert integer_quantiles([])["p50"] is None
    assert token_key("gene=TP53|family=substitution:missense") == "family"
