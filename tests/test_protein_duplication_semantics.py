from __future__ import annotations

from open_cancer.isoform_semantics import TranscriptAnnotation
from open_cancer.protein_duplication_semantics import (
    canonicalize_tandem_duplication,
    classify_protein_duplication,
    duplication_gene_summary,
    parse_protein_insertion_token,
)


def _annotation(
    sequence: str,
    *,
    transcript_id: str = "ENST1",
    mane: bool = True,
    canonical: bool = True,
) -> TranscriptAnnotation:
    return TranscriptAnnotation(
        gene_id="ENSG1",
        gene_symbol="GENE1",
        gene_biotype="protein_coding",
        transcript_id=transcript_id,
        transcript_biotype="protein_coding",
        protein_id=f"ENSP_{transcript_id}",
        is_mane_select=mane,
        is_canonical=canonical,
        sequence=sequence,
    )


def test_lossless_insertion_parser_preserves_boundary_and_sequence() -> None:
    parsed = parse_protein_insertion_token("K745_E746insIPVAIK")
    assert parsed.raw_token == "K745_E746insIPVAIK"
    assert parsed.normalized_token == "K745_E746INSIPVAIK"
    assert parsed.parse_status == "complete"
    assert parsed.left_residue == "K"
    assert parsed.left_position == 745
    assert parsed.right_residue == "E"
    assert parsed.right_position == 746
    assert parsed.positions_adjacent is True
    assert parsed.inserted_sequence == "IPVAIK"
    assert parsed.inserted_length == 6


def test_delins_is_not_misread_as_pure_insertion() -> None:
    parsed = parse_protein_insertion_token("E1117delinsGGRRIIK")
    assert parsed.parse_status == "not_applicable"


def test_unobserved_single_boundary_insertion_is_malformed() -> None:
    parsed = parse_protein_insertion_token("H4insA")
    assert parsed.parse_status == "malformed"


def test_observed_missing_right_residue_is_preserved_as_partial_boundary() -> None:
    parsed = parse_protein_insertion_token("G7_8insIPVAIK")
    assert parsed.parse_status == "partial"
    assert parsed.left_residue == "G"
    assert parsed.left_position == 7
    assert parsed.right_residue is None
    assert parsed.right_position == 8
    assert parsed.positions_adjacent is True
    assert parsed.boundary_residues_complete is False


def test_partial_right_residue_can_be_resolved_from_fixed_reference() -> None:
    annotation = _annotation("MIPVAIKG")
    result = classify_protein_duplication(
        "GENE1", "K7_8insIPVAIK", (annotation,)
    )
    assert result.parse_status == "partial"
    assert result.duplication_status == "REFERENCE_CONFIRMED"
    assert result.right_residue is None
    assert result.resolved_right_residue == "G"
    assert result.flanking_residues_match is True


def test_single_left_copy_is_strong_candidate_without_reference() -> None:
    result = classify_protein_duplication("GENE1", "Q80_E81insQ", ())
    assert result.syntax_event_type == "insertion"
    assert result.semantic_event_type == "tandem_duplication"
    assert result.duplication_status == "STRONG_TOKEN_CANDIDATE"
    assert result.raw_source_start == 80
    assert result.raw_source_end == 80
    assert result.is_single_residue_duplication is True
    assert result.reference_validated is False


def test_multiresidue_tandem_copy_is_reference_confirmed() -> None:
    annotation = _annotation("MIPVAIKE")
    result = classify_protein_duplication(
        "GENE1", "K7_E8insIPVAIK", (annotation,)
    )
    assert result.semantic_event_type == "tandem_duplication"
    assert result.duplication_status == "REFERENCE_CONFIRMED"
    assert result.raw_source_start == 2
    assert result.raw_source_end == 7
    assert result.duplication_source_start == 2
    assert result.duplication_source_end == 7
    assert result.duplication_source_sequence == "IPVAIK"
    assert result.is_range_duplication is True
    assert result.is_direct_n_terminal_copy is True
    assert result.is_tandem is True
    assert result.matched_isoform_tier == "MANE_SELECT"


def test_nearby_but_non_tandem_copy_remains_insertion() -> None:
    annotation = _annotation("MGSSHQAA")
    result = classify_protein_duplication(
        "GENE1", "H5_Q6insGSS", (annotation,)
    )
    assert result.semantic_event_type == "insertion"
    assert result.duplication_status == "REJECTED"
    assert result.reference_validated is False


def test_non_adjacent_flanks_are_rejected() -> None:
    annotation = _annotation("MAAAE")
    result = classify_protein_duplication(
        "GENE1", "A2_A4insA", (annotation,)
    )
    assert result.positions_adjacent is False
    assert result.duplication_status == "REJECTED"


def test_three_prime_rule_chooses_most_c_terminal_equivalent_copy() -> None:
    assert canonicalize_tandem_duplication(
        "MAAAE", insertion_left_position=2, inserted_sequence="A"
    ) == (4, 4, 2)
    result = classify_protein_duplication(
        "GENE1", "A2_A3insA", (_annotation("MAAAE"),)
    )
    assert result.duplication_status == "REFERENCE_CONFIRMED"
    assert result.raw_source_start == 2
    assert result.raw_source_end == 2
    assert result.duplication_source_start == 4
    assert result.duplication_source_end == 4
    assert result.three_prime_shift == 2
    assert result.three_prime_normalized is True


def test_disagreeing_isoform_canonical_ranges_stay_unresolved() -> None:
    annotations = (
        _annotation("MAAE", transcript_id="ENST1"),
        _annotation("MAAAE", transcript_id="ENST2"),
    )
    result = classify_protein_duplication(
        "GENE1", "A2_A3insA", annotations
    )
    assert result.semantic_event_type == "tandem_duplication"
    assert result.duplication_status == "UNRESOLVED_ISOFORM"
    assert result.reference_validated is False
    assert result.matched_transcript_ids == ("ENST1", "ENST2")


def test_reference_missing_multiresidue_insertion_stays_unresolved() -> None:
    result = classify_protein_duplication(
        "UNKNOWN", "K7_E8insIPVAIK", ()
    )
    assert result.semantic_event_type == "insertion"
    assert result.duplication_status == "UNRESOLVED_REFERENCE"


def test_stop_containing_insertion_does_not_become_duplication() -> None:
    result = classify_protein_duplication(
        "GENE1", "A2_A3ins*", (_annotation("MAAAE"),)
    )
    assert result.contains_stop is True
    assert result.semantic_event_type == "insertion"
    assert result.duplication_status == "NOT_APPLICABLE"


def test_literal_duplication_and_frameshift_are_not_reinterpreted() -> None:
    for token in ("A20dup", "SDEL133fs", "-762fs"):
        result = classify_protein_duplication("GENE1", token, ())
        assert result.semantic_event_type == "other"
        assert result.duplication_status == "NOT_APPLICABLE"


def test_gene_summary_counts_only_reference_confirmed_events() -> None:
    annotation = _annotation("MIPVAIKE")
    confirmed = classify_protein_duplication(
        "GENE1", "K7_E8insIPVAIK", (annotation,)
    )
    unresolved = classify_protein_duplication(
        "GENE1", "Q80_E81insQ", ()
    )
    summary = duplication_gene_summary((confirmed, unresolved))
    assert summary == {
        "tandem_duplication_present": 1,
        "tandem_duplication_count": 1,
        "single_residue_duplication_count": 0,
        "range_duplication_count": 1,
        "duplicated_residue_total": 6,
        "max_duplicated_length": 6,
        "duplication_reference_confirmed": 1,
        "duplication_unresolved": 1,
    }
