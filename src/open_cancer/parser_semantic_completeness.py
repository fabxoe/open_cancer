"""Deterministic completeness audit for the parser-v4 semantic contract."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from open_cancer.mutation_features import classify_mutation_token
from open_cancer.mutation_parser_contract import (
    RoutedProteinMutation,
    route_protein_mutation,
)
from open_cancer.parser_support_gate import support_family_key


PARSER_SEMANTIC_AUDIT_VERSION = "1.0.0"
SEMANTIC_FIELD_NAMES = (
    "positions", "reference", "alternate", "range_endpoints", "length",
    "stop_semantics", "hgvs_conformance", "position_eligibility",
)


def semantic_family_key(routed: RoutedProteinMutation) -> tuple[str, str]:
    """Return the stable primary family key used by the support audit."""

    return support_family_key(
        route=routed.route,
        event_type=routed.event_type,
        payload=routed.payload,
    )


def semantic_subfamily_key(routed: RoutedProteinMutation) -> str:
    """Describe source grammar without inventing unavailable biology."""

    payload = routed.payload
    if routed.route == "frameshift":
        return str(payload.get("grammar", "unknown"))
    if routed.route == "deletion":
        return ":".join(
            str(payload.get(key, "unknown"))
            for key in ("deletion_type", "source_syntax")
        )
    if routed.route == "insertion":
        adjacency = payload.get("positions_adjacent")
        stop = bool(payload.get("contains_stop"))
        return f"adjacent={adjacency}:stop={stop}"
    if routed.route == "delins":
        if payload.get("first_stop_offset") == 0:
            stop_state = "immediate_stop"
        elif payload.get("contains_stop"):
            stop_state = "later_stop"
        else:
            stop_state = "no_stop"
        return f"{payload.get('delins_type', 'unknown')}:{stop_state}"
    if routed.route == "range_replacement":
        if payload.get("protein_no_change"):
            consequence = "no_change"
        elif payload.get("first_stop_offset") == 0:
            consequence = "immediate_stop"
        elif payload.get("contains_stop"):
            consequence = "later_stop"
        else:
            consequence = "replacement"
        return consequence
    if routed.route == "substitution":
        return routed.event_type
    return ":".join(
        str(payload.get(key, "unknown"))
        for key in ("event_family", "source_structure")
    )


def _first_present(payload: Mapping[str, Any], names: Sequence[str]) -> Any:
    for name in names:
        value = payload.get(name)
        if value is not None and value != "":
            return value
    return None


def semantic_field_presence(routed: RoutedProteinMutation) -> dict[str, bool]:
    """Return field-level observability, not truth or annotation validity."""

    payload = routed.payload
    reference = _first_present(
        payload,
        (
            "reference_residue", "reference_residue_candidate",
            "start_residue", "left_residue", "right_residue",
            "reference_amino_acid", "reference_sequence",
        ),
    )
    alternate = _first_present(
        payload,
        (
            "alternate_residue_canonical", "first_new_peptide_candidate",
            "inserted_sequence", "alternate_sequence_canonical",
            "alternate_sequence", "translated_alternate_sequence",
        ),
    )
    length_value = _first_present(
        payload,
        (
            "deleted_length", "inserted_length", "reference_span_length",
            "alternate_length_raw", "translated_alternate_length",
            "net_length_change", "duplication_length",
        ),
    )
    return {
        "positions": bool(routed.positions),
        "reference": reference is not None,
        "alternate": alternate is not None,
        "range_endpoints": (
            payload.get("start_position") is not None
            and payload.get("end_position") is not None
        ) or len(routed.positions) >= 2,
        "length": length_value is not None,
        "stop_semantics": any(
            name in payload
            for name in ("contains_stop", "immediate_stop", "first_stop_offset")
        ),
        "hgvs_conformance": "hgvs_conformant" in payload,
        "position_eligibility": "position_eligible" in payload,
    }


def semantic_sequence_lengths(routed: RoutedProteinMutation) -> dict[str, int]:
    """Return lengths already explicit in the payload or source token."""

    payload = routed.payload
    values: dict[str, int] = {}
    candidates = {
        "inserted": ("inserted_length", "inserted_sequence"),
        "alternate_raw": ("alternate_length_raw", "alternate_sequence_raw"),
        "alternate_translated": (
            "translated_alternate_length", "translated_alternate_sequence",
        ),
        "first_new_candidate": (None, "first_new_peptide_candidate"),
    }
    for label, (length_key, sequence_key) in candidates.items():
        explicit = payload.get(length_key) if length_key else None
        sequence = payload.get(sequence_key)
        if isinstance(explicit, int):
            values[label] = explicit
        elif isinstance(sequence, str):
            values[label] = len(sequence)
    return values


def _quantiles(values: Sequence[int]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "p50": None, "p90": None,
                "p99": None, "max": None}
    ordered = sorted(values)

    def select(fraction: float) -> int:
        return ordered[round((len(ordered) - 1) * fraction)]

    return {
        "count": len(ordered),
        "min": ordered[0],
        "p50": select(0.50),
        "p90": select(0.90),
        "p99": select(0.99),
        "max": ordered[-1],
    }


@dataclass
class _SupportRecord:
    occurrences: int = 0
    tokens: set[str] = field(default_factory=set)
    samples: set[str] = field(default_factory=set)
    genes: set[str] = field(default_factory=set)
    gene_cells: set[tuple[str, str]] = field(default_factory=set)
    folds: list[set[str]] = field(default_factory=lambda: [set() for _ in range(5)])
    fields: Counter[str] = field(default_factory=Counter)


@dataclass
class SemanticAuditAccumulator:
    """Streaming accumulator that never reads labels or model predictions."""

    dataset_name: str
    fold_by_id: Mapping[str, int] | None = None
    sample_count: int = 0
    non_wt_gene_cells: int = 0
    source_token_count: int = 0
    routed_token_count: int = 0
    families: dict[tuple[str, str], _SupportRecord] = field(
        default_factory=lambda: defaultdict(_SupportRecord)
    )
    subfamilies: Counter[tuple[str, str, str]] = field(default_factory=Counter)
    parse_statuses: Counter[str] = field(default_factory=Counter)
    unresolved_reasons: Counter[str] = field(default_factory=Counter)
    crosswalk: Counter[tuple[str, str, str]] = field(default_factory=Counter)
    raw_semantics: dict[str, set[tuple[str, str]]] = field(
        default_factory=lambda: defaultdict(set)
    )
    normalized_semantics: dict[str, set[tuple[str, str]]] = field(
        default_factory=lambda: defaultdict(set)
    )
    equivalence_raw: dict[tuple[str, str, str], set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )
    sequence_lengths: dict[str, list[int]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def consume_sample(
        self, *, sample_id: str, gene_cells: Iterable[tuple[str, str]]
    ) -> None:
        self.sample_count += 1
        for gene, cell in gene_cells:
            raw_cell = (cell or "").strip()
            if not raw_cell or raw_cell.upper() == "WT":
                continue
            self.non_wt_gene_cells += 1
            for raw_token in raw_cell.split():
                if not raw_token or raw_token.upper() == "WT":
                    continue
                self.source_token_count += 1
                routed = route_protein_mutation(raw_token)
                self.routed_token_count += 1
                route, event = semantic_family_key(routed)
                record = self.families[(route, event)]
                record.occurrences += 1
                record.tokens.add(raw_token)
                record.samples.add(sample_id)
                record.genes.add(gene)
                record.gene_cells.add((sample_id, gene))
                if self.fold_by_id is not None:
                    record.folds[self.fold_by_id[sample_id]].add(sample_id)
                for name, present in semantic_field_presence(routed).items():
                    if present:
                        record.fields[name] += 1
                self.subfamilies[(route, event, semantic_subfamily_key(routed))] += 1
                self.parse_statuses[routed.parse_status] += 1
                if routed.route == "unresolved" or routed.parse_status == "unresolved":
                    reason = str(
                        routed.payload.get("ambiguity_reason")
                        or routed.payload.get("event_family")
                        or routed.event_type
                    )
                    self.unresolved_reasons[reason] += 1
                legacy = classify_mutation_token(raw_token)
                self.crosswalk[(legacy, route, event)] += 1
                semantic = (route, event)
                self.raw_semantics[raw_token].add(semantic)
                self.normalized_semantics[routed.normalized_token].add(semantic)
                self.equivalence_raw[
                    (route, event, routed.normalized_token)
                ].add(raw_token)
                for label, value in semantic_sequence_lengths(routed).items():
                    self.sequence_lengths[label].append(value)

    def to_document(self) -> dict[str, Any]:
        family_rows = []
        for (route, event), record in sorted(self.families.items()):
            family_rows.append(
                {
                    "route": route,
                    "event_type": event,
                    "occurrences": record.occurrences,
                    "unique_tokens": len(record.tokens),
                    "samples": len(record.samples),
                    "genes": len(record.genes),
                    "gene_cells": len(record.gene_cells),
                    "fold_samples": [len(values) for values in record.folds],
                    "field_coverage": {
                        name: {
                            "count": record.fields[name],
                            "fraction": record.fields[name] / record.occurrences,
                        }
                        for name in SEMANTIC_FIELD_NAMES
                    },
                }
            )
        equivalence = [
            {
                "route": key[0],
                "event_type": key[1],
                "normalized_token": key[2],
                "raw_forms": sorted(forms),
            }
            for key, forms in sorted(self.equivalence_raw.items())
            if len(forms) > 1
        ]
        raw_collisions = {
            token: sorted([list(value) for value in semantics])
            for token, semantics in sorted(self.raw_semantics.items())
            if len(semantics) > 1
        }
        normalized_collisions = {
            token: sorted([list(value) for value in semantics])
            for token, semantics in sorted(self.normalized_semantics.items())
            if len(semantics) > 1
        }
        return {
            "dataset": self.dataset_name,
            "samples": self.sample_count,
            "non_wt_gene_cells": self.non_wt_gene_cells,
            "source_token_count": self.source_token_count,
            "routed_token_count": self.routed_token_count,
            "mutation_presence_preserved": (
                self.source_token_count == self.routed_token_count
            ),
            "parse_statuses": dict(sorted(self.parse_statuses.items())),
            "unresolved_reasons": dict(sorted(self.unresolved_reasons.items())),
            "families": family_rows,
            "subfamilies": [
                {
                    "route": route,
                    "event_type": event,
                    "subfamily": subfamily,
                    "occurrences": count,
                }
                for (route, event, subfamily), count in sorted(
                    self.subfamilies.items()
                )
            ],
            "legacy_crosswalk": [
                {
                    "legacy_family": legacy,
                    "route": route,
                    "event_type": event,
                    "occurrences": count,
                }
                for (legacy, route, event), count in sorted(self.crosswalk.items())
            ],
            "raw_token_semantic_collision_count": len(raw_collisions),
            "raw_token_semantic_collisions": raw_collisions,
            "normalized_semantic_collision_count": len(normalized_collisions),
            "normalized_semantic_collisions": normalized_collisions,
            "canonical_equivalence_group_count": len(equivalence),
            "canonical_equivalence_examples": equivalence[:20],
            "sequence_length_distributions": {
                label: _quantiles(values)
                for label, values in sorted(self.sequence_lengths.items())
            },
        }
