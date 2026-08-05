from __future__ import annotations

import numpy as np

from open_cancer.canonical_event_tokenizer import tokenize_patient_event_row
from open_cancer.hierarchical_event_adapter import (
    fit_hierarchical_event_adapter,
    global_token_projections,
)


GENES = ("TP53", "IDH1", "MADCAM1")


def _patient(tp53="WT", idh1="WT", madcam1="WT"):
    return tokenize_patient_event_row(
        {"TP53": tp53, "IDH1": idh1, "MADCAM1": madcam1}, GENES
    )


def test_global_projection_removes_gene_and_adds_route_group() -> None:
    assert global_token_projections(
        "gene=TP53|family=substitution:missense"
    ) == (
        "global|family=substitution:missense",
        "global|route_group=substitution",
    )
    assert global_token_projections("gene=TP53|aa_transition=R>H") == (
        "global|aa_transition=R>H",
    )


def test_unseen_gene_detail_is_recovered_by_known_global_meaning() -> None:
    train = (_patient(tp53="R132H"),)
    validation = (_patient(idh1="R132H"),)
    fitted = fit_hierarchical_event_adapter(
        train, detail_minimum_support=1, global_minimum_support=1
    )
    audit = fitted.audit(validation)
    assert audit.detail_oov_occurrences > 0
    assert audit.detail_oov_recovery_rate == 1.0
    assert audit.unrecovered_detail_occurrences == 0
    matrix = fitted.transform(validation)
    assert matrix.nnz > 0


def test_fully_unseen_semantics_remain_explicit_oov() -> None:
    train = (_patient(tp53="R132H"),)
    validation = (_patient(madcam1="S261_P262insQEPPDTTS"),)
    fitted = fit_hierarchical_event_adapter(
        train, detail_minimum_support=1, global_minimum_support=1
    )
    audit = fitted.audit(validation)
    assert audit.detail_oov_occurrences > 0
    assert audit.unrecovered_detail_occurrences > 0
    assert audit.global_oov_occurrences > 0
    assert audit.patients_with_unrecovered_detail == 1


def test_fit_is_deterministic_and_transform_does_not_change_vocabulary() -> None:
    patients = (_patient(tp53="R132H"), _patient(idh1="R132R"))
    forward = fit_hierarchical_event_adapter(patients)
    reverse = fit_hierarchical_event_adapter(tuple(reversed(patients)))
    assert forward == reverse
    assert forward.feature_sha256 == reverse.feature_sha256
    before = forward.feature_sha256
    forward.transform((_patient(madcam1="S261_P262insQEPPDTTS"),))
    assert forward.feature_sha256 == before


def test_row_l2_normalizes_nonzero_rows_and_preserves_zero_rows() -> None:
    train = (_patient(tp53="R132H"), _patient())
    raw = fit_hierarchical_event_adapter(
        train, detail_minimum_support=1, normalization="raw"
    )
    normalized = fit_hierarchical_event_adapter(
        train, detail_minimum_support=1, normalization="row_l2"
    )
    assert raw.feature_sha256 == normalized.feature_sha256
    assert raw.adapter_sha256 != normalized.adapter_sha256
    raw_matrix = raw.transform(train)
    normalized_matrix = normalized.transform(train)
    assert raw_matrix.shape == normalized_matrix.shape
    assert np.sqrt(raw_matrix[0].multiply(raw_matrix[0]).sum()) > 1.0
    assert np.isclose(
        np.sqrt(normalized_matrix[0].multiply(normalized_matrix[0]).sum()), 1.0
    )
    assert normalized_matrix[1].nnz == 0


def test_support_threshold_is_based_on_patient_document_frequency() -> None:
    train = (
        _patient(tp53="R132H R132H"),
        _patient(idh1="R132R"),
    )
    fitted = fit_hierarchical_event_adapter(train, detail_minimum_support=2)
    assert "gene=TP53|aa_transition=R>H" not in fitted.detail_tokens
    assert "global|aa_transition=R>H" in fitted.global_tokens
