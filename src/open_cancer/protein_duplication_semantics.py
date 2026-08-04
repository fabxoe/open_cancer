"""Lossless protein insertion parsing and tandem-duplication semantics.

Competition tokens do not use the literal HGVS ``dup`` syntax.  Some test
tokens use ``<left>_<right>ins<sequence>`` even when the inserted sequence is
an immediate copy of the reference sequence directly N-terminal to the
insertion boundary.  This module preserves that source syntax and records the
reference-aware tandem-duplication interpretation separately.

No target, test prevalence, cancer label, or leaderboard result is used here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Literal, Mapping, Sequence

from open_cancer.isoform_semantics import TranscriptAnnotation


PROTEIN_DUPLICATION_SEMANTICS_VERSION = "4.0.0"

InsertionParseStatus = Literal[
    "complete", "partial", "not_applicable", "malformed"
]
DuplicationStatus = Literal[
    "REFERENCE_CONFIRMED",
    "STRONG_TOKEN_CANDIDATE",
    "REJECTED",
    "UNRESOLVED_REFERENCE",
    "UNRESOLVED_ISOFORM",
    "NOT_APPLICABLE",
]
DuplicationSemanticEvent = Literal[
    "tandem_duplication", "insertion", "other"
]

_AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"
_PURE_INSERTION = re.compile(
    rf"^(?P<left_residue>[{_AMINO_ACIDS}])"
    rf"(?P<left_position>[1-9][0-9]*)_"
    rf"(?P<right_residue>[{_AMINO_ACIDS}])"
    rf"(?P<right_position>[1-9][0-9]*)INS"
    rf"(?P<inserted_sequence>[A-Z*]+)$",
    re.IGNORECASE,
)
_PARTIAL_RIGHT_FLANK_INSERTION = re.compile(
    rf"^(?P<left_residue>[{_AMINO_ACIDS}])"
    rf"(?P<left_position>[1-9][0-9]*)_"
    rf"(?P<right_position>[1-9][0-9]*)INS"
    rf"(?P<inserted_sequence>[A-Z*]+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedProteinInsertion:
    """Lossless structure explicitly present in one insertion token."""

    raw_token: str
    normalized_token: str
    parse_status: InsertionParseStatus
    left_residue: str | None = None
    left_position: int | None = None
    right_residue: str | None = None
    boundary_residues_complete: bool = False
    right_position: int | None = None
    positions_adjacent: bool | None = None
    inserted_sequence: str | None = None
    inserted_length: int | None = None
    contains_stop: bool = False


@dataclass(frozen=True)
class ProteinDuplicationSemanticResult:
    """Reference-aware meaning added without replacing the raw insertion."""

    gene_symbol: str
    raw_token: str
    normalized_token: str
    syntax_event_type: str
    semantic_event_type: DuplicationSemanticEvent
    parse_status: InsertionParseStatus
    duplication_status: DuplicationStatus
    left_residue: str | None = None
    left_position: int | None = None
    right_residue: str | None = None
    resolved_right_residue: str | None = None
    boundary_residues_complete: bool = False
    right_position: int | None = None
    positions_adjacent: bool | None = None
    inserted_sequence: str | None = None
    inserted_length: int | None = None
    contains_stop: bool = False
    raw_source_start: int | None = None
    raw_source_end: int | None = None
    duplication_source_start: int | None = None
    duplication_source_end: int | None = None
    duplication_source_sequence: str | None = None
    duplication_length: int | None = None
    is_single_residue_duplication: bool = False
    is_range_duplication: bool = False
    is_direct_n_terminal_copy: bool = False
    is_tandem: bool = False
    reference_validated: bool = False
    flanking_residues_match: bool = False
    three_prime_normalized: bool = False
    three_prime_shift: int | None = None
    matched_transcript_ids: tuple[str, ...] = ()
    matched_protein_ids: tuple[str, ...] = ()
    matched_isoform_tier: str | None = None
    total_copy_number: int | None = None


@dataclass(frozen=True)
class _ConfirmedIsoformDuplication:
    annotation: TranscriptAnnotation
    raw_source_start: int
    raw_source_end: int
    canonical_source_start: int
    canonical_source_end: int
    three_prime_shift: int


def parse_protein_insertion_token(raw_token: str) -> ParsedProteinInsertion:
    """Parse the observed two-flank protein insertion grammar.

    ``delins`` is deliberately excluded even though it contains the substring
    ``ins``.  A token containing ``ins`` but not matching the complete grammar
    is reported as malformed instead of being coerced into a partial event.
    """

    raw = raw_token.strip()
    normalized = raw.upper()
    if "DELINS" in normalized or "INS" not in normalized:
        return ParsedProteinInsertion(raw, normalized, "not_applicable")

    match = _PURE_INSERTION.fullmatch(normalized)
    partial_right = False
    if match is None:
        match = _PARTIAL_RIGHT_FLANK_INSERTION.fullmatch(normalized)
        partial_right = match is not None
    if match is None:
        return ParsedProteinInsertion(raw, normalized, "malformed")

    left_position = int(match.group("left_position"))
    right_position = int(match.group("right_position"))
    inserted_sequence = match.group("inserted_sequence").upper()
    return ParsedProteinInsertion(
        raw_token=raw,
        normalized_token=normalized,
        parse_status="partial" if partial_right else "complete",
        left_residue=match.group("left_residue").upper(),
        left_position=left_position,
        right_residue=(
            None
            if partial_right
            else match.group("right_residue").upper()
        ),
        boundary_residues_complete=not partial_right,
        right_position=right_position,
        positions_adjacent=right_position == left_position + 1,
        inserted_sequence=inserted_sequence,
        inserted_length=len(inserted_sequence),
        contains_stop="*" in inserted_sequence or "X" in inserted_sequence,
    )


def canonicalize_tandem_duplication(
    reference_sequence: str,
    *,
    insertion_left_position: int,
    inserted_sequence: str,
) -> tuple[int, int, int] | None:
    """Return the most C-terminal equivalent source range (HGVS 3' rule).

    Positions are one-based.  The initial event inserts ``inserted_sequence``
    after ``insertion_left_position``.  Every possible direct tandem source is
    simulated against the same final protein sequence, and the most
    C-terminal equivalent representation is selected deterministically.
    """

    sequence = reference_sequence.upper().rstrip("*")
    inserted = inserted_sequence.upper()
    length = len(inserted)
    if (
        not sequence
        or not inserted
        or insertion_left_position < length
        or insertion_left_position >= len(sequence)
    ):
        return None

    raw_source = sequence[
        insertion_left_position - length : insertion_left_position
    ]
    if raw_source != inserted:
        return None

    target = (
        sequence[:insertion_left_position]
        + inserted
        + sequence[insertion_left_position:]
    )
    equivalent_boundaries: list[int] = []
    for boundary in range(length, len(sequence)):
        source = sequence[boundary - length : boundary]
        if source != inserted:
            continue
        candidate = sequence[:boundary] + source + sequence[boundary:]
        if candidate == target:
            equivalent_boundaries.append(boundary)

    if not equivalent_boundaries:
        return None
    canonical_end = max(equivalent_boundaries)
    canonical_start = canonical_end - length + 1
    return (
        canonical_start,
        canonical_end,
        canonical_end - insertion_left_position,
    )


def _isoform_tier(annotation: TranscriptAnnotation) -> str:
    if annotation.is_mane_select:
        return "MANE_SELECT"
    if annotation.is_canonical:
        return "ENSEMBL_CANONICAL"
    return "OTHER_ISOFORM"


def _base_result(
    gene_symbol: str,
    parsed: ParsedProteinInsertion,
    *,
    semantic_event_type: DuplicationSemanticEvent,
    duplication_status: DuplicationStatus,
) -> ProteinDuplicationSemanticResult:
    inserted_length = parsed.inserted_length
    left_position = parsed.left_position
    raw_start = (
        left_position - inserted_length + 1
        if left_position is not None
        and inserted_length is not None
        and left_position >= inserted_length
        else None
    )
    return ProteinDuplicationSemanticResult(
        gene_symbol=gene_symbol,
        raw_token=parsed.raw_token,
        normalized_token=parsed.normalized_token,
        syntax_event_type=(
            "insertion" if parsed.parse_status != "not_applicable" else "other"
        ),
        semantic_event_type=semantic_event_type,
        parse_status=parsed.parse_status,
        duplication_status=duplication_status,
        left_residue=parsed.left_residue,
        left_position=parsed.left_position,
        right_residue=parsed.right_residue,
        boundary_residues_complete=parsed.boundary_residues_complete,
        right_position=parsed.right_position,
        positions_adjacent=parsed.positions_adjacent,
        inserted_sequence=parsed.inserted_sequence,
        inserted_length=inserted_length,
        contains_stop=parsed.contains_stop,
        raw_source_start=raw_start,
        raw_source_end=left_position if raw_start is not None else None,
        duplication_length=inserted_length,
        is_single_residue_duplication=(
            semantic_event_type == "tandem_duplication" and inserted_length == 1
        ),
        is_range_duplication=(
            semantic_event_type == "tandem_duplication"
            and inserted_length is not None
            and inserted_length > 1
        ),
    )


def classify_protein_duplication(
    gene_symbol: str,
    raw_token: str,
    annotations: Sequence[TranscriptAnnotation],
) -> ProteinDuplicationSemanticResult:
    """Classify one token as insertion or reference-confirmed tandem copy."""

    parsed = parse_protein_insertion_token(raw_token)
    if parsed.parse_status not in {"complete", "partial"}:
        return _base_result(
            gene_symbol,
            parsed,
            semantic_event_type="other",
            duplication_status="NOT_APPLICABLE",
        )
    if parsed.contains_stop:
        return _base_result(
            gene_symbol,
            parsed,
            semantic_event_type="insertion",
            duplication_status="NOT_APPLICABLE",
        )
    if not parsed.positions_adjacent:
        return _base_result(
            gene_symbol,
            parsed,
            semantic_event_type="insertion",
            duplication_status="REJECTED",
        )

    assert parsed.left_position is not None
    assert parsed.right_position is not None
    assert parsed.left_residue is not None
    assert parsed.inserted_sequence is not None
    assert parsed.inserted_length is not None

    token_candidate = (
        parsed.inserted_length == 1
        and parsed.inserted_sequence == parsed.left_residue
    )
    if not annotations:
        return _base_result(
            gene_symbol,
            parsed,
            semantic_event_type=(
                "tandem_duplication" if token_candidate else "insertion"
            ),
            duplication_status=(
                "STRONG_TOKEN_CANDIDATE"
                if token_candidate
                else "UNRESOLVED_REFERENCE"
            ),
        )

    confirmed: list[_ConfirmedIsoformDuplication] = []
    flanking_match_count = 0
    for annotation in annotations:
        sequence = annotation.sequence.upper().rstrip("*")
        if parsed.right_position > len(sequence):
            continue
        if (
            sequence[parsed.left_position - 1] != parsed.left_residue
            or (
                parsed.right_residue is not None
                and sequence[parsed.right_position - 1] != parsed.right_residue
            )
        ):
            continue
        flanking_match_count += 1
        raw_start = parsed.left_position - parsed.inserted_length + 1
        if raw_start < 1:
            continue
        canonical = canonicalize_tandem_duplication(
            sequence,
            insertion_left_position=parsed.left_position,
            inserted_sequence=parsed.inserted_sequence,
        )
        if canonical is None:
            continue
        canonical_start, canonical_end, shift = canonical
        confirmed.append(
            _ConfirmedIsoformDuplication(
                annotation=annotation,
                raw_source_start=raw_start,
                raw_source_end=parsed.left_position,
                canonical_source_start=canonical_start,
                canonical_source_end=canonical_end,
                three_prime_shift=shift,
            )
        )

    if not confirmed:
        status: DuplicationStatus = (
            "REJECTED" if flanking_match_count else "UNRESOLVED_ISOFORM"
        )
        return _base_result(
            gene_symbol,
            parsed,
            semantic_event_type=(
                "tandem_duplication"
                if token_candidate and status == "UNRESOLVED_ISOFORM"
                else "insertion"
            ),
            duplication_status=status,
        )

    mane = [item for item in confirmed if item.annotation.is_mane_select]
    canonical = [
        item
        for item in confirmed
        if not item.annotation.is_mane_select and item.annotation.is_canonical
    ]
    selected = mane or canonical or confirmed
    interpretations = {
        (
            item.raw_source_start,
            item.raw_source_end,
            item.canonical_source_start,
            item.canonical_source_end,
            item.three_prime_shift,
        )
        for item in selected
    }
    if len(interpretations) != 1:
        result = _base_result(
            gene_symbol,
            parsed,
            semantic_event_type="tandem_duplication",
            duplication_status="UNRESOLVED_ISOFORM",
        )
        return replace(
            result,
            matched_transcript_ids=tuple(
                item.annotation.transcript_id for item in selected
            ),
            matched_protein_ids=tuple(
                item.annotation.protein_id for item in selected
            ),
        )

    chosen = selected[0]
    result = _base_result(
        gene_symbol,
        parsed,
        semantic_event_type="tandem_duplication",
        duplication_status="REFERENCE_CONFIRMED",
    )
    return replace(
        result,
        raw_source_start=chosen.raw_source_start,
        raw_source_end=chosen.raw_source_end,
        duplication_source_start=chosen.canonical_source_start,
        duplication_source_end=chosen.canonical_source_end,
        duplication_source_sequence=parsed.inserted_sequence,
        resolved_right_residue=chosen.annotation.sequence[
            parsed.right_position - 1
        ].upper(),
        is_direct_n_terminal_copy=True,
        is_tandem=True,
        reference_validated=True,
        flanking_residues_match=True,
        three_prime_normalized=True,
        three_prime_shift=chosen.three_prime_shift,
        matched_transcript_ids=tuple(
            item.annotation.transcript_id for item in selected
        ),
        matched_protein_ids=tuple(
            item.annotation.protein_id for item in selected
        ),
        matched_isoform_tier=_isoform_tier(chosen.annotation),
    )


def classify_gene_duplications(
    gene_symbol: str,
    cell: str,
    annotation_index: Mapping[str, Sequence[TranscriptAnnotation]],
) -> tuple[ProteinDuplicationSemanticResult, ...]:
    """Classify every non-WT token in one competition gene cell."""

    if not isinstance(cell, str) or not cell.strip():
        return ()
    annotations = annotation_index.get(gene_symbol, ())
    return tuple(
        classify_protein_duplication(gene_symbol, token, annotations)
        for token in cell.split()
        if token and token.upper() != "WT"
    )


def duplication_gene_summary(
    results: Sequence[ProteinDuplicationSemanticResult],
) -> dict[str, int]:
    """Return compact target-independent gene-level semantic counts."""

    confirmed = [
        result
        for result in results
        if result.duplication_status == "REFERENCE_CONFIRMED"
    ]
    unresolved = [
        result
        for result in results
        if result.duplication_status
        in {
            "STRONG_TOKEN_CANDIDATE",
            "UNRESOLVED_REFERENCE",
            "UNRESOLVED_ISOFORM",
        }
    ]
    lengths = [result.duplication_length or 0 for result in confirmed]
    return {
        "tandem_duplication_present": int(bool(confirmed)),
        "tandem_duplication_count": len(confirmed),
        "single_residue_duplication_count": sum(
            result.is_single_residue_duplication for result in confirmed
        ),
        "range_duplication_count": sum(
            result.is_range_duplication for result in confirmed
        ),
        "duplicated_residue_total": sum(lengths),
        "max_duplicated_length": max(lengths, default=0),
        "duplication_reference_confirmed": int(bool(confirmed)),
        "duplication_unresolved": len(unresolved),
    }
