from open_cancer.protein_partial_terminal_semantics import (
    parse_partial_terminal_token,
)


def test_signed_frameshift_preserves_sign_but_blocks_protein_position() -> None:
    result = parse_partial_terminal_token("-762fs")
    assert result.semantic_kind == "signed_nonstandard_frameshift"
    assert result.source_position == -762
    assert result.source_position_text == "-762"
    assert result.frameshift_marker_present is True
    assert result.position_eligible is False
    assert result.coordinate_domain == "unresolved"


def test_bilateral_stop_is_not_forced_to_nonsense_or_extension() -> None:
    result = parse_partial_terminal_token("*261*")
    assert result.semantic_kind == "bilateral_stop_unresolved"
    assert result.source_position == 261
    assert result.stop_markers_present == 2
    assert result.position_eligible is False
    assert "nonsense" in result.interpretation_limit
    assert "extension" in result.interpretation_limit


def test_ordinary_stop_and_frameshift_are_not_consumed() -> None:
    for token in ("Y780*", "WQ288fs", "P953Hfs", "SDEL133fs"):
        assert parse_partial_terminal_token(token).parse_status == "not_applicable"

