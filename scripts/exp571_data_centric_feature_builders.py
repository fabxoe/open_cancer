"""EXP-571 data-centric feature additions on the fixed EXP-567 parent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FoldFeatureBundle
from open_cancer.hashing import sha256_lines
from open_cancer.mutation_parser_contract import route_protein_mutation
from exp527_lightgbm_ablation_builders import build_parser_plus_cosine_features


PARSER_QC_NAMES = (
    "exp571__parser_complete_ratio",
    "exp571__parser_partial_ratio",
    "exp571__parser_unresolved_ratio",
    "exp571__parser_other_status_ratio",
    "exp571__parser_unresolved_any",
)

EVENT_SPAN_NAMES = (
    "exp571__span_observed_event_count",
    "exp571__positive_span_event_count",
    "exp571__positive_span_ratio",
    "exp571__log1p_span_mean",
    "exp571__log1p_span_std",
    "exp571__log1p_span_max",
    "exp571__log1p_span_p90",
)

Arm = Literal["parser_qc", "event_span"]


def mutation_tokens(value: object) -> tuple[str, ...]:
    """Return source tokens without learning a vocabulary from any partition."""

    if value is None or pd.isna(value):
        return ()
    text = str(value).strip()
    if not text or text.upper() == "WT":
        return ()
    return tuple(token for token in text.split() if token)


def summarize_tokens(tokens: tuple[str, ...]) -> tuple[np.ndarray, np.ndarray]:
    """Create parser-QC and within-event span summaries for one gene cell."""

    status_counts = {"complete": 0, "partial": 0, "unresolved": 0, "other": 0}
    spans: list[float] = []
    for token in tokens:
        event = route_protein_mutation(token)
        status = str(event.parse_status).lower()
        if status in {"complete", "partial", "unresolved"}:
            status_counts[status] += 1
        else:
            status_counts["other"] += 1
        if event.positions:
            positions = np.asarray(event.positions, dtype=np.float64)
            spans.append(float(positions.max() - positions.min()))

    denominator = max(len(tokens), 1)
    qc = np.asarray(
        [
            status_counts["complete"] / denominator,
            status_counts["partial"] / denominator,
            status_counts["unresolved"] / denominator,
            status_counts["other"] / denominator,
            float(status_counts["unresolved"] > 0),
        ],
        dtype=np.float32,
    )
    values = np.asarray(spans, dtype=np.float64)
    positive = values[values > 0]
    span = np.asarray(
        [
            values.size,
            positive.size,
            positive.size / max(values.size, 1),
            np.log1p(values.mean()) if values.size else 0.0,
            np.log1p(values.std()) if values.size else 0.0,
            np.log1p(values.max()) if values.size else 0.0,
            np.log1p(np.quantile(values, 0.90)) if values.size else 0.0,
        ],
        dtype=np.float32,
    )
    return qc, span


def summarize_frame(
    frame: pd.DataFrame,
    gene_columns: tuple[str, ...],
) -> tuple[sparse.csr_matrix, sparse.csr_matrix]:
    """Build row-level summaries without using labels or population statistics."""

    qc_output = np.zeros((len(frame), len(PARSER_QC_NAMES)), dtype=np.float32)
    span_output = np.zeros((len(frame), len(EVENT_SPAN_NAMES)), dtype=np.float32)
    for row_position, row in enumerate(frame.loc[:, gene_columns].itertuples(index=False, name=None)):
        all_tokens = tuple(
            token
            for cell in row
            for token in mutation_tokens(cell)
        )
        qc_output[row_position], span_output[row_position] = summarize_tokens(all_tokens)
    return sparse.csr_matrix(qc_output), sparse.csr_matrix(span_output)


@dataclass(frozen=True)
class _CachedSummaries:
    train_qc: sparse.csr_matrix
    test_qc: sparse.csr_matrix
    train_span: sparse.csr_matrix
    test_span: sparse.csr_matrix


_CACHE: _CachedSummaries | None = None


class Exp571AugmentedFoldBuilder:
    """Append exactly one stateless summary family to the complete EXP-567 input."""

    def __init__(self, arm: Arm) -> None:
        global _CACHE
        self.arm = arm
        self.parent = build_parser_plus_cosine_features()
        if _CACHE is None:
            train_qc, train_span = summarize_frame(
                self.parent.train, tuple(self.parent.gene_columns)
            )
            test_qc, test_span = summarize_frame(
                self.parent.test, tuple(self.parent.gene_columns)
            )
            _CACHE = _CachedSummaries(train_qc, test_qc, train_span, test_span)
        self.cache = _CACHE

    def __call__(
        self,
        *,
        fold,
        train_indices,
        valid_indices,
        base_train,
        base_validation,
        base_test,
        base_feature_names,
        target,
    ) -> FoldFeatureBundle:
        parent = self.parent(
            fold=fold,
            train_indices=train_indices,
            valid_indices=valid_indices,
            base_train=base_train,
            base_validation=base_validation,
            base_test=base_test,
            base_feature_names=base_feature_names,
            target=target,
        )
        if self.arm == "parser_qc":
            train_extra = self.cache.train_qc[train_indices]
            valid_extra = self.cache.train_qc[valid_indices]
            test_extra = self.cache.test_qc
            names = PARSER_QC_NAMES
            family_name = "exp571_parser_status_ratios"
        else:
            train_extra = self.cache.train_span[train_indices]
            valid_extra = self.cache.train_span[valid_indices]
            test_extra = self.cache.test_span
            names = EVENT_SPAN_NAMES
            family_name = "exp571_parser_event_span_summary"

        registry = {
            **parent.registry,
            family_name: {
                "definition_version": "1.0.0",
                "enabled": True,
                "output_dimension": len(names),
                "feature_names_sha256": sha256_lines(names),
                "fit_scope": "stateless",
                "external_knowledge": None,
            },
        }
        return FoldFeatureBundle(
            train=sparse.hstack([parent.train, train_extra], format="csr", dtype=np.float32),
            validation=sparse.hstack(
                [parent.validation, valid_extra], format="csr", dtype=np.float32
            ),
            test=sparse.hstack([parent.test, test_extra], format="csr", dtype=np.float32),
            fitted_families=parent.fitted_families,
            feature_names=parent.feature_names + names,
            registry=registry,
            base_feature_names_to_drop=parent.base_feature_names_to_drop,
        )


def build_parser_qc_features() -> Exp571AugmentedFoldBuilder:
    return Exp571AugmentedFoldBuilder("parser_qc")


def build_event_span_features() -> Exp571AugmentedFoldBuilder:
    return Exp571AugmentedFoldBuilder("event_span")

