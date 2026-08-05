from __future__ import annotations

import io

from open_cancer.isoform_semantics import (
    TranscriptAnnotation,
    classify_token_semantics,
    iter_fasta,
    parse_gtf_attributes,
)


def _annotation(
    transcript_id: str,
    sequence: str,
    *,
    mane: bool = False,
    canonical: bool = False,
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


def test_parse_gtf_attributes_preserves_repeated_tags() -> None:
    attributes = parse_gtf_attributes(
        'gene_id "ENSG1"; transcript_id "ENST1"; '
        'tag "MANE_Select"; tag "Ensembl_canonical";'
    )
    assert attributes["gene_id"] == "ENSG1"
    assert attributes["tag"] == "MANE_Select,Ensembl_canonical"


def test_iter_fasta_parses_ensembl_header() -> None:
    records = list(
        iter_fasta(
            io.StringIO(
                ">ENSP0001.2 pep chromosome:GRCh38 transcript:ENST0001.4 gene:ENSG1\n"
                "ACD\nEF\n"
            )
        )
    )
    assert records == [
        (
            "ENSP0001",
            "ACDEF",
            {
                "chromosome": "GRCh38",
                "transcript": "ENST0001.4",
                "gene": "ENSG1",
            },
        )
    ]


def test_semantic_category_priority_and_reference_check() -> None:
    annotations = (
        _annotation("ENST_MANE", "MAAA", mane=True, canonical=True),
        _annotation("ENST_OTHER", "MTAA"),
    )
    assert classify_token_semantics("GENE1", "A2T", annotations).category == (
        "MANE_MATCH"
    )
    assert classify_token_semantics("GENE1", "T2A", annotations).category == (
        "OTHER_ISOFORM_MATCH"
    )
    assert classify_token_semantics("GENE1", "C2A", annotations).category == (
        "POSITION_VALID_REF_MISMATCH"
    )
    assert classify_token_semantics("GENE1", "A8T", annotations).category == (
        "OUTSIDE_ALL_KNOWN_ISOFORMS"
    )


def test_complex_and_missing_annotation_are_unmappable() -> None:
    annotation = _annotation("ENST1", "MAAA", canonical=True)
    assert classify_token_semantics("GENE1", "A2_B3del", (annotation,)).category == (
        "COMPLEX_OR_UNMAPPABLE"
    )
    assert classify_token_semantics("UNKNOWN", "A2T", ()).category == (
        "COMPLEX_OR_UNMAPPABLE"
    )


def test_start_codon_and_unknown_reference_tokens_are_unmappable() -> None:
    # N6: parser v4 routing distinguishes M1 start-codon and leading-X
    # unknown-reference tokens from ordinary substitutions; the legacy lexical
    # parser did not, so these were previously eligible for isoform matching.
    annotation = _annotation("ENST1", "MAAA", mane=True)
    assert classify_token_semantics("GENE1", "M1V", (annotation,)).category == (
        "COMPLEX_OR_UNMAPPABLE"
    )
    assert classify_token_semantics("GENE1", "X2A", (annotation,)).category == (
        "COMPLEX_OR_UNMAPPABLE"
    )


def test_nonsense_and_no_change_tokens_remain_eligible() -> None:
    annotation = _annotation("ENST1", "MAAA", mane=True)
    assert classify_token_semantics("GENE1", "A2*", (annotation,)).category == (
        "MANE_MATCH"
    )
    assert classify_token_semantics("GENE1", "A2A", (annotation,)).category == (
        "MANE_MATCH"
    )
