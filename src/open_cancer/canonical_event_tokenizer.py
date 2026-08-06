"""Canonical patient event tokens derived from the parser-v4 contract.

This module is deliberately model-agnostic.  It turns lossless routed protein
events into a bounded, deterministic multiset without exposing arbitrary raw
peptide strings as vocabulary entries.  Vocabulary fitting and support/OOV
filtering belong to a later fold-train-only step.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from open_cancer.canonical_mutation_events import parse_canonical_gene_cell
from open_cancer.mutation_parser_contract import RoutedProteinMutation
from open_cancer.parser_native_v2_features import native_v2_primary_family
from open_cancer.parser_semantic_completeness import semantic_subfamily_key


CANONICAL_EVENT_TOKENIZER_VERSION = "1.0.0"
DEFAULT_POSITION_BIN_WIDTH = 100
_AMINO_ACIDS = frozenset("ACDEFGHIKLMNPQRSTVWY")


def _length_bucket(value: int) -> str:
    if value < 0:
        raise ValueError("length must be non-negative")
    if value <= 2:
        return str(value)
    if value <= 5:
        return "3-5"
    if value <= 10:
        return "6-10"
    if value <= 20:
        return "11-20"
    if value <= 50:
        return "21-50"
    return "51+"


def _position_bin(position: int, width: int) -> str:
    if position < 1:
        raise ValueError("protein positions are one-based")
    if width < 1:
        raise ValueError("position_bin_width must be positive")
    start = ((position - 1) // width) * width + 1
    return f"{start}-{start + width - 1}"


def _token(gene: str, key: str, value: object) -> str:
    return f"gene={gene.upper()}|{key}={value}"


def _amino_acid_tokens(
    gene: str, *, key: str, sequence: object
) -> list[str]:
    if not isinstance(sequence, str):
        return []
    return [
        _token(gene, key, residue)
        for residue in sequence.upper()
        if residue in _AMINO_ACIDS
    ]


def canonical_event_tokens(
    gene_symbol: str,
    routed: RoutedProteinMutation,
    *,
    position_bin_width: int = DEFAULT_POSITION_BIN_WIDTH,
) -> tuple[str, ...]:
    """Project one routed event into a bounded semantic token multiset.

    Duplicate returned tokens are intentional: they retain amino-acid counts
    while keeping the vocabulary bounded.  Exact raw tokens and arbitrary
    full peptide strings are never used as feature names.
    """

    gene = gene_symbol.upper()
    payload = routed.payload
    family = native_v2_primary_family(routed, gene_symbol=gene)
    tokens: list[str] = [_token(gene, "family", family)]

    if routed.parse_status != "complete":
        tokens.append(_token(gene, "parse_status", routed.parse_status))
    tokens.append(
        _token(gene, "subfamily", semantic_subfamily_key(routed))
    )

    positions = sorted(set(routed.positions))
    for position in positions:
        tokens.append(
            _token(gene, "position_bin", _position_bin(position, position_bin_width))
        )
    if len(positions) >= 2:
        span = positions[-1] - positions[0] + 1
        tokens.append(_token(gene, "position_span", _length_bucket(span)))

    if routed.route == "substitution":
        reference = payload.get("reference_residue")
        alternate = payload.get("alternate_residue_canonical")
        if (
            isinstance(reference, str)
            and len(reference) == 1
            and reference.upper() in _AMINO_ACIDS
            and isinstance(alternate, str)
            and (alternate.upper() in _AMINO_ACIDS or alternate == "*")
        ):
            alt = "STOP" if alternate == "*" else alternate.upper()
            tokens.append(_token(gene, "aa_transition", f"{reference.upper()}>{alt}"))

    elif routed.route == "frameshift":
        first_new = payload.get("first_new_peptide_candidate")
        # Compact forms such as SDEL133fs do not prove that DEL is a peptide.
        if (
            isinstance(first_new, str)
            and len(first_new) == 1
            and first_new.upper() in _AMINO_ACIDS
        ):
            tokens.append(_token(gene, "frameshift_first_new_aa", first_new.upper()))
        grammar = payload.get("grammar")
        if grammar:
            tokens.append(_token(gene, "frameshift_grammar", grammar))

    elif routed.route == "deletion":
        deleted_length = payload.get("deleted_length")
        if isinstance(deleted_length, int):
            tokens.append(
                _token(gene, "deleted_length", _length_bucket(deleted_length))
            )

    elif routed.route == "insertion":
        inserted_length = payload.get("inserted_length")
        if isinstance(inserted_length, int):
            tokens.append(
                _token(gene, "inserted_length", _length_bucket(inserted_length))
            )
        tokens.extend(
            _amino_acid_tokens(
                gene, key="inserted_aa", sequence=payload.get("inserted_sequence")
            )
        )

    elif routed.route == "delins":
        reference_length = payload.get("reference_span_length")
        alternate_length = payload.get("translated_alternate_length")
        net_change = payload.get("net_length_change")
        if isinstance(reference_length, int):
            tokens.append(
                _token(gene, "replaced_length", _length_bucket(reference_length))
            )
        if isinstance(alternate_length, int):
            tokens.append(
                _token(gene, "replacement_length", _length_bucket(alternate_length))
            )
        if isinstance(net_change, int):
            direction = "negative" if net_change < 0 else "positive" if net_change > 0 else "zero"
            tokens.append(_token(gene, "net_length_change", direction))
        tokens.extend(
            _amino_acid_tokens(
                gene,
                key="replacement_aa",
                sequence=payload.get("translated_alternate_sequence"),
            )
        )

    elif routed.route == "range_replacement":
        reference = payload.get("reference_sequence")
        alternate = payload.get("translated_alternate_sequence")
        if isinstance(reference, str):
            tokens.append(
                _token(gene, "range_reference_length", _length_bucket(len(reference)))
            )
        if isinstance(alternate, str):
            tokens.append(
                _token(gene, "range_alternate_length", _length_bucket(len(alternate)))
            )
        tokens.extend(
            _amino_acid_tokens(gene, key="range_reference_aa", sequence=reference)
        )
        tokens.extend(
            _amino_acid_tokens(gene, key="range_alternate_aa", sequence=alternate)
        )

    elif routed.route == "unresolved":
        structure = payload.get("source_structure")
        if structure:
            tokens.append(_token(gene, "unresolved_structure", structure))

    return tuple(tokens)


@dataclass(frozen=True)
class PatientEventTokens:
    """Deterministic sparse token multiset and source-cell provenance."""

    token_counts: tuple[tuple[str, int], ...]
    source_event_count: int
    blank_gene_cell_count: int
    wt_gene_cell_count: int
    partial_event_count: int
    unresolved_event_count: int
    tokenizer_version: str = CANONICAL_EVENT_TOKENIZER_VERSION

    @property
    def unique_token_count(self) -> int:
        return len(self.token_counts)

    @property
    def token_occurrence_count(self) -> int:
        return sum(count for _, count in self.token_counts)

    @property
    def sha256(self) -> str:
        payload = {
            "tokenizer_version": self.tokenizer_version,
            "token_counts": self.token_counts,
            "source_event_count": self.source_event_count,
            "blank_gene_cell_count": self.blank_gene_cell_count,
            "wt_gene_cell_count": self.wt_gene_cell_count,
            "partial_event_count": self.partial_event_count,
            "unresolved_event_count": self.unresolved_event_count,
        }
        encoded = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def as_counter(self) -> Counter[str]:
        return Counter(dict(self.token_counts))


@dataclass(frozen=True)
class CanonicalEventVocabulary:
    """Stable lexicographic vocabulary built from an explicit train scope."""

    tokens: tuple[str, ...]
    tokenizer_version: str = CANONICAL_EVENT_TOKENIZER_VERSION

    @property
    def sha256(self) -> str:
        encoded = json.dumps(
            {
                "tokenizer_version": self.tokenizer_version,
                "tokens": self.tokens,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def index(self) -> dict[str, int]:
        return {token: index for index, token in enumerate(self.tokens)}

    def encode(
        self, patient: PatientEventTokens
    ) -> tuple[tuple[int, int], ...]:
        """Return sparse ``(column, count)`` pairs; unknown tokens are OOV."""

        index = self.index()
        return tuple(
            (index[token], count)
            for token, count in patient.token_counts
            if token in index
        )


@dataclass(frozen=True)
class EventTokenizerAuditSummary:
    patient_count: int
    source_event_count: int
    token_occurrence_count: int
    unique_token_count: int
    blank_gene_cell_count: int
    wt_gene_cell_count: int
    partial_event_count: int
    unresolved_event_count: int
    vocabulary_sha256: str
    tokenizer_version: str = CANONICAL_EVENT_TOKENIZER_VERSION


def build_event_vocabulary(
    patients: Iterable[PatientEventTokens],
) -> CanonicalEventVocabulary:
    """Build a threshold-free vocabulary from the caller-provided scope.

    Official consumers must pass only the applicable outer-train rows.  This
    function intentionally has no validation/test-aware filtering knobs.
    """

    tokens = {
        token
        for patient in patients
        for token, _count in patient.token_counts
    }
    return CanonicalEventVocabulary(tuple(sorted(tokens)))


def summarize_event_tokens(
    patients: Iterable[PatientEventTokens],
) -> EventTokenizerAuditSummary:
    materialized = tuple(patients)
    vocabulary = build_event_vocabulary(materialized)
    return EventTokenizerAuditSummary(
        patient_count=len(materialized),
        source_event_count=sum(p.source_event_count for p in materialized),
        token_occurrence_count=sum(p.token_occurrence_count for p in materialized),
        unique_token_count=len(vocabulary.tokens),
        blank_gene_cell_count=sum(p.blank_gene_cell_count for p in materialized),
        wt_gene_cell_count=sum(p.wt_gene_cell_count for p in materialized),
        partial_event_count=sum(p.partial_event_count for p in materialized),
        unresolved_event_count=sum(p.unresolved_event_count for p in materialized),
        vocabulary_sha256=vocabulary.sha256,
    )


def tokenize_patient_event_row(
    row: Mapping[str, object],
    gene_columns: Sequence[str],
    *,
    position_bin_width: int = DEFAULT_POSITION_BIN_WIDTH,
) -> PatientEventTokens:
    """Tokenize one patient row without labels or fitted vocabulary state."""

    counts: Counter[str] = Counter()
    source_events = 0
    blank_cells = 0
    wt_cells = 0
    partial_events = 0
    unresolved_events = 0

    for gene in sorted(gene_columns):
        value = row[gene]
        if not isinstance(value, str) or not value.strip():
            blank_cells += 1
            counts[_token(gene, "provenance", "blank")] += 1
            continue
        if value.strip().upper() == "WT":
            wt_cells += 1
            continue
        canonical = parse_canonical_gene_cell(value)
        source_events += len(canonical.events)
        for routed in canonical.events:
            if routed.parse_status == "partial":
                partial_events += 1
            if routed.parse_status == "unresolved" or routed.route == "unresolved":
                unresolved_events += 1
            counts.update(
                canonical_event_tokens(
                    gene,
                    routed,
                    position_bin_width=position_bin_width,
                )
            )

    return PatientEventTokens(
        token_counts=tuple(sorted(counts.items())),
        source_event_count=source_events,
        blank_gene_cell_count=blank_cells,
        wt_gene_cell_count=wt_cells,
        partial_event_count=partial_events,
        unresolved_event_count=unresolved_events,
    )
