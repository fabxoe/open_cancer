"""Annotation-invariant protein mutation parsing and feature contracts.

This module is intentionally separate from ``mutation_features``.  Historical
experiments must keep the exact v1 lexical parser, while new experiments may
opt into this versioned representation after an explicit ablation.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FeatureFamilyDescriptor
from open_cancer.hashing import sha256_lines


ROBUST_PARSER_VERSION = "2.0.0"

EventFamily = Literal[
    "missense",
    "synonymous",
    "stop_gain",
    "frameshift",
    "inframe_deletion",
    "inframe_insertion",
    "delins",
    "range_replacement",
    "duplication",
    "other_unmappable",
]
ParseConfidence = Literal["high", "medium", "low"]

EVENT_FAMILIES: tuple[EventFamily, ...] = (
    "missense",
    "synonymous",
    "stop_gain",
    "frameshift",
    "inframe_deletion",
    "inframe_insertion",
    "delins",
    "range_replacement",
    "duplication",
    "other_unmappable",
)

_AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"
_SIMPLE_SUBSTITUTION = re.compile(
    rf"^([{_AMINO_ACIDS}])([1-9][0-9]*)([{_AMINO_ACIDS}*X])$",
    re.IGNORECASE,
)
_RESIDUE_POSITION = re.compile(r"[1-9][0-9]*")
_LEADING_AMINO_ACIDS = re.compile(rf"^([{_AMINO_ACIDS}*]+)", re.IGNORECASE)
_TRAILING_AMINO_ACIDS = re.compile(rf"([{_AMINO_ACIDS}*]+)$", re.IGNORECASE)


@dataclass(frozen=True)
class NormalizedMutationToken:
    """Target-independent semantic parse of one supplied protein token."""

    raw: str
    normalized: str
    event_family: EventFamily
    residue_positions: tuple[int, ...]
    reference_amino_acid: str | None
    alternate_amino_acid: str | None
    confidence: ParseConfidence
    position_eligible: bool


@dataclass(frozen=True)
class CanonicalMutationCell:
    """Order-invariant, exact-deduplicated representation of a gene cell."""

    tokens: tuple[NormalizedMutationToken, ...]
    source_token_count: int
    exact_duplicate_count: int


def _amino_acids_at_edges(raw: str) -> tuple[str | None, str | None]:
    left, separator, right = raw.partition(">")
    reference_match = _TRAILING_AMINO_ACIDS.search(left)
    alternate_match = _LEADING_AMINO_ACIDS.match(right) if separator else None
    return (
        reference_match.group(1).upper() if reference_match else None,
        alternate_match.group(1).upper() if alternate_match else None,
    )


def parse_robust_mutation_token(token: str) -> NormalizedMutationToken:
    """Parse explicit protein-event semantics without transcript inference.

    ``X`` and ``*`` are normalized to the same stop-gain meaning when written
    as the alternate residue of a simple substitution.  Indels and range
    replacements remain separate event families instead of a generic complex
    catch-all.
    """

    raw = token.strip()
    normalized = raw.upper()
    positions = tuple(int(value) for value in _RESIDUE_POSITION.findall(normalized))
    reference: str | None = None
    alternate: str | None = None
    confidence: ParseConfidence = "low"
    position_eligible = False

    substitution = _SIMPLE_SUBSTITUTION.fullmatch(normalized)
    if substitution is not None:
        reference, _, alternate = substitution.groups()
        reference = reference.upper()
        alternate = alternate.upper()
        confidence = "high"
        position_eligible = True
        if alternate == reference:
            family: EventFamily = "synonymous"
        elif alternate in {"*", "X"}:
            family = "stop_gain"
            alternate = "*"
            normalized = f"{reference}{positions[0]}*"
        else:
            family = "missense"
        return NormalizedMutationToken(
            raw=raw,
            normalized=normalized,
            event_family=family,
            residue_positions=positions,
            reference_amino_acid=reference,
            alternate_amino_acid=alternate,
            confidence=confidence,
            position_eligible=position_eligible,
        )

    lowered = normalized.lower()
    if "delins" in lowered:
        family = "delins"
        confidence = "medium"
    elif "del" in lowered:
        family = "inframe_deletion"
        confidence = "medium"
    elif "ins" in lowered:
        family = "inframe_insertion"
        confidence = "medium"
    elif "dup" in lowered:
        family = "duplication"
        confidence = "medium"
    elif "fs" in lowered:
        family = "frameshift"
        confidence = "medium"
        position_eligible = bool(positions)
    elif ">" in normalized:
        family = "range_replacement"
        confidence = "medium"
    else:
        family = "other_unmappable"

    if ">" in normalized:
        reference, alternate = _amino_acids_at_edges(normalized)
    else:
        reference_match = _LEADING_AMINO_ACIDS.match(normalized)
        reference = reference_match.group(1).upper() if reference_match else None
        alternate = None
    return NormalizedMutationToken(
        raw=raw,
        normalized=normalized,
        event_family=family,
        residue_positions=positions,
        reference_amino_acid=reference,
        alternate_amino_acid=alternate,
        confidence=confidence,
        position_eligible=position_eligible,
    )


def canonicalize_mutation_cell(cell: Any) -> CanonicalMutationCell:
    """Canonicalize whitespace, order, case, and exact duplicate tokens."""

    if not isinstance(cell, str) or not cell.strip():
        return CanonicalMutationCell(tokens=(), source_token_count=0, exact_duplicate_count=0)
    source = [
        token
        for token in cell.split()
        if token and token.upper() != "WT"
    ]
    parsed_by_normalized: dict[str, NormalizedMutationToken] = {}
    for token in source:
        parsed = parse_robust_mutation_token(token)
        parsed_by_normalized.setdefault(parsed.normalized, parsed)
    parsed = tuple(
        sorted(
            parsed_by_normalized.values(),
            key=lambda item: (
                EVENT_FAMILIES.index(item.event_family),
                item.residue_positions,
                item.normalized,
            ),
        )
    )
    return CanonicalMutationCell(
        tokens=parsed,
        source_token_count=len(source),
        exact_duplicate_count=len(source) - len(parsed),
    )


def robust_event_feature_names(
    genes: tuple[str, ...],
    *,
    include_gene_indicators: bool,
) -> tuple[str, ...]:
    """Return deterministic unique-gene count and optional gene indicator names."""

    sample = tuple(f"sample__robust_{family}_gene_count" for family in EVENT_FAMILIES)
    if not include_gene_indicators:
        return sample
    gene_features = tuple(
        f"{gene}__robust_{family}_any"
        for gene in genes
        for family in EVENT_FAMILIES
    )
    return (*sample, *gene_features)


@dataclass(frozen=True)
class FittedRobustMutationEventFamily:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    include_gene_indicators: bool

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")
        family_index = {family: index for index, family in enumerate(EVENT_FAMILIES)}
        sample_dimension = len(EVENT_FAMILIES)
        output = sparse.lil_matrix(
            (len(frame), self.descriptor.output_dimension),
            dtype=np.float32,
        )
        for row_index, row in enumerate(
            frame.loc[:, self.gene_columns].itertuples(index=False, name=None)
        ):
            sample_families: Counter[EventFamily] = Counter()
            for gene_index, cell in enumerate(row):
                canonical = canonicalize_mutation_cell(cell)
                present = {token.event_family for token in canonical.tokens}
                for family in present:
                    family_offset = family_index[family]
                    sample_families[family] += 1
                    if self.include_gene_indicators:
                        column = (
                            sample_dimension
                            + gene_index * len(EVENT_FAMILIES)
                            + family_offset
                        )
                        output[row_index, column] = 1.0
            for family, count in sample_families.items():
                output[row_index, family_index[family]] = float(count)
        return output.tocsr()


@dataclass(frozen=True)
class RobustMutationEventFamily:
    """Stateless annotation-invariant event representation for an ablation."""

    gene_columns: tuple[str, ...]
    include_gene_indicators: bool = False
    version: str = ROBUST_PARSER_VERSION

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedRobustMutationEventFamily:
        del target
        if not self.gene_columns:
            raise ValueError("유전자 열이 하나 이상 필요합니다.")
        names = robust_event_feature_names(
            self.gene_columns,
            include_gene_indicators=self.include_gene_indicators,
        )
        return FittedRobustMutationEventFamily(
            descriptor=FeatureFamilyDescriptor(
                name="annotation_invariant_mutation_events",
                version=self.version,
                fit_scope="stateless",
                feature_names=names,
            ),
            gene_columns=self.gene_columns,
            include_gene_indicators=self.include_gene_indicators,
        )


def audit_robust_mutation_parser(
    frame: pd.DataFrame,
    genes: tuple[str, ...],
) -> dict[str, Any]:
    """Return compact parser QC without retaining patient-level values."""

    family_counts: Counter[EventFamily] = Counter()
    confidence_counts: Counter[ParseConfidence] = Counter()
    source_tokens = 0
    canonical_tokens = 0
    exact_duplicates = 0
    position_eligible = 0
    for row in frame.loc[:, genes].itertuples(index=False, name=None):
        for cell in row:
            canonical = canonicalize_mutation_cell(cell)
            source_tokens += canonical.source_token_count
            canonical_tokens += len(canonical.tokens)
            exact_duplicates += canonical.exact_duplicate_count
            for token in canonical.tokens:
                family_counts[token.event_family] += 1
                confidence_counts[token.confidence] += 1
                position_eligible += int(token.position_eligible)
    contract_lines = (
        f"parser_version={ROBUST_PARSER_VERSION}",
        *(f"event_family={family}" for family in EVENT_FAMILIES),
    )
    return {
        "parser_version": ROBUST_PARSER_VERSION,
        "rows": len(frame),
        "gene_columns": len(genes),
        "source_tokens": source_tokens,
        "canonical_tokens": canonical_tokens,
        "exact_duplicates_removed": exact_duplicates,
        "position_eligible_tokens": position_eligible,
        "event_family_counts": {
            family: family_counts[family] for family in EVENT_FAMILIES
        },
        "confidence_counts": {
            confidence: confidence_counts[confidence]
            for confidence in ("high", "medium", "low")
        },
        "contract_sha256": sha256_lines(contract_lines),
    }
