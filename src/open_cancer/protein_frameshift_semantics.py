"""Conservative semantics for the two observed compact frameshift grammars."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Literal, Sequence

from open_cancer.isoform_semantics import TranscriptAnnotation


PROTEIN_FRAMESHIFT_SEMANTICS_VERSION = "4.0.0"
FrameshiftGrammar = Literal[
    "ref_alt_before_position", "ref_position_alt", "short_ref_position", "other"
]
ReferenceMatchTier = Literal[
    "MANE_MATCH", "CANONICAL_MATCH", "OTHER_ISOFORM_MATCH",
    "POSITION_VALID_REF_MISMATCH", "OUTSIDE_ALL_KNOWN_ISOFORMS",
    "NO_REFERENCE", "NOT_APPLICABLE",
]

_AA = "ACDEFGHIKLMNPQRSTVWY"
_PREFIX_POSITION = re.compile(
    rf"^(?P<prefix>[{_AA}]+)(?P<position>[1-9][0-9]*)FS$", re.IGNORECASE
)
_REF_POSITION_ALT = re.compile(
    rf"^(?P<reference>[{_AA}])(?P<position>[1-9][0-9]*)"
    rf"(?P<alternate>[{_AA}]+)FS$", re.IGNORECASE
)


@dataclass(frozen=True)
class ProteinFrameshiftSemanticResult:
    raw_token: str
    normalized_token: str
    parse_status: str
    event_type: str
    grammar: FrameshiftGrammar
    position: int | None = None
    reference_residue_candidate: str | None = None
    first_new_peptide_candidate: str | None = None
    termination_distance: int | None = None
    termination_distance_known: bool = False
    reference_match_tier: ReferenceMatchTier = "NOT_APPLICABLE"
    matched_transcript_ids: tuple[str, ...] = ()
    matched_protein_ids: tuple[str, ...] = ()
    parser_definition_version: str = PROTEIN_FRAMESHIFT_SEMANTICS_VERSION


def parse_protein_frameshift_token(raw_token: str) -> ProteinFrameshiftSemanticResult:
    raw = raw_token.strip()
    normalized = raw.upper()
    post = _REF_POSITION_ALT.fullmatch(normalized)
    if post is not None:
        return ProteinFrameshiftSemanticResult(
            raw, normalized, "partial", "frameshift", "ref_position_alt",
            int(post.group("position")), post.group("reference").upper(),
            post.group("alternate").upper(),
        )
    prefix = _PREFIX_POSITION.fullmatch(normalized)
    if prefix is not None:
        sequence = prefix.group("prefix").upper()
        grammar: FrameshiftGrammar = (
            "short_ref_position" if len(sequence) == 1 else "ref_alt_before_position"
        )
        return ProteinFrameshiftSemanticResult(
            raw, normalized, "partial", "frameshift", grammar,
            int(prefix.group("position")), sequence[0], sequence[1:] or None,
        )
    return ProteinFrameshiftSemanticResult(
        raw, normalized, "not_applicable", "other", "other"
    )


def validate_frameshift_reference(
    parsed: ProteinFrameshiftSemanticResult,
    annotations: Sequence[TranscriptAnnotation],
) -> ProteinFrameshiftSemanticResult:
    if parsed.parse_status == "not_applicable" or parsed.position is None:
        return parsed
    if not annotations:
        return replace(parsed, reference_match_tier="NO_REFERENCE")
    valid = tuple(a for a in annotations if parsed.position <= len(a.sequence))
    if not valid:
        return replace(parsed, reference_match_tier="OUTSIDE_ALL_KNOWN_ISOFORMS")
    matches = tuple(
        a for a in valid
        if a.sequence[parsed.position - 1] == parsed.reference_residue_candidate
    )
    mane = tuple(a for a in matches if a.is_mane_select)
    canonical = tuple(a for a in matches if a.is_canonical)
    if mane:
        selected, tier = mane, "MANE_MATCH"
    elif canonical:
        selected, tier = canonical, "CANONICAL_MATCH"
    elif matches:
        selected, tier = matches, "OTHER_ISOFORM_MATCH"
    else:
        selected, tier = valid, "POSITION_VALID_REF_MISMATCH"
    return replace(
        parsed,
        reference_match_tier=tier,
        matched_transcript_ids=tuple(sorted({a.transcript_id for a in selected})),
        matched_protein_ids=tuple(sorted({a.protein_id for a in selected})),
    )
