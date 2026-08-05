from pathlib import Path

from open_cancer.driver_event_signature import (
    load_driver_catalog,
    summarize_driver_cell,
)
from open_cancer.isoform_semantics import TranscriptAnnotation


ROOT = Path(__file__).resolve().parents[1]
CATALOG = load_driver_catalog(ROOT / "knowledge/known_driver_protein_events_v1.json")


def _annotation(
    sequence: str,
    transcript_id: str,
    protein_id: str,
    *,
    mane: bool = False,
) -> TranscriptAnnotation:
    return TranscriptAnnotation(
        gene_id="ENSG00000146648",
        gene_symbol="EGFR",
        gene_biotype="protein_coding",
        transcript_id=transcript_id,
        transcript_biotype="protein_coding",
        protein_id=protein_id,
        is_mane_select=mane,
        is_canonical=mane,
        sequence=sequence,
    )


def _egfr_like(length_before: int) -> str:
    return "A" * (length_before - 6) + "IPVAIK" + "E" + "A" * 100


def test_four_annotations_collapse_to_one_driver_without_losing_presence() -> None:
    annotations = (
        _annotation(
            _egfr_like(745),
            "ENST00000275493",
            "ENSP00000275493",
            mane=True,
        ),
        _annotation(_egfr_like(692), "ENST_ALT692", "ENSP_ALT692"),
        _annotation(_egfr_like(700), "ENST_ALT700", "ENSP_ALT700"),
    )
    cell = (
        "K692_E693insIPVAIK K745_E746insIPVAIK "
        "K478_E479insIPVAIK K700_E701insIPVAIK"
    )
    result = summarize_driver_cell(
        "EGFR", cell, {"EGFR": annotations}, CATALOG
    )
    assert result.annotation_multiplicity == 4
    assert result.driver_presence == 1
    assert result.independent_driver_event_count == 1
    assert result.exact_match_count == 1
    assert result.isoform_projected_count == 2
    assert result.family_level_count == 1
    assert len(result.canonical_signatures) == 1


def test_unrelated_insertion_is_not_marked_as_driver() -> None:
    result = summarize_driver_cell(
        "EGFR", "K745_E746insVPVAIK", {}, CATALOG
    )
    assert result.driver_presence == 0
    assert result.independent_driver_event_count == 0
    assert result.matches[0].equivalence_confidence == "NO_MATCH"


def test_cross_patient_calls_are_not_collapsed_together() -> None:
    first = summarize_driver_cell(
        "EGFR", "K745_E746insIPVAIK", {}, CATALOG
    )
    second = summarize_driver_cell(
        "EGFR", "K745_E746insIPVAIK", {}, CATALOG
    )
    assert first.driver_presence == 1
    assert second.driver_presence == 1
    assert first.annotation_multiplicity + second.annotation_multiplicity == 2

