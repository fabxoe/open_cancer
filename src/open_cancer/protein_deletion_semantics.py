"""Lossless protein-deletion semantics for the competition shorthand."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FeatureFamilyDescriptor
from open_cancer.hashing import sha256_lines


PROTEIN_DELETION_SEMANTICS_VERSION = "4.0.0"
PROTEIN_DELETION_SEMANTICS_CONTRACT: dict[str, Any] = {
    "name": "protein_deletion_semantics_v4",
    "definition_version": PROTEIN_DELETION_SEMANTICS_VERSION,
    "routing_precedence": ["frameshift", "delins", "deletion"],
    "range_length": "inclusive end-start+1",
    "reversed_range_policy": "unresolved_no_auto_swap",
    "equal_position_policy": "semantic_single_raw_preserved",
    "three_prime_policy": "unknown_without_fixed_reference",
    "raw_token_preserved": True,
    "target_used": False,
    "test_distribution_used_for_rule": False,
}

ParseStatus = Literal["complete", "partial", "unresolved", "not_applicable"]
ParseConfidence = Literal["exact", "partial", "unresolved", "not_applicable"]
DeletionType = Literal["single_residue", "residue_range", "unknown"]
SourceSyntax = Literal[
    "residue_aware_single",
    "position_only_single",
    "residue_aware_range",
    "position_only_range",
    "equal_position_range",
    "other",
]
ThreePrimeStatus = Literal["unknown", "not_applicable", "verified"]

_AA = "ACDEFGHIKLMNPQRSTVWY"
_RESIDUE_RANGE = re.compile(
    rf"^(?P<start_residue>[{_AA}])(?P<start>[1-9][0-9]*)_"
    rf"(?P<end_residue>[{_AA}])(?P<end>[1-9][0-9]*)DEL$",
    re.IGNORECASE,
)
_POSITION_RANGE = re.compile(
    r"^(?P<start>[1-9][0-9]*)_(?P<end>[1-9][0-9]*)DEL$",
    re.IGNORECASE,
)
_RESIDUE_SINGLE = re.compile(
    rf"^(?P<residue>[{_AA}])(?P<position>[1-9][0-9]*)DEL$",
    re.IGNORECASE,
)
_POSITION_SINGLE = re.compile(r"^(?P<position>[1-9][0-9]*)DEL$", re.IGNORECASE)


@dataclass(frozen=True)
class ProteinDeletionSemanticResult:
    raw_token: str
    normalized_token: str
    semantic_canonical_token: str | None
    parse_status: ParseStatus
    event_type: str
    deletion_type: DeletionType
    source_syntax: SourceSyntax
    start_position: int | None = None
    end_position: int | None = None
    start_residue: str | None = None
    end_residue: str | None = None
    deleted_length: int | None = None
    reference_sequence_complete: bool = False
    range_order_valid: bool | None = None
    hgvs_conformant: bool = False
    has_frameshift: bool = False
    contains_stop: bool = False
    three_prime_normalized: ThreePrimeStatus = "not_applicable"
    reference_validated: bool = False
    position_eligible: bool = False
    parse_confidence: ParseConfidence = "not_applicable"
    protein_consequence_evidence: str = "unknown"
    parser_definition_version: str = PROTEIN_DELETION_SEMANTICS_VERSION

    @property
    def is_deletion(self) -> bool:
        return self.event_type == "deletion" and self.parse_status in {
            "complete",
            "partial",
        }

    @property
    def is_position_only(self) -> bool:
        return self.source_syntax in {
            "position_only_single",
            "position_only_range",
            "equal_position_range",
        }


def _not_applicable(raw: str, normalized: str) -> ProteinDeletionSemanticResult:
    return ProteinDeletionSemanticResult(
        raw_token=raw,
        normalized_token=normalized,
        semantic_canonical_token=None,
        parse_status="not_applicable",
        event_type="other",
        deletion_type="unknown",
        source_syntax="other",
    )


def _range_result(
    *,
    raw: str,
    normalized: str,
    start: int,
    end: int,
    start_residue: str | None,
    end_residue: str | None,
) -> ProteinDeletionSemanticResult:
    residue_aware = start_residue is not None and end_residue is not None
    if end < start:
        return ProteinDeletionSemanticResult(
            raw_token=raw,
            normalized_token=normalized,
            semantic_canonical_token=None,
            parse_status="unresolved",
            event_type="deletion",
            deletion_type="residue_range",
            source_syntax=(
                "residue_aware_range" if residue_aware else "position_only_range"
            ),
            start_position=start,
            end_position=end,
            start_residue=start_residue,
            end_residue=end_residue,
            range_order_valid=False,
            position_eligible=False,
            parse_confidence="unresolved",
            three_prime_normalized="unknown",
        )

    if start == end:
        residue = start_residue if start_residue == end_residue else None
        canonical = f"{residue or ''}{start}DEL"
        return ProteinDeletionSemanticResult(
            raw_token=raw,
            normalized_token=normalized,
            semantic_canonical_token=canonical,
            parse_status="partial",
            event_type="deletion",
            deletion_type="single_residue",
            source_syntax="equal_position_range",
            start_position=start,
            end_position=end,
            start_residue=residue,
            end_residue=residue,
            deleted_length=1,
            reference_sequence_complete=residue is not None,
            range_order_valid=True,
            hgvs_conformant=False,
            three_prime_normalized="unknown",
            position_eligible=True,
            parse_confidence="partial",
        )

    canonical = (
        f"{start_residue or ''}{start}_{end_residue or ''}{end}DEL"
    )
    return ProteinDeletionSemanticResult(
        raw_token=raw,
        normalized_token=normalized,
        semantic_canonical_token=canonical,
        parse_status="complete" if residue_aware else "partial",
        event_type="deletion",
        deletion_type="residue_range",
        source_syntax="residue_aware_range" if residue_aware else "position_only_range",
        start_position=start,
        end_position=end,
        start_residue=start_residue,
        end_residue=end_residue,
        deleted_length=end - start + 1,
        # Endpoint residues do not reveal the intervening reference sequence.
        reference_sequence_complete=False,
        range_order_valid=True,
        hgvs_conformant=residue_aware,
        three_prime_normalized="unknown",
        position_eligible=True,
        parse_confidence="exact" if residue_aware else "partial",
    )


def parse_protein_deletion_token(raw_token: str) -> ProteinDeletionSemanticResult:
    """Parse complete observed deletion grammar without substring heuristics."""

    raw = raw_token.strip()
    normalized = raw.upper()

    match = _RESIDUE_RANGE.fullmatch(normalized)
    if match is not None:
        return _range_result(
            raw=raw,
            normalized=normalized,
            start=int(match.group("start")),
            end=int(match.group("end")),
            start_residue=match.group("start_residue").upper(),
            end_residue=match.group("end_residue").upper(),
        )

    match = _POSITION_RANGE.fullmatch(normalized)
    if match is not None:
        return _range_result(
            raw=raw,
            normalized=normalized,
            start=int(match.group("start")),
            end=int(match.group("end")),
            start_residue=None,
            end_residue=None,
        )

    match = _RESIDUE_SINGLE.fullmatch(normalized)
    if match is not None:
        residue = match.group("residue").upper()
        position = int(match.group("position"))
        canonical = f"{residue}{position}DEL"
        return ProteinDeletionSemanticResult(
            raw_token=raw,
            normalized_token=canonical,
            semantic_canonical_token=canonical,
            parse_status="complete",
            event_type="deletion",
            deletion_type="single_residue",
            source_syntax="residue_aware_single",
            start_position=position,
            end_position=position,
            start_residue=residue,
            end_residue=residue,
            deleted_length=1,
            reference_sequence_complete=True,
            range_order_valid=True,
            hgvs_conformant=True,
            three_prime_normalized="unknown",
            position_eligible=True,
            parse_confidence="exact",
        )

    match = _POSITION_SINGLE.fullmatch(normalized)
    if match is not None:
        position = int(match.group("position"))
        canonical = f"{position}DEL"
        return ProteinDeletionSemanticResult(
            raw_token=raw,
            normalized_token=canonical,
            semantic_canonical_token=canonical,
            parse_status="partial",
            event_type="deletion",
            deletion_type="single_residue",
            source_syntax="position_only_single",
            start_position=position,
            end_position=position,
            deleted_length=1,
            reference_sequence_complete=False,
            range_order_valid=True,
            hgvs_conformant=False,
            three_prime_normalized="unknown",
            position_eligible=True,
            parse_confidence="partial",
        )

    return _not_applicable(raw, normalized)


DELETION_FEATURE_NAMES = (
    "deletion",
    "single_deletion",
    "range_deletion",
    "position_only_deletion",
)


def deletion_semantic_feature_names(
    genes: tuple[str, ...],
    *,
    include_gene_features: bool,
) -> tuple[str, ...]:
    sample = (
        "sample__deletion_token_count",
        "sample__deletion_gene_count",
        "sample__single_deletion_gene_count",
        "sample__range_deletion_gene_count",
        "sample__position_only_deletion_gene_count",
        "sample__deleted_length_sum",
        "sample__deleted_length_max",
        "sample__deleted_length_log1p_sum",
    )
    if not include_gene_features:
        return sample
    gene = tuple(
        name
        for symbol in genes
        for name in (
            f"{symbol}__deletion_any",
            f"{symbol}__deletion_count",
            f"{symbol}__single_deletion_any",
            f"{symbol}__single_deletion_count",
            f"{symbol}__range_deletion_any",
            f"{symbol}__range_deletion_count",
            f"{symbol}__position_only_deletion_any",
            f"{symbol}__position_only_deletion_count",
            f"{symbol}__deleted_length_sum",
            f"{symbol}__deleted_length_max",
            f"{symbol}__deleted_length_log1p_sum",
        )
    )
    return (*sample, *gene)


@dataclass(frozen=True)
class FittedProteinDeletionSemanticFamily:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    include_gene_features: bool

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")
        output = sparse.lil_matrix(
            (len(frame), self.descriptor.output_dimension), dtype=np.float32
        )
        sample_width = 8
        gene_width = 11
        for row_index, row in enumerate(
            frame.loc[:, self.gene_columns].itertuples(index=False, name=None)
        ):
            total_tokens = 0
            total_genes = 0
            single_genes = 0
            range_genes = 0
            position_only_genes = 0
            sample_lengths: list[int] = []
            for gene_index, cell in enumerate(row):
                parsed = []
                if isinstance(cell, str):
                    parsed = [
                        result
                        for token in cell.split()
                        if token and token.upper() != "WT"
                        and (result := parse_protein_deletion_token(token)).is_deletion
                    ]
                if not parsed:
                    continue
                total_genes += 1
                total_tokens += len(parsed)
                singles = sum(item.deletion_type == "single_residue" for item in parsed)
                ranges = sum(item.deletion_type == "residue_range" for item in parsed)
                position_only = sum(item.is_position_only for item in parsed)
                single_genes += int(singles > 0)
                range_genes += int(ranges > 0)
                position_only_genes += int(position_only > 0)
                lengths = [item.deleted_length for item in parsed if item.deleted_length is not None]
                sample_lengths.extend(lengths)
                if self.include_gene_features:
                    offset = sample_width + gene_index * gene_width
                    values = (
                        1,
                        len(parsed),
                        int(singles > 0),
                        singles,
                        int(ranges > 0),
                        ranges,
                        int(position_only > 0),
                        position_only,
                        sum(lengths),
                        max(lengths, default=0),
                        sum(math.log1p(value) for value in lengths),
                    )
                    for index, value in enumerate(values):
                        if value:
                            output[row_index, offset + index] = float(value)
            sample_values = (
                total_tokens,
                total_genes,
                single_genes,
                range_genes,
                position_only_genes,
                sum(sample_lengths),
                max(sample_lengths, default=0),
                sum(math.log1p(value) for value in sample_lengths),
            )
            for index, value in enumerate(sample_values):
                if value:
                    output[row_index, index] = float(value)
        return output.tocsr()


@dataclass(frozen=True)
class ProteinDeletionSemanticFamily:
    gene_columns: tuple[str, ...]
    include_gene_features: bool = False
    version: str = PROTEIN_DELETION_SEMANTICS_VERSION

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedProteinDeletionSemanticFamily:
        del target
        if not self.gene_columns:
            raise ValueError("유전자 열이 하나 이상 필요합니다.")
        names = deletion_semantic_feature_names(
            self.gene_columns, include_gene_features=self.include_gene_features
        )
        return FittedProteinDeletionSemanticFamily(
            descriptor=FeatureFamilyDescriptor(
                name="protein_deletion_semantics",
                version=self.version,
                fit_scope="stateless",
                feature_names=names,
            ),
            gene_columns=self.gene_columns,
            include_gene_features=self.include_gene_features,
        )


def audit_protein_deletion_semantics(
    frame: pd.DataFrame,
    genes: tuple[str, ...],
) -> dict[str, Any]:
    syntax_counts: Counter[str] = Counter()
    unique_tokens: set[str] = set()
    affected_genes: set[str] = set()
    affected_samples: set[int] = set()
    deletion_lengths: list[int] = []
    examples: dict[str, list[str]] = {}
    delins_tokens = 0
    frameshift_del_substring_tokens = 0
    unsupported_del_substring_tokens = 0
    reversed_range_tokens = 0

    for row_index, row in enumerate(
        frame.loc[:, genes].itertuples(index=False, name=None)
    ):
        for gene, cell in zip(genes, row, strict=True):
            if not isinstance(cell, str):
                continue
            for raw in cell.split():
                if not raw or raw.upper() == "WT":
                    continue
                normalized = raw.upper()
                parsed = parse_protein_deletion_token(raw)
                if parsed.is_deletion:
                    syntax_counts[parsed.source_syntax] += 1
                    unique_tokens.add(parsed.normalized_token)
                    affected_genes.add(gene)
                    affected_samples.add(row_index)
                    if parsed.deleted_length is not None:
                        deletion_lengths.append(parsed.deleted_length)
                    bucket = examples.setdefault(parsed.source_syntax, [])
                    if len(bucket) < 20 and raw not in bucket:
                        bucket.append(raw)
                elif parsed.event_type == "deletion" and parsed.range_order_valid is False:
                    reversed_range_tokens += 1
                elif "DELINS" in normalized:
                    delins_tokens += 1
                elif normalized.endswith("FS") and "DEL" in normalized:
                    frameshift_del_substring_tokens += 1
                elif "DEL" in normalized:
                    unsupported_del_substring_tokens += 1

    length_array = np.asarray(deletion_lengths, dtype=np.int64)
    quantiles = {}
    if len(length_array):
        quantiles = {
            "min": int(length_array.min()),
            "p50": float(np.quantile(length_array, 0.50)),
            "p90": float(np.quantile(length_array, 0.90)),
            "p99": float(np.quantile(length_array, 0.99)),
            "max": int(length_array.max()),
        }
    contract_lines = (
        f"parser_version={PROTEIN_DELETION_SEMANTICS_VERSION}",
        "routing=frameshift>delins>deletion",
        "length=end-start+1",
        "reversed=no_auto_swap",
        "equal_range=semantic_single_raw_preserved",
        "three_prime=unknown_without_reference",
    )
    ordered_syntax = (
        "residue_aware_single",
        "position_only_single",
        "residue_aware_range",
        "position_only_range",
        "equal_position_range",
    )
    return {
        "parser_version": PROTEIN_DELETION_SEMANTICS_VERSION,
        "rows": len(frame),
        "gene_columns": len(genes),
        "deletion_occurrences": sum(syntax_counts.values()),
        "unique_normalized_deletion_tokens": len(unique_tokens),
        "affected_genes": len(affected_genes),
        "affected_samples": len(affected_samples),
        "syntax_counts": {name: syntax_counts[name] for name in ordered_syntax},
        "length_distribution": quantiles,
        "delins_routed_separately": delins_tokens,
        "frameshift_del_substring_routed_separately": frameshift_del_substring_tokens,
        "unsupported_del_substring_tokens": unsupported_del_substring_tokens,
        "reversed_range_tokens": reversed_range_tokens,
        "examples": {name: examples.get(name, []) for name in ordered_syntax},
        "semantic_contract_sha256": sha256_lines(contract_lines),
    }
