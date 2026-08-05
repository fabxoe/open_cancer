from __future__ import annotations

import math

import pandas as pd
import pytest

from open_cancer.protein_deletion_semantics import (
    PROTEIN_DELETION_SEMANTICS_CONTRACT,
    ProteinDeletionSemanticFamily,
    audit_protein_deletion_semantics,
    parse_protein_deletion_token,
)


def test_contract_is_versioned_and_target_independent() -> None:
    assert PROTEIN_DELETION_SEMANTICS_CONTRACT["definition_version"] == "4.0.0"
    assert PROTEIN_DELETION_SEMANTICS_CONTRACT["raw_token_preserved"] is True
    assert PROTEIN_DELETION_SEMANTICS_CONTRACT["target_used"] is False


@pytest.mark.parametrize(
    ("token", "syntax", "kind", "length", "confidence"),
    [
        ("R649del", "residue_aware_single", "single_residue", 1, "exact"),
        ("249del", "position_only_single", "single_residue", 1, "partial"),
        ("G235_G238del", "residue_aware_range", "residue_range", 4, "exact"),
        ("134_135del", "position_only_range", "residue_range", 2, "partial"),
    ],
)
def test_observed_deletion_grammars(
    token: str, syntax: str, kind: str, length: int, confidence: str
) -> None:
    parsed = parse_protein_deletion_token(token)
    assert parsed.is_deletion
    assert parsed.source_syntax == syntax
    assert parsed.deletion_type == kind
    assert parsed.deleted_length == length
    assert parsed.parse_confidence == confidence
    assert parsed.position_eligible is True
    assert parsed.has_frameshift is False
    assert parsed.contains_stop is False
    assert parsed.three_prime_normalized == "unknown"


def test_equal_position_range_preserves_raw_but_normalizes_semantic_single() -> None:
    parsed = parse_protein_deletion_token("277_277del")
    assert parsed.raw_token == "277_277del"
    assert parsed.normalized_token == "277_277DEL"
    assert parsed.semantic_canonical_token == "277DEL"
    assert parsed.source_syntax == "equal_position_range"
    assert parsed.deletion_type == "single_residue"
    assert parsed.deleted_length == 1
    assert parsed.hgvs_conformant is False
    assert parsed.parse_status == "partial"


def test_reversed_range_is_unresolved_and_never_auto_swapped() -> None:
    parsed = parse_protein_deletion_token("E79_C76del")
    assert parsed.event_type == "deletion"
    assert parsed.parse_status == "unresolved"
    assert parsed.range_order_valid is False
    assert parsed.deleted_length is None
    assert parsed.start_position == 79
    assert parsed.end_position == 76
    assert parsed.semantic_canonical_token is None
    assert parsed.position_eligible is False


@pytest.mark.parametrize(
    "token",
    [
        "E1117delinsGGRRIIK",
        "H1176_W1177delinsQ",
        "SDEL133fs",
        "Y780*",
        "R45del6",
        "EX17del",
        "ΔF508",
    ],
)
def test_non_deletion_or_unsupported_grammar_is_not_consumed(token: str) -> None:
    parsed = parse_protein_deletion_token(token)
    assert parsed.is_deletion is False
    assert parsed.parse_status == "not_applicable"


@pytest.mark.parametrize(
    "token",
    ["R649del", "249del", "G235_G238del", "134_135del", "277_277del"],
)
def test_normalization_is_idempotent(token: str) -> None:
    first = parse_protein_deletion_token(token)
    second = parse_protein_deletion_token(first.normalized_token)
    assert second.normalized_token == first.normalized_token
    assert second.source_syntax == first.source_syntax
    assert second.deleted_length == first.deleted_length


def test_feature_adapter_preserves_length_and_unique_gene_semantics() -> None:
    frame = pd.DataFrame(
        {
            "G1": ["R10del G20_G22del", "WT"],
            "G2": ["249del E1117delinsG", "134_135del"],
        }
    )
    fitted = ProteinDeletionSemanticFamily(
        gene_columns=("G1", "G2"), include_gene_features=True
    ).fit(frame)
    matrix = fitted.transform(frame)
    names = fitted.descriptor.feature_names
    assert matrix[0, names.index("sample__deletion_token_count")] == 3
    assert matrix[0, names.index("sample__deletion_gene_count")] == 2
    assert matrix[0, names.index("sample__deleted_length_sum")] == 5
    assert matrix[0, names.index("G1__single_deletion_count")] == 1
    assert matrix[0, names.index("G1__range_deletion_count")] == 1
    assert matrix[0, names.index("G2__position_only_deletion_count")] == 1
    assert matrix[1, names.index("sample__range_deletion_gene_count")] == 1
    assert matrix[1, names.index("sample__deleted_length_log1p_sum")] == pytest.approx(
        math.log1p(2), rel=1e-6
    )


def test_compact_audit_separates_delins_and_frameshift_substring() -> None:
    frame = pd.DataFrame(
        {
            "G1": ["R1del E2delinsG", "SDEL133fs"],
            "G2": ["10_12del", "WT"],
        }
    )
    result = audit_protein_deletion_semantics(frame, ("G1", "G2"))
    assert result["deletion_occurrences"] == 2
    assert result["delins_routed_separately"] == 1
    assert result["frameshift_del_substring_routed_separately"] == 1
