"""Exact-duplicate-invariant adapter layered on stop notation normalization."""

from __future__ import annotations

from typing import Any

from open_cancer.mutation_features import ParsedMutationCell, ParsedMutationToken
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_token,
)


EXACT_DUPLICATE_PARSER_CONTRACT: dict[str, Any] = {
    "name": "stop_notation_exact_duplicate_invariant_v3",
    "definition_version": "3.0.0",
    "parent_contract": STOP_NOTATION_PARSER_CONTRACT,
    "equivalent_stop_alternates": ["*", "X", "Ter"],
    "deduplicate_exact_normalized_tokens": True,
    "token_order_invariant": True,
    "distinct_tokens_preserved": True,
    "target_used": False,
    "test_distribution_used_for_rule": False,
}


def parse_exact_duplicate_invariant_token(raw: str) -> ParsedMutationToken:
    """Preserve EXP-374 token semantics for pathway and hotspot families."""

    return parse_stop_notation_invariant_token(raw)


def _token_identity(token: ParsedMutationToken) -> tuple[Any, ...]:
    """Return a deterministic identity without inferring transcript meaning."""

    return (
        token.raw,
        token.mutation_type,
        token.residue_positions,
        token.reference_amino_acid,
        token.alternate_amino_acid,
        token.token_shape,
        token.is_complex,
    )


def _assemble_cell(tokens: tuple[ParsedMutationToken, ...]) -> ParsedMutationCell:
    positions = tuple(
        position for token in tokens for position in token.residue_positions
    )
    return ParsedMutationCell(
        tokens=tokens,
        token_count=len(tokens),
        residue_positions=positions,
        mutation_types=frozenset(token.mutation_type for token in tokens),
        has_complex_token=any(token.is_complex for token in tokens),
    )


def parse_exact_duplicate_invariant_cell(cell: str) -> ParsedMutationCell:
    """Normalize stop notation, remove exact duplicates, and sort tokens.

    The adapter does not merge different positions, event strings or mutation
    types. Exact duplicates introduced by ``X``/``*``/``Ter`` normalization are
    removed in the same way as duplicates already written identically.
    """

    unique: dict[tuple[Any, ...], ParsedMutationToken] = {}
    for raw in cell.split():
        if not raw or raw.upper() == "WT":
            continue
        parsed = parse_exact_duplicate_invariant_token(raw)
        unique.setdefault(_token_identity(parsed), parsed)

    tokens = tuple(unique[key] for key in sorted(unique, key=repr))
    return _assemble_cell(tokens)


def normalize_exact_duplicate_hotspot_token(raw: str) -> str:
    """Use EXP-374 token normalization; hotspot indicators are already sets."""

    return normalize_stop_notation_token(raw)


def audit_exact_duplicate_cell(cell: str) -> dict[str, int]:
    """Return target-independent cell-level impact counts for QC."""

    raw_tokens = [
        raw for raw in cell.split() if raw and raw.upper() != "WT"
    ]
    normalized = [
        parse_exact_duplicate_invariant_token(raw) for raw in raw_tokens
    ]
    raw_unique = len(set(raw_tokens))
    normalized_unique = len({_token_identity(token) for token in normalized})
    return {
        "source_tokens": len(raw_tokens),
        "raw_exact_duplicates": len(raw_tokens) - raw_unique,
        "normalized_exact_duplicates": len(raw_tokens) - normalized_unique,
        "duplicates_introduced_by_normalization": raw_unique
        - normalized_unique,
    }
