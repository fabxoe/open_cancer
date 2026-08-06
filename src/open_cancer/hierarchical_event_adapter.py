"""Fold-safe sparse adapter for parser-v4 canonical patient event tokens.

The adapter keeps supported gene-specific detail while also projecting every
semantic token into a small gene-agnostic namespace.  A detail token that is
unseen in validation/test can therefore fall back only to meaning already
observed in the outer-train scope; no test-only coefficient is invented.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Literal

import numpy as np
from scipy import sparse

from open_cancer.canonical_event_tokenizer import PatientEventTokens
from open_cancer.event_token_audit import token_document_frequency


HIERARCHICAL_EVENT_ADAPTER_VERSION = "1.0.0"
Normalization = Literal["raw", "row_l2"]


def _split_detail_token(token: str) -> tuple[str, str]:
    if not token.startswith("gene=") or "|" not in token:
        raise ValueError(f"invalid canonical detail token: {token!r}")
    _gene, semantic = token.split("|", 1)
    if "=" not in semantic:
        raise ValueError(f"invalid canonical semantic token: {token!r}")
    return semantic.split("=", 1)


def _route_group(family: str) -> str:
    if family.startswith("substitution:"):
        return "substitution"
    if family in {"deletion", "insertion", "duplication_candidate", "delins"}:
        return "inframe_structural"
    if family.startswith("range_") or family == "range_replacement":
        return "range"
    if family == "frameshift":
        return "frameshift"
    if family == "unresolved":
        return "unresolved"
    return "other"


def global_token_projections(detail_token: str) -> tuple[str, ...]:
    """Return bounded gene-agnostic fallbacks for one canonical detail token."""

    key, value = _split_detail_token(detail_token)
    projected = [f"global|{key}={value}"]
    if key == "family":
        projected.append(f"global|route_group={_route_group(value)}")
    return tuple(projected)


def _global_counts(patient: PatientEventTokens) -> Counter[str]:
    counts: Counter[str] = Counter()
    for detail_token, count in patient.token_counts:
        for token in global_token_projections(detail_token):
            counts[token] += count
    return counts


def _global_document_frequency(
    patients: Iterable[PatientEventTokens],
) -> Counter[str]:
    frequencies: Counter[str] = Counter()
    for patient in patients:
        frequencies.update(_global_counts(patient).keys())
    return frequencies


@dataclass(frozen=True)
class HierarchicalOovAudit:
    patient_count: int
    detail_occurrences: int
    detail_oov_occurrences: int
    detail_oov_rate: float
    detail_oov_recovered_occurrences: int
    detail_oov_recovery_rate: float
    unrecovered_detail_occurrences: int
    patients_with_detail_oov: int
    patients_with_unrecovered_detail: int
    global_occurrences: int
    global_oov_occurrences: int
    global_oov_rate: float


@dataclass(frozen=True)
class FittedHierarchicalEventAdapter:
    detail_tokens: tuple[str, ...]
    global_tokens: tuple[str, ...]
    detail_minimum_support: int
    global_minimum_support: int
    normalization: Normalization
    version: str = HIERARCHICAL_EVENT_ADAPTER_VERSION

    @property
    def feature_names(self) -> tuple[str, ...]:
        return tuple(f"detail|{token}" for token in self.detail_tokens) + self.global_tokens

    @property
    def output_dimension(self) -> int:
        return len(self.detail_tokens) + len(self.global_tokens)

    @property
    def feature_sha256(self) -> str:
        encoded = json.dumps(
            self.feature_names,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @property
    def adapter_sha256(self) -> str:
        encoded = json.dumps(
            {
                "version": self.version,
                "detail_minimum_support": self.detail_minimum_support,
                "global_minimum_support": self.global_minimum_support,
                "normalization": self.normalization,
                "feature_sha256": self.feature_sha256,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def transform(
        self, patients: Iterable[PatientEventTokens]
    ) -> sparse.csr_matrix:
        materialized = tuple(patients)
        detail_index = {token: i for i, token in enumerate(self.detail_tokens)}
        global_offset = len(detail_index)
        global_index = {
            token: global_offset + i for i, token in enumerate(self.global_tokens)
        }
        rows: list[int] = []
        columns: list[int] = []
        values: list[float] = []
        for row_index, patient in enumerate(materialized):
            for token, count in patient.token_counts:
                column = detail_index.get(token)
                if column is not None:
                    rows.append(row_index)
                    columns.append(column)
                    values.append(float(count))
            for token, count in _global_counts(patient).items():
                column = global_index.get(token)
                if column is not None:
                    rows.append(row_index)
                    columns.append(column)
                    values.append(float(count))
        matrix = sparse.csr_matrix(
            (np.asarray(values, dtype=np.float32), (rows, columns)),
            shape=(len(materialized), self.output_dimension),
            dtype=np.float32,
        )
        matrix.sum_duplicates()
        if self.normalization == "row_l2":
            norms = np.sqrt(matrix.multiply(matrix).sum(axis=1)).A1
            inverse = np.zeros_like(norms, dtype=np.float32)
            nonzero = norms > 0
            inverse[nonzero] = 1.0 / norms[nonzero]
            matrix = sparse.diags(inverse, format="csr") @ matrix
        return matrix.tocsr()

    def audit(
        self, patients: Iterable[PatientEventTokens]
    ) -> HierarchicalOovAudit:
        materialized = tuple(patients)
        detail_vocabulary = frozenset(self.detail_tokens)
        global_vocabulary = frozenset(self.global_tokens)
        detail_total = detail_oov = recovered = 0
        global_total = global_oov = 0
        patients_detail_oov = patients_unrecovered = 0

        for patient in materialized:
            patient_detail_oov = False
            patient_unrecovered = False
            for token, count in patient.token_counts:
                detail_total += count
                projections = global_token_projections(token)
                known_projection = any(p in global_vocabulary for p in projections)
                if token not in detail_vocabulary:
                    detail_oov += count
                    patient_detail_oov = True
                    if known_projection:
                        recovered += count
                    else:
                        patient_unrecovered = True
                for projection in projections:
                    global_total += count
                    if projection not in global_vocabulary:
                        global_oov += count
            patients_detail_oov += int(patient_detail_oov)
            patients_unrecovered += int(patient_unrecovered)

        return HierarchicalOovAudit(
            patient_count=len(materialized),
            detail_occurrences=detail_total,
            detail_oov_occurrences=detail_oov,
            detail_oov_rate=(detail_oov / detail_total if detail_total else 0.0),
            detail_oov_recovered_occurrences=recovered,
            detail_oov_recovery_rate=(recovered / detail_oov if detail_oov else 1.0),
            unrecovered_detail_occurrences=detail_oov - recovered,
            patients_with_detail_oov=patients_detail_oov,
            patients_with_unrecovered_detail=patients_unrecovered,
            global_occurrences=global_total,
            global_oov_occurrences=global_oov,
            global_oov_rate=(global_oov / global_total if global_total else 0.0),
        )


def fit_hierarchical_event_adapter(
    train_patients: Iterable[PatientEventTokens],
    *,
    detail_minimum_support: int = 2,
    global_minimum_support: int = 1,
    normalization: Normalization = "raw",
) -> FittedHierarchicalEventAdapter:
    """Fit vocabularies from the explicitly supplied training scope only."""

    if detail_minimum_support < 1 or global_minimum_support < 1:
        raise ValueError("minimum support must be positive")
    if normalization not in {"raw", "row_l2"}:
        raise ValueError(f"unsupported normalization: {normalization}")
    materialized = tuple(train_patients)
    detail_df = token_document_frequency(materialized)
    global_df = _global_document_frequency(materialized)
    return FittedHierarchicalEventAdapter(
        detail_tokens=tuple(sorted(
            token for token, count in detail_df.items()
            if count >= detail_minimum_support
        )),
        global_tokens=tuple(sorted(
            token for token, count in global_df.items()
            if count >= global_minimum_support
        )),
        detail_minimum_support=detail_minimum_support,
        global_minimum_support=global_minimum_support,
        normalization=normalization,
    )
