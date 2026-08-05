"""Shared parser-v4 event identity used by every new semantic consumer."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from open_cancer.mutation_parser_contract import RoutedProteinMutation, route_protein_mutation


CANONICAL_EVENT_IDENTITY_VERSION = "1.0.0"
_RAW_PAYLOAD_KEYS = {
    "raw",
    "raw_token",
    "normalized",
    "normalized_token",
    "alternate_residue_raw",
    "alternate_sequence_raw",
}


@lru_cache(maxsize=8_192)
def route_canonical_token(token: str) -> RoutedProteinMutation:
    """Route a source token through the one frozen precedence contract."""

    return route_protein_mutation(token)


def canonical_event_record(routed: RoutedProteinMutation) -> dict[str, Any]:
    """Return an alias-invariant semantic identity without raw provenance."""

    semantic_payload = {
        key: value
        for key, value in routed.payload.items()
        if key not in _RAW_PAYLOAD_KEYS
    }
    return {
        "identity_version": CANONICAL_EVENT_IDENTITY_VERSION,
        "normalized_token": routed.normalized_token,
        "route": routed.route,
        "semantic_module": routed.semantic_module,
        "semantic_module_version": routed.semantic_module_version,
        "parse_status": routed.parse_status,
        "event_type": routed.event_type,
        "positions": list(routed.positions),
        "semantic_payload": semantic_payload,
    }


def canonical_event_sha256(routed: RoutedProteinMutation) -> str:
    encoded = json.dumps(
        canonical_event_record(routed),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class CanonicalGeneCell:
    events: tuple[RoutedProteinMutation, ...]
    event_sha256: tuple[str, ...]

    @property
    def mutated(self) -> bool:
        return bool(self.events)


def parse_canonical_gene_cell(cell: object) -> CanonicalGeneCell:
    """Parse one competition cell once and retain source-token ordering."""

    if not isinstance(cell, str) or not cell.strip() or cell.strip().upper() == "WT":
        return CanonicalGeneCell((), ())
    events = tuple(
        route_canonical_token(token)
        for raw in cell.split()
        if (token := raw.strip()) and token.upper() != "WT"
    )
    return CanonicalGeneCell(
        events=events,
        event_sha256=tuple(canonical_event_sha256(event) for event in events),
    )

