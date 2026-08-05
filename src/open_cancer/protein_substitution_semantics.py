"""Lossless protein-substitution semantics for the competition notation.

The supplied cells use a compact one-letter protein notation rather than full
HGVS.  This module parses only grammar that is actually observed and keeps the
raw token alongside a conservative semantic interpretation.  It deliberately
does not infer transcript phase, pathogenicity, driver status, or DNA cause.
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


PROTEIN_SUBSTITUTION_SEMANTICS_VERSION = "4.0.0"

PROTEIN_SUBSTITUTION_SEMANTICS_CONTRACT: dict[str, Any] = {
    "name": "protein_substitution_semantics_v4",
    "definition_version": PROTEIN_SUBSTITUTION_SEMANTICS_VERSION,
    "equivalent_stop_alternates": ["*", "X", "Ter"],
    "start_site_policy": "M1 changes are not ordinary missense",
    "leading_x_policy": "unknown reference residue",
    "leading_stop_policy": "nonstandard unresolved",
    "physicochemical_delta_policy": "exact missense only",
    "raw_token_preserved": True,
    "target_used": False,
    "test_distribution_used_for_rule": False,
}

ParseStatus = Literal["complete", "unresolved", "not_applicable"]
ParseConfidence = Literal["exact", "unresolved", "not_applicable"]
SemanticEvent = Literal[
    "missense",
    "no_change",
    "nonsense",
    "start_codon_affected",
    "unknown_reference_substitution",
    "nonstandard_stop_reference",
    "other",
]
SubstitutionType = Literal["missense", "synonymous", "nonsense", "unknown"]

STANDARD_AMINO_ACIDS = frozenset("ACDEFGHIKLMNPQRSTVWY")
SUBSTITUTION_FEATURE_FAMILIES = (
    "missense",
    "synonymous",
    "nonsense",
    "start_codon_affected",
    "unknown_reference",
)

_SIMPLE_SUBSTITUTION = re.compile(
    r"^(?P<reference>[A-Z*])(?P<position>[1-9][0-9]*)"
    r"(?P<alternate>TER|[A-Z*])$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ProteinSubstitutionSemanticResult:
    """Conservative meaning of one compact protein token."""

    raw_token: str
    normalized_token: str
    parse_status: ParseStatus
    event_type: SemanticEvent
    substitution_type: SubstitutionType
    reference_residue: str | None = None
    position: int | None = None
    alternate_residue_raw: str | None = None
    alternate_residue_canonical: str | None = None
    protein_changed: bool | None = None
    contains_stop: bool = False
    immediate_stop: bool = False
    has_frameshift: bool = False
    start_codon_affected: bool = False
    unknown_reference_residue: bool = False
    nonstandard_reference_stop_notation: bool = False
    physicochemical_delta_eligible: bool = False
    protein_consequence_evidence: str = "unknown"
    parse_confidence: ParseConfidence = "not_applicable"
    parser_definition_version: str = PROTEIN_SUBSTITUTION_SEMANTICS_VERSION

    @property
    def feature_family(self) -> str | None:
        """Return the optional feature-adapter family without changing meaning."""

        if self.event_type == "no_change":
            return "synonymous"
        if self.event_type == "unknown_reference_substitution":
            return "unknown_reference"
        if self.event_type in {
            "missense",
            "nonsense",
            "start_codon_affected",
        }:
            return self.event_type
        return None


def _unresolved(
    raw: str,
    normalized: str,
    *,
    event_type: SemanticEvent,
    reference: str,
    position: int,
    alternate_raw: str,
    unknown_reference: bool = False,
    nonstandard_reference_stop: bool = False,
) -> ProteinSubstitutionSemanticResult:
    return ProteinSubstitutionSemanticResult(
        raw_token=raw,
        normalized_token=normalized,
        parse_status="unresolved",
        event_type=event_type,
        substitution_type="unknown",
        reference_residue=reference,
        position=position,
        alternate_residue_raw=alternate_raw,
        alternate_residue_canonical=None,
        protein_changed=None,
        unknown_reference_residue=unknown_reference,
        nonstandard_reference_stop_notation=nonstandard_reference_stop,
        parse_confidence="unresolved",
    )


def parse_protein_substitution_token(
    raw_token: str,
) -> ProteinSubstitutionSemanticResult:
    """Parse one observed compact single-position substitution token.

    Range replacements, indels and frameshifts do not match this anchored
    grammar and remain ``not_applicable`` for their dedicated parsers.
    ``X`` is a stop symbol only in alternate position; a leading ``X`` remains
    an unknown reference residue until a fixed reference validates it.
    """

    raw = raw_token.strip()
    normalized = raw.upper()
    match = _SIMPLE_SUBSTITUTION.fullmatch(normalized)
    if match is None:
        return ProteinSubstitutionSemanticResult(
            raw_token=raw,
            normalized_token=normalized,
            parse_status="not_applicable",
            event_type="other",
            substitution_type="unknown",
        )

    reference = match.group("reference").upper()
    position = int(match.group("position"))
    alternate_raw = match.group("alternate").upper()

    # A reference-side stop marker is not an ordinary amino-acid coordinate in
    # this compact dataset.  Preserve it instead of inventing stop-loss logic.
    if reference == "*":
        return _unresolved(
            raw,
            normalized,
            event_type="nonstandard_stop_reference",
            reference=reference,
            position=position,
            alternate_raw=alternate_raw,
            nonstandard_reference_stop=True,
        )
    if reference == "X":
        return _unresolved(
            raw,
            normalized,
            event_type="unknown_reference_substitution",
            reference=reference,
            position=position,
            alternate_raw=alternate_raw,
            unknown_reference=True,
        )
    if reference not in STANDARD_AMINO_ACIDS:
        return _unresolved(
            raw,
            normalized,
            event_type="other",
            reference=reference,
            position=position,
            alternate_raw=alternate_raw,
        )

    canonical_alternate = "*" if alternate_raw in {"*", "X", "TER"} else alternate_raw

    # Position 1 Met changes are translation-initiation-site annotations.  The
    # compact token cannot determine p.0, alternative initiation, or ordinary
    # residue substitution, so this precedes nonsense/missense classification.
    if reference == "M" and position == 1 and canonical_alternate != reference:
        return ProteinSubstitutionSemanticResult(
            raw_token=raw,
            normalized_token=f"M1{canonical_alternate}",
            parse_status="complete",
            event_type="start_codon_affected",
            substitution_type="unknown",
            reference_residue=reference,
            position=position,
            alternate_residue_raw=alternate_raw,
            alternate_residue_canonical=canonical_alternate,
            protein_changed=None,
            contains_stop=canonical_alternate == "*",
            immediate_stop=canonical_alternate == "*",
            start_codon_affected=True,
            parse_confidence="exact",
        )

    if canonical_alternate == "*":
        return ProteinSubstitutionSemanticResult(
            raw_token=raw,
            normalized_token=f"{reference}{position}*",
            parse_status="complete",
            event_type="nonsense",
            substitution_type="nonsense",
            reference_residue=reference,
            position=position,
            alternate_residue_raw=alternate_raw,
            alternate_residue_canonical="*",
            protein_changed=True,
            contains_stop=True,
            immediate_stop=True,
            parse_confidence="exact",
        )

    if canonical_alternate not in STANDARD_AMINO_ACIDS:
        return _unresolved(
            raw,
            normalized,
            event_type="other",
            reference=reference,
            position=position,
            alternate_raw=alternate_raw,
        )

    if reference == canonical_alternate:
        return ProteinSubstitutionSemanticResult(
            raw_token=raw,
            normalized_token=f"{reference}{position}{canonical_alternate}",
            parse_status="complete",
            event_type="no_change",
            substitution_type="synonymous",
            reference_residue=reference,
            position=position,
            alternate_residue_raw=alternate_raw,
            alternate_residue_canonical=canonical_alternate,
            protein_changed=False,
            parse_confidence="exact",
        )

    return ProteinSubstitutionSemanticResult(
        raw_token=raw,
        normalized_token=f"{reference}{position}{canonical_alternate}",
        parse_status="complete",
        event_type="missense",
        substitution_type="missense",
        reference_residue=reference,
        position=position,
        alternate_residue_raw=alternate_raw,
        alternate_residue_canonical=canonical_alternate,
        protein_changed=True,
        physicochemical_delta_eligible=True,
        parse_confidence="exact",
    )


def substitution_semantic_feature_names(
    genes: tuple[str, ...],
    *,
    include_gene_features: bool,
) -> tuple[str, ...]:
    sample_names = tuple(
        name
        for family in SUBSTITUTION_FEATURE_FAMILIES
        for name in (
            f"sample__substitution_{family}_gene_count",
            f"sample__substitution_{family}_token_count",
        )
    )
    if not include_gene_features:
        return sample_names
    gene_names = tuple(
        name
        for gene in genes
        for family in SUBSTITUTION_FEATURE_FAMILIES
        for name in (
            f"{gene}__substitution_{family}_any",
            f"{gene}__substitution_{family}_count",
        )
    )
    return (*sample_names, *gene_names)


@dataclass(frozen=True)
class FittedProteinSubstitutionSemanticFamily:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    include_gene_features: bool

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")
        family_index = {
            family: index for index, family in enumerate(SUBSTITUTION_FEATURE_FAMILIES)
        }
        sample_width = len(SUBSTITUTION_FEATURE_FAMILIES) * 2
        rows: list[int] = []
        columns: list[int] = []
        values: list[float] = []

        for row_index, row in enumerate(
            frame.loc[:, self.gene_columns].itertuples(index=False, name=None)
        ):
            sample_tokens: Counter[str] = Counter()
            sample_genes: Counter[str] = Counter()
            for gene_index, cell in enumerate(row):
                gene_tokens: Counter[str] = Counter()
                if isinstance(cell, str):
                    for raw in cell.split():
                        if not raw or raw.upper() == "WT":
                            continue
                        family = parse_protein_substitution_token(raw).feature_family
                        if family is not None:
                            gene_tokens[family] += 1
                for family, count in gene_tokens.items():
                    sample_tokens[family] += count
                    sample_genes[family] += 1
                    if self.include_gene_features:
                        offset = (
                            sample_width
                            + gene_index * len(SUBSTITUTION_FEATURE_FAMILIES) * 2
                            + family_index[family] * 2
                        )
                        rows.extend((row_index, row_index))
                        columns.extend((offset, offset + 1))
                        values.extend((1.0, float(count)))
            for family, index in family_index.items():
                if sample_genes[family]:
                    rows.append(row_index)
                    columns.append(index * 2)
                    values.append(float(sample_genes[family]))
                if sample_tokens[family]:
                    rows.append(row_index)
                    columns.append(index * 2 + 1)
                    values.append(float(sample_tokens[family]))
        return sparse.csr_matrix(
            (np.asarray(values, dtype=np.float32), (rows, columns)),
            shape=(len(frame), self.descriptor.output_dimension),
            dtype=np.float32,
        )


@dataclass(frozen=True)
class ProteinSubstitutionSemanticFamily:
    """Stateless opt-in feature adapter; not part of the frozen default spec."""

    gene_columns: tuple[str, ...]
    include_gene_features: bool = False
    version: str = PROTEIN_SUBSTITUTION_SEMANTICS_VERSION

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedProteinSubstitutionSemanticFamily:
        del target
        if not self.gene_columns:
            raise ValueError("유전자 열이 하나 이상 필요합니다.")
        names = substitution_semantic_feature_names(
            self.gene_columns,
            include_gene_features=self.include_gene_features,
        )
        return FittedProteinSubstitutionSemanticFamily(
            descriptor=FeatureFamilyDescriptor(
                name="protein_substitution_semantics",
                version=self.version,
                fit_scope="stateless",
                feature_names=names,
            ),
            gene_columns=self.gene_columns,
            include_gene_features=self.include_gene_features,
        )


def audit_protein_substitution_semantics(
    frame: pd.DataFrame,
    genes: tuple[str, ...],
) -> dict[str, Any]:
    """Return compact, patient-free vocabulary statistics."""

    event_counts: Counter[str] = Counter()
    unique_tokens: dict[str, set[str]] = {}
    affected_genes: dict[str, set[str]] = {}
    affected_samples: dict[str, set[int]] = {}
    examples: dict[str, list[str]] = {}
    source_tokens = 0
    applicable_tokens = 0
    for row_index, row in enumerate(
        frame.loc[:, genes].itertuples(index=False, name=None)
    ):
        for gene, cell in zip(genes, row, strict=True):
            if not isinstance(cell, str):
                continue
            for raw in cell.split():
                if not raw or raw.upper() == "WT":
                    continue
                source_tokens += 1
                parsed = parse_protein_substitution_token(raw)
                if parsed.parse_status == "not_applicable":
                    continue
                applicable_tokens += 1
                family = parsed.event_type
                event_counts[family] += 1
                unique_tokens.setdefault(family, set()).add(parsed.normalized_token)
                affected_genes.setdefault(family, set()).add(gene)
                affected_samples.setdefault(family, set()).add(row_index)
                bucket = examples.setdefault(family, [])
                if len(bucket) < 20 and raw not in bucket:
                    bucket.append(raw)

    ordered = (
        "missense",
        "no_change",
        "nonsense",
        "start_codon_affected",
        "unknown_reference_substitution",
        "nonstandard_stop_reference",
        "other",
    )
    contract_lines = (
        f"parser_version={PROTEIN_SUBSTITUTION_SEMANTICS_VERSION}",
        "stop_alternates=*,X,Ter",
        "start_site=M1_before_ordinary_substitution",
        "leading_X=unknown_reference",
        "leading_*=nonstandard_unresolved",
        "property_delta=exact_missense_only",
    )
    return {
        "parser_version": PROTEIN_SUBSTITUTION_SEMANTICS_VERSION,
        "rows": len(frame),
        "gene_columns": len(genes),
        "source_non_wt_tokens": source_tokens,
        "applicable_substitution_tokens": applicable_tokens,
        "event_counts": {family: event_counts[family] for family in ordered},
        "unique_normalized_token_counts": {
            family: len(unique_tokens.get(family, set())) for family in ordered
        },
        "affected_gene_counts": {
            family: len(affected_genes.get(family, set())) for family in ordered
        },
        "affected_sample_counts": {
            family: len(affected_samples.get(family, set())) for family in ordered
        },
        "examples": {family: examples.get(family, []) for family in ordered},
        "semantic_contract_sha256": sha256_lines(contract_lines),
    }
