from open_cancer.isoform_semantics import TranscriptAnnotation
from open_cancer.protein_frameshift_semantics import (
    parse_protein_frameshift_token,
    validate_frameshift_reference,
)


def _annotation(sequence: str, *, mane: bool = True) -> TranscriptAnnotation:
    return TranscriptAnnotation(
        gene_id="G", gene_symbol="GENE", gene_biotype="protein_coding",
        transcript_id="T", transcript_biotype="protein_coding", protein_id="P",
        is_mane_select=mane, is_canonical=mane, sequence=sequence,
    )


def test_two_observed_frameshift_orders_are_kept_distinct() -> None:
    before = parse_protein_frameshift_token("WQ288fs")
    assert before.grammar == "ref_alt_before_position"
    assert (before.reference_residue_candidate, before.position) == ("W", 288)
    assert before.first_new_peptide_candidate == "Q"

    after = parse_protein_frameshift_token("P953Hfs")
    assert after.grammar == "ref_position_alt"
    assert (after.reference_residue_candidate, after.position) == ("P", 953)
    assert after.first_new_peptide_candidate == "H"


def test_sdel_is_frameshift_peptide_candidate_not_deletion_keyword() -> None:
    parsed = parse_protein_frameshift_token("SDEL133fs")
    assert parsed.grammar == "ref_alt_before_position"
    assert parsed.reference_residue_candidate == "S"
    assert parsed.first_new_peptide_candidate == "DEL"


def test_reference_validation_does_not_rewrite_raw_token() -> None:
    sequence = "A" * 287 + "W" + "A" * 10
    parsed = parse_protein_frameshift_token("WQ288fs")
    validated = validate_frameshift_reference(parsed, (_annotation(sequence),))
    assert validated.reference_match_tier == "MANE_MATCH"
    assert validated.raw_token == "WQ288fs"
    assert validated.termination_distance is None


def test_non_frameshift_and_unknown_stop_distance() -> None:
    assert parse_protein_frameshift_token("G108del").parse_status == "not_applicable"
    parsed = parse_protein_frameshift_token("P953Hfs")
    assert parsed.termination_distance_known is False
