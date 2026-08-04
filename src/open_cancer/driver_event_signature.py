"""Evidence-tiered canonical signatures for literature-backed protein drivers.

The raw competition annotation is never replaced.  A fixed catalog may attach a
canonical event signature at one of three evidence tiers: exact canonical
notation, reference-confirmed isoform projection, or family-level equivalence.
The last tier preserves driver presence but is not an exact coordinate claim.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

from open_cancer.isoform_semantics import TranscriptAnnotation
from open_cancer.protein_duplication_semantics import (
    ProteinDuplicationSemanticResult,
    classify_protein_duplication,
)


DRIVER_EVENT_SIGNATURE_VERSION = "1.0.0"
EquivalenceConfidence = Literal[
    "EXACT",
    "ISOFORM_PROJECTED",
    "FAMILY_LEVEL",
    "NO_MATCH",
]


@dataclass(frozen=True)
class DriverCatalogEvent:
    event_id: str
    gene_symbol: str
    gene_id: str
    reference_transcript: str
    reference_protein: str
    canonical_protein_event: str
    semantic_family: str
    inserted_sequence: str
    source_start: int
    source_end: int
    pathway_memberships: tuple[str, ...]
    hotspot_positions: tuple[int, ...]


@dataclass(frozen=True)
class DriverEventMatch:
    raw_token: str
    normalized_token: str
    event_id: str | None
    canonical_signature: str | None
    canonical_protein_event: str | None
    driver_presence: int
    annotation_multiplicity: int
    equivalence_confidence: EquivalenceConfidence
    exact_coordinate_equivalence: bool
    reference_validated: bool
    matched_transcript_ids: tuple[str, ...]
    matched_protein_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class DriverCellSummary:
    driver_presence: int
    independent_driver_event_count: int
    annotation_multiplicity: int
    exact_match_count: int
    isoform_projected_count: int
    family_level_count: int
    canonical_signatures: tuple[str, ...]
    raw_tokens: tuple[str, ...]
    matches: tuple[DriverEventMatch, ...]


def load_driver_catalog(path: Path) -> tuple[DriverCatalogEvent, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        DriverCatalogEvent(
            event_id=item["event_id"],
            gene_symbol=item["gene_symbol"],
            gene_id=item["gene_id"],
            reference_transcript=item["reference_transcript"],
            reference_protein=item["reference_protein"],
            canonical_protein_event=item["canonical_protein_event"],
            semantic_family=item["semantic_family"],
            inserted_sequence=item["inserted_sequence"],
            source_start=int(item["source_start"]),
            source_end=int(item["source_end"]),
            pathway_memberships=tuple(item.get("pathway_memberships", ())),
            hotspot_positions=tuple(item.get("hotspot_positions", ())),
        )
        for item in payload["events"]
    )


def canonical_signature(event: DriverCatalogEvent) -> str:
    return (
        f"{event.gene_id}|{event.reference_transcript}|"
        f"{event.canonical_protein_event}|{event.semantic_family}"
    )


def _no_match(result: ProteinDuplicationSemanticResult) -> DriverEventMatch:
    return DriverEventMatch(
        raw_token=result.raw_token,
        normalized_token=result.normalized_token,
        event_id=None,
        canonical_signature=None,
        canonical_protein_event=None,
        driver_presence=0,
        annotation_multiplicity=1,
        equivalence_confidence="NO_MATCH",
        exact_coordinate_equivalence=False,
        reference_validated=result.reference_validated,
        matched_transcript_ids=result.matched_transcript_ids,
        matched_protein_ids=result.matched_protein_ids,
        reason="no fixed catalog event matches gene and inserted sequence",
    )


def match_driver_event(
    result: ProteinDuplicationSemanticResult,
    catalog: Sequence[DriverCatalogEvent],
) -> DriverEventMatch:
    """Attach a catalog signature while retaining the evidence tier."""

    candidates = [
        event
        for event in catalog
        if event.gene_symbol == result.gene_symbol
        and event.inserted_sequence == result.inserted_sequence
    ]
    if len(candidates) != 1:
        return _no_match(result)
    event = candidates[0]
    signature = canonical_signature(event)

    exact = (
        result.reference_validated
        and result.duplication_source_start == event.source_start
        and result.duplication_source_end == event.source_end
        and event.reference_transcript.split(".", 1)[0]
        in result.matched_transcript_ids
    )
    if exact:
        confidence: EquivalenceConfidence = "EXACT"
        reason = "fixed MANE/reference coordinates equal the catalog event"
    elif result.reference_validated:
        confidence = "ISOFORM_PROJECTED"
        reason = (
            "fixed alternative isoform confirms the same tandem-copy product; "
            "canonical coordinates come from the catalog reference transcript"
        )
    else:
        confidence = "FAMILY_LEVEL"
        reason = (
            "gene and inserted peptide match the fixed driver family, but the "
            "observed coordinates lack reference confirmation"
        )

    return DriverEventMatch(
        raw_token=result.raw_token,
        normalized_token=result.normalized_token,
        event_id=event.event_id,
        canonical_signature=signature,
        canonical_protein_event=event.canonical_protein_event,
        driver_presence=1,
        annotation_multiplicity=1,
        equivalence_confidence=confidence,
        exact_coordinate_equivalence=exact,
        reference_validated=result.reference_validated,
        matched_transcript_ids=result.matched_transcript_ids,
        matched_protein_ids=result.matched_protein_ids,
        reason=reason,
    )


def summarize_driver_cell(
    gene_symbol: str,
    cell: str,
    annotation_index: Mapping[str, Sequence[TranscriptAnnotation]],
    catalog: Sequence[DriverCatalogEvent],
) -> DriverCellSummary:
    raw_tokens = tuple(
        token for token in cell.split() if token and token.upper() != "WT"
    )
    matches = tuple(
        match_driver_event(
            classify_protein_duplication(
                gene_symbol, token, annotation_index.get(gene_symbol, ())
            ),
            catalog,
        )
        for token in raw_tokens
    )
    signatures = tuple(
        sorted(
            {
                match.canonical_signature
                for match in matches
                if match.canonical_signature is not None
            }
        )
    )
    return DriverCellSummary(
        driver_presence=int(bool(signatures)),
        independent_driver_event_count=len(signatures),
        annotation_multiplicity=len(raw_tokens),
        exact_match_count=sum(
            match.equivalence_confidence == "EXACT" for match in matches
        ),
        isoform_projected_count=sum(
            match.equivalence_confidence == "ISOFORM_PROJECTED"
            for match in matches
        ),
        family_level_count=sum(
            match.equivalence_confidence == "FAMILY_LEVEL" for match in matches
        ),
        canonical_signatures=signatures,
        raw_tokens=raw_tokens,
        matches=matches,
    )

