from __future__ import annotations

import pandas as pd
import pytest

from open_cancer.protein_delins_semantics import (
    PROTEIN_DELINS_SEMANTICS_CONTRACT,
    ProteinDelinsSemanticFamily,
    audit_protein_delins_semantics,
    parse_protein_delins_token,
)


def test_contract_is_versioned_and_target_independent() -> None:
    assert PROTEIN_DELINS_SEMANTICS_CONTRACT["definition_version"] == "4.0.0"
    assert PROTEIN_DELINS_SEMANTICS_CONTRACT["target_used"] is False


@pytest.mark.parametrize(
    ("token", "kind", "span", "alternate", "net"),
    [
        ("E1117delinsGGRRIIK", "single_position", 1, "GGRRIIK", 6),
        ("H1176_W1177delinsQ", "residue_range", 2, "Q", -1),
        ("E378_V380delinsD", "residue_range", 3, "D", -2),
    ],
)
def test_exact_delins(token: str, kind: str, span: int, alternate: str, net: int) -> None:
    parsed = parse_protein_delins_token(token)
    assert parsed.parse_status == "complete"
    assert parsed.primary_event == "delins"
    assert parsed.delins_type == kind
    assert parsed.reference_span_length == span
    assert parsed.translated_alternate_sequence == alternate
    assert parsed.net_length_change == net


def test_long_alternate_is_lossless() -> None:
    alternate = "NEGNNHWPRVEMPTGWLLVGYNTRNTAQNPRLQQHLKHWQQCTRARW"
    token = f"K176delins{alternate}"
    parsed = parse_protein_delins_token(token)
    assert parsed.raw_token == token
    assert parsed.alternate_sequence_raw == alternate
    assert parsed.translated_alternate_sequence == alternate


def test_immediate_and_later_stop_are_separate() -> None:
    immediate = parse_protein_delins_token("X541delinsX")
    assert immediate.unknown_reference_residue is True
    assert immediate.primary_event == "nonsense"
    assert immediate.translated_alternate_sequence == ""
    assert immediate.first_stop_offset == 0

    later = parse_protein_delins_token("K629delinsKX")
    assert later.primary_event == "delins"
    assert later.translated_alternate_sequence == "K"
    assert later.first_stop_offset == 1
    assert later.protein_truncating is True


def test_stop_notation_is_canonical_and_idempotent() -> None:
    values = [parse_protein_delins_token(x) for x in ("K629delinsK*", "K629delinsKX", "K629delinsKTer")]
    assert {x.normalized_token for x in values} == {"K629DELINSK*"}
    second = parse_protein_delins_token(values[0].normalized_token)
    assert second.normalized_token == values[0].normalized_token


def test_uppercase_ter_inside_one_letter_peptide_is_not_a_stop() -> None:
    parsed = parse_protein_delins_token("E10delinsATERG")
    assert parsed.alternate_sequence_canonical == "ATERG"
    assert parsed.contains_stop is False


def test_unknown_range_endpoint_is_unresolved_but_structured() -> None:
    parsed = parse_protein_delins_token("L400_X401delinsLX")
    assert parsed.source_structure == "delins"
    assert parsed.parse_status == "unresolved"
    assert parsed.unknown_reference_residue is True
    assert parsed.reference_span_length == 2
    assert parsed.translated_alternate_sequence == "L"


@pytest.mark.parametrize("token", ["SDEL133fs", "G235_G238del", "K745_E746insIPVAIK", "300_301LE>F*"])
def test_other_event_grammars_are_not_consumed(token: str) -> None:
    assert parse_protein_delins_token(token).is_delins_syntax is False


def test_reversed_range_is_not_swapped() -> None:
    parsed = parse_protein_delins_token("W1177_H1176delinsQ")
    assert parsed.parse_status == "unresolved"
    assert parsed.range_order_valid is False
    assert parsed.reference_span_length is None
    assert parsed.start_position == 1177


def test_feature_adapter_counts_delins_once() -> None:
    frame = pd.DataFrame({"G1": ["E1delinsGG E2del"], "G2": ["H3_W4delinsQ"]})
    fitted = ProteinDelinsSemanticFamily(("G1", "G2"), include_gene_features=True).fit(frame)
    matrix = fitted.transform(frame); names = fitted.descriptor.feature_names
    assert matrix[0, names.index("sample__delins_token_count")] == 2
    assert matrix[0, names.index("sample__delins_gene_count")] == 2
    assert matrix[0, names.index("G1__delins_count")] == 1


def test_audit_is_compact() -> None:
    frame = pd.DataFrame({"G1": ["E1delinsGG"], "G2": ["X2delinsX"]})
    result = audit_protein_delins_semantics(frame, ("G1", "G2"))
    assert result["occurrences"] == 2
    assert result["stop_counts"]["immediate_stop"] == 1
