from __future__ import annotations

from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
    parse_stop_notation_invariant_token,
)


def test_exp370_stop_alternates_are_semantically_equivalent() -> None:
    parsed = [
        parse_stop_notation_invariant_token(token)
        for token in ("R213*", "R213X", "R213Ter")
    ]

    assert {token.mutation_type for token in parsed} == {"nonsense"}
    assert {token.raw for token in parsed} == {"R213*"}
    assert {token.residue_positions for token in parsed} == {(213,)}


def test_exp370_cell_preserves_multiplicity_and_other_v1_semantics() -> None:
    cell = parse_stop_notation_invariant_cell(
        "R213X R213Ter A10V K16fs"
    )

    assert cell.token_count == 4
    assert cell.mutation_types == {
        "nonsense",
        "missense",
        "frameshift",
    }
    assert normalize_stop_notation_token("A10V") == "A10V"
    assert normalize_stop_notation_token("K16fs") == "K16fs"


def test_exp370_parser_contract_is_target_and_test_distribution_independent() -> None:
    assert STOP_NOTATION_PARSER_CONTRACT["definition_version"] == "2.1.0"
    assert STOP_NOTATION_PARSER_CONTRACT["equivalent_stop_alternates"] == [
        "*",
        "X",
        "Ter",
    ]
    assert STOP_NOTATION_PARSER_CONTRACT["deduplicate_tokens"] is False
    assert STOP_NOTATION_PARSER_CONTRACT["target_used"] is False
    assert (
        STOP_NOTATION_PARSER_CONTRACT["test_distribution_used_for_rule"]
        is False
    )
