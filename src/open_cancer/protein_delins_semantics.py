"""Lossless, stop-aware protein delins semantics for competition tokens."""

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


PROTEIN_DELINS_SEMANTICS_VERSION = "4.0.0"
PROTEIN_DELINS_SEMANTICS_CONTRACT: dict[str, Any] = {
    "name": "protein_delins_semantics_v4",
    "definition_version": PROTEIN_DELINS_SEMANTICS_VERSION,
    "routing_precedence": ["frameshift", "delins", "deletion", "insertion"],
    "alternate_stop_spellings": ["*", "X", "Ter"],
    "post_stop_policy": "provenance_only",
    "reference_x_policy": "unknown_reference",
    "three_prime_policy": "unknown_without_fixed_reference",
    "raw_token_preserved": True,
    "target_used": False,
    "test_distribution_used_for_rule": False,
}

ParseStatus = Literal["complete", "unresolved", "not_applicable"]
DelinsType = Literal["single_position", "residue_range", "unknown"]
PrimaryEvent = Literal["delins", "nonsense", "unresolved", "other"]

_AA_WITH_UNKNOWN = "ACDEFGHIKLMNPQRSTVWYX"
_RANGE = re.compile(
    rf"^(?P<start_residue>[{_AA_WITH_UNKNOWN}])(?P<start>[1-9][0-9]*)_"
    rf"(?P<end_residue>[{_AA_WITH_UNKNOWN}])(?P<end>[1-9][0-9]*)"
    r"DELINS(?P<alternate>[A-Z*]+)$",
    re.IGNORECASE,
)
_SINGLE = re.compile(
    rf"^(?P<residue>[{_AA_WITH_UNKNOWN}])(?P<position>[1-9][0-9]*)"
    r"DELINS(?P<alternate>[A-Z*]+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ProteinDelinsSemanticResult:
    raw_token: str
    normalized_token: str
    parse_status: ParseStatus
    source_structure: str
    primary_event: PrimaryEvent
    delins_type: DelinsType
    start_position: int | None = None
    end_position: int | None = None
    start_residue: str | None = None
    end_residue: str | None = None
    reference_span_length: int | None = None
    range_order_valid: bool | None = None
    alternate_sequence_raw: str | None = None
    alternate_sequence_canonical: str | None = None
    translated_alternate_sequence: str | None = None
    alternate_length_raw: int | None = None
    translated_alternate_length: int | None = None
    net_length_change: int | None = None
    contains_stop: bool = False
    first_stop_offset: int | None = None
    first_stop_position: int | None = None
    post_stop_sequence: str | None = None
    protein_truncating: bool = False
    unknown_reference_residue: bool = False
    reference_validated: bool = False
    three_prime_normalized: str = "not_applicable"
    position_eligible: bool = False
    parse_confidence: str = "not_applicable"
    parser_definition_version: str = PROTEIN_DELINS_SEMANTICS_VERSION

    @property
    def is_delins_syntax(self) -> bool:
        return self.source_structure == "delins"


def _canonicalize_alternate(sequence: str) -> str:
    # ``Ter`` is a three-letter stop symbol only when explicitly cased that
    # way.  Upper-case ``TER`` inside a multi-letter one-letter sequence is
    # Thr-Glu-Arg and must not be collapsed.
    canonical = sequence[:-3].upper() + "*" if sequence.endswith("Ter") else sequence.upper()
    return canonical.replace("X", "*")


def _build(
    *,
    raw: str,
    normalized_source: str,
    kind: DelinsType,
    start: int,
    end: int,
    start_residue: str,
    end_residue: str,
    alternate_raw: str,
) -> ProteinDelinsSemanticResult:
    unknown_reference = "X" in {start_residue, end_residue}
    order_valid = end >= start
    alternate = _canonicalize_alternate(alternate_raw)
    first_stop = alternate.find("*")
    contains_stop = first_stop >= 0
    translated = alternate[:first_stop] if contains_stop else alternate
    post_stop = alternate[first_stop + 1 :] if contains_stop else None
    span = end - start + 1 if order_valid else None
    parse_status: ParseStatus = (
        "complete" if order_valid and not unknown_reference else "unresolved"
    )
    if not order_valid or unknown_reference:
        primary: PrimaryEvent = "unresolved" if not (contains_stop and first_stop == 0) else "nonsense"
    elif contains_stop and first_stop == 0:
        primary = "nonsense"
    else:
        primary = "delins"
    prefix = normalized_source.split("DELINS", 1)[0]
    normalized = f"{prefix}DELINS{alternate}"
    return ProteinDelinsSemanticResult(
        raw_token=raw,
        normalized_token=normalized,
        parse_status=parse_status,
        source_structure="delins",
        primary_event=primary,
        delins_type=kind,
        start_position=start,
        end_position=end,
        start_residue=start_residue,
        end_residue=end_residue,
        reference_span_length=span,
        range_order_valid=order_valid,
        alternate_sequence_raw=alternate_raw.upper(),
        alternate_sequence_canonical=alternate,
        translated_alternate_sequence=translated,
        alternate_length_raw=len(alternate),
        translated_alternate_length=len(translated),
        net_length_change=(len(translated) - span if span is not None else None),
        contains_stop=contains_stop,
        first_stop_offset=(first_stop if contains_stop else None),
        first_stop_position=(start + first_stop if contains_stop else None),
        post_stop_sequence=post_stop,
        protein_truncating=contains_stop,
        unknown_reference_residue=unknown_reference,
        three_prime_normalized="unknown",
        position_eligible=order_valid,
        parse_confidence=("exact" if parse_status == "complete" else "unresolved"),
    )


def parse_protein_delins_token(raw_token: str) -> ProteinDelinsSemanticResult:
    raw = raw_token.strip()
    normalized = raw.upper()
    match = _RANGE.fullmatch(raw)
    if match is not None:
        return _build(
            raw=raw,
            normalized_source=normalized,
            kind="residue_range",
            start=int(match.group("start")),
            end=int(match.group("end")),
            start_residue=match.group("start_residue").upper(),
            end_residue=match.group("end_residue").upper(),
            alternate_raw=match.group("alternate"),
        )
    match = _SINGLE.fullmatch(raw)
    if match is not None:
        position = int(match.group("position"))
        residue = match.group("residue").upper()
        return _build(
            raw=raw,
            normalized_source=normalized,
            kind="single_position",
            start=position,
            end=position,
            start_residue=residue,
            end_residue=residue,
            alternate_raw=match.group("alternate"),
        )
    return ProteinDelinsSemanticResult(
        raw_token=raw,
        normalized_token=normalized,
        parse_status="not_applicable",
        source_structure="other",
        primary_event="other",
        delins_type="unknown",
    )


def delins_semantic_feature_names(
    genes: tuple[str, ...], *, include_gene_features: bool
) -> tuple[str, ...]:
    sample = (
        "sample__delins_token_count", "sample__delins_gene_count",
        "sample__delins_single_gene_count", "sample__delins_range_gene_count",
        "sample__delins_stop_gene_count", "sample__delins_unknown_reference_gene_count",
        "sample__delins_reference_span_sum", "sample__delins_reference_span_max",
        "sample__delins_translated_alt_length_sum", "sample__delins_translated_alt_length_max",
        "sample__delins_net_length_change_sum", "sample__delins_net_length_change_max_abs",
    )
    if not include_gene_features:
        return sample
    gene = tuple(
        name for symbol in genes for name in (
            f"{symbol}__delins_any", f"{symbol}__delins_count",
            f"{symbol}__delins_single_count", f"{symbol}__delins_range_count",
            f"{symbol}__delins_stop_count", f"{symbol}__delins_unknown_reference_count",
            f"{symbol}__delins_reference_span_sum", f"{symbol}__delins_reference_span_max",
            f"{symbol}__delins_translated_alt_length_sum", f"{symbol}__delins_translated_alt_length_max",
            f"{symbol}__delins_net_length_change_sum", f"{symbol}__delins_net_length_change_max_abs",
        )
    )
    return (*sample, *gene)


@dataclass(frozen=True)
class FittedProteinDelinsSemanticFamily:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    include_gene_features: bool

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")
        output = sparse.lil_matrix((len(frame), self.descriptor.output_dimension), dtype=np.float32)
        sample_width = 12
        for row_index, row in enumerate(frame.loc[:, self.gene_columns].itertuples(index=False, name=None)):
            sample = Counter()
            spans: list[int] = []
            alt_lengths: list[int] = []
            nets: list[int] = []
            for gene_index, cell in enumerate(row):
                parsed = [parse_protein_delins_token(token) for token in cell.split()] if isinstance(cell, str) else []
                parsed = [item for item in parsed if item.is_delins_syntax]
                if not parsed:
                    continue
                sample["genes"] += 1; sample["tokens"] += len(parsed)
                sample["single"] += any(x.delins_type == "single_position" for x in parsed)
                sample["range"] += any(x.delins_type == "residue_range" for x in parsed)
                sample["stop"] += any(x.contains_stop for x in parsed)
                sample["unknown"] += any(x.unknown_reference_residue for x in parsed)
                gene_spans = [x.reference_span_length for x in parsed if x.reference_span_length is not None]
                gene_alts = [x.translated_alternate_length for x in parsed if x.translated_alternate_length is not None]
                gene_nets = [x.net_length_change for x in parsed if x.net_length_change is not None]
                spans.extend(gene_spans); alt_lengths.extend(gene_alts); nets.extend(gene_nets)
                if self.include_gene_features:
                    offset = sample_width + gene_index * 12
                    values = (1, len(parsed), sum(x.delins_type == "single_position" for x in parsed),
                              sum(x.delins_type == "residue_range" for x in parsed), sum(x.contains_stop for x in parsed),
                              sum(x.unknown_reference_residue for x in parsed), sum(gene_spans), max(gene_spans, default=0),
                              sum(gene_alts), max(gene_alts, default=0), sum(gene_nets), max(map(abs, gene_nets), default=0))
                    for index, value in enumerate(values):
                        if value: output[row_index, offset + index] = float(value)
            values = (sample["tokens"], sample["genes"], sample["single"], sample["range"], sample["stop"],
                      sample["unknown"], sum(spans), max(spans, default=0), sum(alt_lengths), max(alt_lengths, default=0),
                      sum(nets), max(map(abs, nets), default=0))
            for index, value in enumerate(values):
                if value: output[row_index, index] = float(value)
        return output.tocsr()


@dataclass(frozen=True)
class ProteinDelinsSemanticFamily:
    gene_columns: tuple[str, ...]
    include_gene_features: bool = False
    version: str = PROTEIN_DELINS_SEMANTICS_VERSION

    def fit(self, train_frame: pd.DataFrame, target: pd.Series | None = None) -> FittedProteinDelinsSemanticFamily:
        del target
        names = delins_semantic_feature_names(self.gene_columns, include_gene_features=self.include_gene_features)
        return FittedProteinDelinsSemanticFamily(
            FeatureFamilyDescriptor("protein_delins_semantics", self.version, "stateless", names),
            self.gene_columns, self.include_gene_features,
        )


def audit_protein_delins_semantics(frame: pd.DataFrame, genes: tuple[str, ...]) -> dict[str, Any]:
    counts = Counter(); unique: dict[str, set[str]] = {}; affected_genes: set[str] = set(); affected_samples: set[int] = set()
    alt_lengths: list[int] = []; net_changes: list[int] = []; examples: dict[str, list[str]] = {}
    for row_index, row in enumerate(frame.loc[:, genes].itertuples(index=False, name=None)):
        for gene, cell in zip(genes, row, strict=True):
            if not isinstance(cell, str): continue
            for raw in cell.split():
                parsed = parse_protein_delins_token(raw)
                if not parsed.is_delins_syntax: continue
                syntax = "unknown_reference" if parsed.unknown_reference_residue else parsed.delins_type
                stop = "immediate_stop" if parsed.first_stop_offset == 0 else "later_stop" if parsed.contains_stop else "no_stop"
                counts[syntax] += 1; counts[stop] += 1
                unique.setdefault(syntax, set()).add(parsed.normalized_token)
                affected_genes.add(gene); affected_samples.add(row_index)
                alt_lengths.append(parsed.alternate_length_raw or 0)
                if parsed.net_length_change is not None: net_changes.append(parsed.net_length_change)
                bucket = examples.setdefault(syntax, [])
                if len(bucket) < 12 and raw not in bucket: bucket.append(raw)
    def summary(values: list[int]) -> dict[str, float | int]:
        if not values: return {}
        array = np.asarray(values)
        return {"min": int(array.min()), "p50": float(np.quantile(array,.5)), "p90": float(np.quantile(array,.9)), "max": int(array.max())}
    contract = (f"version={PROTEIN_DELINS_SEMANTICS_VERSION}", "stop=*,X,Ter", "post_stop=provenance", "frame=no_dna_inference")
    return {"parser_version": PROTEIN_DELINS_SEMANTICS_VERSION, "rows": len(frame), "gene_columns": len(genes),
            "occurrences": counts["single_position"] + counts["residue_range"] + counts["unknown_reference"],
            "syntax_counts": {key: counts[key] for key in ("single_position","residue_range","unknown_reference")},
            "stop_counts": {key: counts[key] for key in ("no_stop","immediate_stop","later_stop")},
            "unique_token_counts": {key: len(unique.get(key,set())) for key in ("single_position","residue_range","unknown_reference")},
            "affected_genes": len(affected_genes), "affected_samples": len(affected_samples),
            "alternate_length": summary(alt_lengths), "net_length_change": summary(net_changes), "examples": examples,
            "semantic_contract_sha256": sha256_lines(contract)}
