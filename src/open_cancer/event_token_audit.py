"""Label-free support and OOV summaries for canonical patient event tokens."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from open_cancer.canonical_event_tokenizer import PatientEventTokens


SUPPORT_THRESHOLDS = (1, 2, 5, 10, 20, 50)


def token_document_frequency(
    patients: Iterable[PatientEventTokens],
) -> Counter[str]:
    result: Counter[str] = Counter()
    for patient in patients:
        result.update(token for token, _count in patient.token_counts)
    return result


def vocabulary_at_support(
    document_frequency: Counter[str], minimum_support: int
) -> frozenset[str]:
    if minimum_support < 1:
        raise ValueError("minimum_support must be positive")
    return frozenset(
        token for token, count in document_frequency.items()
        if count >= minimum_support
    )


@dataclass(frozen=True)
class OovSummary:
    patient_count: int
    token_occurrences: int
    oov_occurrences: int
    oov_occurrence_rate: float
    patients_with_oov: int
    patient_oov_rate: float
    unique_tokens: int
    unique_oov_tokens: int


def summarize_oov(
    patients: Iterable[PatientEventTokens], vocabulary: frozenset[str]
) -> OovSummary:
    materialized = tuple(patients)
    total = 0
    oov = 0
    patients_with_oov = 0
    unique: set[str] = set()
    unique_oov: set[str] = set()
    for patient in materialized:
        patient_has_oov = False
        for token, count in patient.token_counts:
            unique.add(token)
            total += count
            if token not in vocabulary:
                oov += count
                unique_oov.add(token)
                patient_has_oov = True
        patients_with_oov += int(patient_has_oov)
    return OovSummary(
        patient_count=len(materialized),
        token_occurrences=total,
        oov_occurrences=oov,
        oov_occurrence_rate=(oov / total if total else 0.0),
        patients_with_oov=patients_with_oov,
        patient_oov_rate=(patients_with_oov / len(materialized) if materialized else 0.0),
        unique_tokens=len(unique),
        unique_oov_tokens=len(unique_oov),
    )


def integer_quantiles(values: Iterable[int]) -> dict[str, float | int | None]:
    array = np.asarray(tuple(values), dtype=np.int64)
    if array.size == 0:
        return {
            "count": 0, "min": None, "p50": None, "p90": None,
            "p95": None, "p99": None, "max": None,
        }
    return {
        "count": int(array.size),
        "min": int(array.min()),
        "p50": float(np.quantile(array, 0.50)),
        "p90": float(np.quantile(array, 0.90)),
        "p95": float(np.quantile(array, 0.95)),
        "p99": float(np.quantile(array, 0.99)),
        "max": int(array.max()),
    }


def token_key(token: str) -> str:
    return token.split("|", 1)[1].split("=", 1)[0]
