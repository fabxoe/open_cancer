"""Conservative grouping candidates for repeated protein annotations."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Hashable

from open_cancer.mutation_parser_contract import route_protein_mutation


MULTIPLICITY_GROUPER_VERSION = "1.0.0"


@dataclass(frozen=True)
class AnnotationMultiplicityGroup:
    signature: tuple[Hashable, ...]
    raw_tokens: tuple[str, ...]
    normalized_tokens: tuple[str, ...]
    annotation_count: int
    unique_position_sets: tuple[tuple[int, ...], ...]
    confidence: str
    ambiguity_reason: str


@dataclass(frozen=True)
class GeneCellMultiplicity:
    raw_tokens: tuple[str, ...]
    raw_annotation_count: int
    strict_event_count: int
    likely_event_count: int
    exact_duplicate_count: int
    likely_collapse_count: int
    likely_groups: tuple[AnnotationMultiplicityGroup, ...]
    grouper_version: str = MULTIPLICITY_GROUPER_VERSION


def _likely_signature(routed: Any) -> tuple[Hashable, ...] | None:
    payload = routed.payload
    if routed.route == "frameshift":
        reference = payload.get("reference_residue_candidate")
        first_new = payload.get("first_new_peptide_candidate")
        if reference and first_new:
            return ("frameshift", reference, first_new)
    if routed.route == "insertion":
        inserted = payload.get("inserted_sequence")
        if inserted:
            return ("insertion", inserted)
    if routed.route == "delins":
        alternate = payload.get("alternate_sequence_canonical")
        start_residue = payload.get("start_residue")
        end_residue = payload.get("end_residue")
        if alternate and start_residue and end_residue:
            return ("delins", start_residue, end_residue, alternate)
    return None


def group_gene_cell_annotations(cell: str) -> GeneCellMultiplicity:
    raw_tokens = tuple(
        token for token in cell.split() if token and token.upper() != "WT"
    )
    if not raw_tokens:
        return GeneCellMultiplicity((), 0, 0, 0, 0, 0, ())

    routed = tuple(route_protein_mutation(token) for token in raw_tokens)
    strict_keys = tuple(item.normalized_token for item in routed)
    strict_event_count = len(set(strict_keys))

    buckets: dict[tuple[Hashable, ...], list[Any]] = defaultdict(list)
    ungrouped_strict: set[str] = set()
    for item in routed:
        signature = _likely_signature(item)
        if signature is None:
            ungrouped_strict.add(item.normalized_token)
        else:
            buckets[signature].append(item)

    groups: list[AnnotationMultiplicityGroup] = []
    likely_event_count = len(ungrouped_strict)
    for signature, items in sorted(buckets.items(), key=lambda pair: repr(pair[0])):
        unique_normalized = tuple(sorted({item.normalized_token for item in items}))
        unique_positions = tuple(sorted({tuple(item.positions) for item in items}))
        likely_event_count += 1
        if len(unique_normalized) > 1 and len(unique_positions) > 1:
            groups.append(
                AnnotationMultiplicityGroup(
                    signature=signature,
                    raw_tokens=tuple(item.raw_token for item in items),
                    normalized_tokens=unique_normalized,
                    annotation_count=len(items),
                    unique_position_sets=unique_positions,
                    confidence="likely",
                    ambiguity_reason=(
                        "same gene/event/ref-alt signature at multiple protein positions; "
                        "transcript or genomic event identifier unavailable"
                    ),
                )
            )

    return GeneCellMultiplicity(
        raw_tokens=raw_tokens,
        raw_annotation_count=len(raw_tokens),
        strict_event_count=strict_event_count,
        likely_event_count=likely_event_count,
        exact_duplicate_count=len(raw_tokens) - strict_event_count,
        likely_collapse_count=strict_event_count - likely_event_count,
        likely_groups=tuple(groups),
    )
