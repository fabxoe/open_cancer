from __future__ import annotations

from open_cancer.exact_duplicate_mutation_parser import (
    EXACT_DUPLICATE_PARSER_CONTRACT,
    audit_exact_duplicate_cell,
    parse_exact_duplicate_invariant_cell,
)


def _semantics(cell: str) -> tuple[tuple[object, ...], ...]:
    parsed = parse_exact_duplicate_invariant_cell(cell)
    return tuple(
        (
            token.raw,
            token.mutation_type,
            token.residue_positions,
            token.reference_amino_acid,
            token.alternate_amino_acid,
            token.is_complex,
        )
        for token in parsed.tokens
    )


def test_stop_alternates_collapse_to_one_exact_normalized_token() -> None:
    parsed = parse_exact_duplicate_invariant_cell(
        "R213X R213* R213Ter"
    )

    assert parsed.token_count == 1
    assert parsed.tokens[0].raw == "R213*"
    assert parsed.tokens[0].mutation_type == "nonsense"
    assert parsed.residue_positions == (213,)


def test_only_exact_duplicates_are_removed() -> None:
    parsed = parse_exact_duplicate_invariant_cell(
        "A10V A10V A11V K16fs K17fs"
    )

    assert parsed.token_count == 4
    assert {token.raw for token in parsed.tokens} == {
        "A10V",
        "A11V",
        "K16fs",
        "K17fs",
    }


def test_cell_semantics_are_order_invariant() -> None:
    assert _semantics("A10V R213X K16fs") == _semantics(
        "K16fs R213* A10V"
    )


def test_audit_separates_raw_and_stop_induced_duplicates() -> None:
    result = audit_exact_duplicate_cell(
        "A10V A10V R213X R213* R213Ter A11V"
    )

    assert result == {
        "source_tokens": 6,
        "raw_exact_duplicates": 1,
        "normalized_exact_duplicates": 3,
        "duplicates_introduced_by_normalization": 2,
    }


def test_contract_forbids_target_and_test_distribution_selection() -> None:
    assert EXACT_DUPLICATE_PARSER_CONTRACT[
        "deduplicate_exact_normalized_tokens"
    ] is True
    assert EXACT_DUPLICATE_PARSER_CONTRACT["token_order_invariant"] is True
    assert EXACT_DUPLICATE_PARSER_CONTRACT["distinct_tokens_preserved"] is True
    assert EXACT_DUPLICATE_PARSER_CONTRACT["target_used"] is False
    assert EXACT_DUPLICATE_PARSER_CONTRACT[
        "test_distribution_used_for_rule"
    ] is False
