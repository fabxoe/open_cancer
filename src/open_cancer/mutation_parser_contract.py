"""Versioned parser contract and deterministic semantic router.

Historical experiments keep their recorded parser. New work may opt into this
contract explicitly; importing this module never changes the default Feature
Spec or any legacy parser.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from open_cancer.hashing import sha256_file
from open_cancer.protein_deletion_semantics import (
    PROTEIN_DELETION_SEMANTICS_VERSION,
    parse_protein_deletion_token,
)
from open_cancer.protein_delins_semantics import (
    PROTEIN_DELINS_SEMANTICS_VERSION,
    parse_protein_delins_token,
)
from open_cancer.protein_duplication_semantics import (
    PROTEIN_DUPLICATION_SEMANTICS_VERSION,
    parse_protein_insertion_token,
)
from open_cancer.protein_substitution_semantics import (
    PROTEIN_SUBSTITUTION_SEMANTICS_VERSION,
    parse_protein_substitution_token,
)
from open_cancer.robust_mutation_parser import (
    ROBUST_PARSER_VERSION,
    parse_robust_mutation_token,
)


NOTATION_NORMALIZER_VERSION = "4.0.0"
SEMANTIC_ROUTER_VERSION = "4.0.0"
FEATURE_ADAPTER_VERSION = "4.0.0-opt-in"
PARSER_FIXTURE_SCHEMA_VERSION = "1.0.0"

_REF_POSITION_FIRST_ALT_FRAMESHIFT = re.compile(
    r"^(?P<reference>[ACDEFGHIKLMNPQRSTVWY])"
    r"(?P<position>[1-9][0-9]*)"
    r"(?P<first_alternate>[ACDEFGHIKLMNPQRSTVWY])FS$",
    re.IGNORECASE,
)
_NON_PROTEIN_PARTIAL = re.compile(r"^-[1-9][0-9]*", re.IGNORECASE)
_AMBIGUOUS_DOUBLE_STOP = re.compile(r"^\*[1-9][0-9]*\*$", re.IGNORECASE)

SemanticRoute = Literal[
    "frameshift", "delins", "deletion", "insertion", "substitution",
    "range_replacement", "unresolved",
]


@dataclass(frozen=True)
class MutationParserContract:
    notation_normalizer_version: str
    semantic_parser_version: str
    feature_adapter_version: str
    fixture_catalog_sha256: str
    fixture_schema_version: str = PARSER_FIXTURE_SCHEMA_VERSION


@dataclass(frozen=True)
class RoutedProteinMutation:
    raw_token: str
    normalized_token: str
    route: SemanticRoute
    semantic_module: str
    semantic_module_version: str
    parse_status: str
    event_type: str
    positions: tuple[int, ...]
    payload: Mapping[str, Any]


def build_parser_contract(fixture_catalog_path: Path) -> MutationParserContract:
    if not fixture_catalog_path.is_file():
        raise FileNotFoundError(fixture_catalog_path)
    return MutationParserContract(
        notation_normalizer_version=NOTATION_NORMALIZER_VERSION,
        semantic_parser_version=SEMANTIC_ROUTER_VERSION,
        feature_adapter_version=FEATURE_ADAPTER_VERSION,
        fixture_catalog_sha256=sha256_file(fixture_catalog_path),
    )


def validate_resolved_parser_contract(
    value: Mapping[str, Any], *, fixture_catalog_path: Path
) -> MutationParserContract:
    """Reject missing, stale, or partially declared parser contracts."""

    required = {
        "notation_normalizer_version", "semantic_parser_version",
        "feature_adapter_version", "fixture_catalog_sha256",
        "fixture_schema_version",
    }
    missing = sorted(required - set(value))
    if missing:
        raise ValueError(f"parser_contract missing required fields: {missing}")
    expected = build_parser_contract(fixture_catalog_path)
    actual = MutationParserContract(**{key: str(value[key]) for key in required})
    if actual != expected:
        raise ValueError(
            "parser_contract does not match the repository contract: "
            f"actual={actual!r}, expected={expected!r}"
        )
    return actual


def _payload(result: Any) -> dict[str, Any]:
    return asdict(result)


def route_protein_mutation(raw_token: str) -> RoutedProteinMutation:
    """Route one token exactly once using the frozen precedence contract."""

    raw = raw_token.strip()
    robust = parse_robust_mutation_token(raw)
    if _NON_PROTEIN_PARTIAL.match(raw) or _AMBIGUOUS_DOUBLE_STOP.fullmatch(raw):
        return RoutedProteinMutation(
            raw, robust.normalized, "unresolved", "robust_mutation_parser",
            ROBUST_PARSER_VERSION, "unresolved", "other_unmappable", (),
            _payload(robust),
        )
    if robust.source_structure == "frameshift":
        return RoutedProteinMutation(
            raw, robust.normalized, "frameshift", "robust_mutation_parser",
            ROBUST_PARSER_VERSION, "complete", "frameshift",
            robust.residue_positions, _payload(robust),
        )

    # Observed compact HGVS-like form: reference + position + first new amino
    # acid + fs (for example P953Hfs).  Route the family, but keep the semantic
    # detail partial until Issue #383 validates the source annotation grammar.
    ref_alt_frameshift = _REF_POSITION_FIRST_ALT_FRAMESHIFT.fullmatch(raw)
    if ref_alt_frameshift is not None:
        position = int(ref_alt_frameshift.group("position"))
        normalized = raw.upper()
        return RoutedProteinMutation(
            raw, normalized, "frameshift", "mutation_parser_contract",
            SEMANTIC_ROUTER_VERSION, "partial", "frameshift", (position,),
            {
                "raw_token": raw,
                "normalized_token": normalized,
                "reference_residue_candidate": ref_alt_frameshift.group("reference").upper(),
                "position": position,
                "first_alternate_residue_candidate": ref_alt_frameshift.group("first_alternate").upper(),
                "ambiguity_reason": "source frameshift grammar not yet reference-validated",
            },
        )

    delins = parse_protein_delins_token(raw)
    if delins.parse_status != "not_applicable":
        positions = tuple(
            position for position in (delins.start_position, delins.end_position)
            if position is not None
        )
        return RoutedProteinMutation(
            raw, delins.normalized_token, "delins", "protein_delins_semantics",
            PROTEIN_DELINS_SEMANTICS_VERSION, delins.parse_status,
            delins.primary_event, positions, _payload(delins),
        )

    deletion = parse_protein_deletion_token(raw)
    if deletion.parse_status != "not_applicable":
        positions = tuple(
            position for position in (deletion.start_position, deletion.end_position)
            if position is not None
        )
        return RoutedProteinMutation(
            raw, deletion.normalized_token, "deletion",
            "protein_deletion_semantics", PROTEIN_DELETION_SEMANTICS_VERSION,
            deletion.parse_status, deletion.event_type, positions,
            _payload(deletion),
        )

    insertion = parse_protein_insertion_token(raw)
    if insertion.parse_status != "not_applicable":
        positions = tuple(
            position for position in (insertion.left_position, insertion.right_position)
            if position is not None
        )
        return RoutedProteinMutation(
            raw, insertion.normalized_token, "insertion",
            "protein_duplication_semantics", PROTEIN_DUPLICATION_SEMANTICS_VERSION,
            insertion.parse_status, "insertion", positions, _payload(insertion),
        )

    substitution = parse_protein_substitution_token(raw)
    if substitution.parse_status != "not_applicable":
        positions = (() if substitution.position is None else (substitution.position,))
        return RoutedProteinMutation(
            raw, substitution.normalized_token, "substitution",
            "protein_substitution_semantics", PROTEIN_SUBSTITUTION_SEMANTICS_VERSION,
            substitution.parse_status, substitution.event_type, positions,
            _payload(substitution),
        )

    if robust.source_structure == "range_replacement":
        return RoutedProteinMutation(
            raw, robust.normalized, "range_replacement", "robust_mutation_parser",
            ROBUST_PARSER_VERSION, "complete", robust.event_family,
            robust.residue_positions, _payload(robust),
        )

    return RoutedProteinMutation(
        raw, robust.normalized, "unresolved", "robust_mutation_parser",
        ROBUST_PARSER_VERSION, "unresolved", robust.event_family,
        robust.residue_positions, _payload(robust),
    )
