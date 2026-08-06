"""Hierarchical parser-v4 event and QC summaries for EXP-640."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.canonical_mutation_events import parse_canonical_gene_cell
from open_cancer.feature_family import FoldFeatureBundle
from open_cancer.hashing import sha256_lines
from open_cancer.parser_native_v2_features import native_v2_primary_family
from open_cancer.sparse_gene_cells import extract_non_wt_gene_cells
from exp527_lightgbm_ablation_builders import build_parser_plus_cosine_features


HIERARCHICAL_EVENT_VERSION = "1.0.0"

EVENT_FAMILIES = (
    "missense",
    "no_change",
    "stop_gain",
    "frameshift",
    "deletion",
    "insertion",
    "duplication",
    "delins_or_complex_replacement",
    "other_non_synonymous",
    "complex_or_unresolved",
)

EVENT_FEATURE_NAMES = tuple(
    f"exp640__{family}_{suffix}"
    for family in EVENT_FAMILIES
    for suffix in ("event_count", "gene_count", "event_ratio")
) + (
    "exp640__non_synonymous_event_count",
    "exp640__non_synonymous_event_ratio",
    "exp640__indel_event_count",
    "exp640__indel_event_ratio",
    "exp640__truncating_event_count",
    "exp640__truncating_event_ratio",
    "exp640__distinct_event_family_count",
)

QC_FEATURE_NAMES = (
    "exp640__parser_complete_ratio",
    "exp640__parser_partial_ratio",
    "exp640__parser_unresolved_ratio",
    "exp640__parser_other_status_ratio",
    "exp640__parser_success_rate",
    "exp640__unresolved_any",
    "exp640__unresolved_gene_count",
    "exp640__complex_gene_count",
    "exp640__multi_token_cell_count",
    "exp640__multi_token_cell_ratio",
)

Arm = Literal["event_family", "parser_qc", "combined"]


def hierarchical_event_family(event, *, gene_symbol: str) -> str:
    """Map one lossless parser-v4 event to one exclusive stable family."""

    primary = native_v2_primary_family(event, gene_symbol=gene_symbol)
    if primary == "substitution:missense":
        return "missense"
    if primary in {"substitution:no_change", "range_no_change"}:
        return "no_change"
    if primary in {"substitution:nonsense", "range_stop"}:
        return "stop_gain"
    if primary == "frameshift":
        return "frameshift"
    if primary == "deletion":
        return "deletion"
    if primary == "insertion":
        return "insertion"
    if primary == "duplication_candidate":
        return "duplication"
    if primary in {"delins", "range_replacement"}:
        return "delins_or_complex_replacement"
    if primary == "unresolved":
        return "complex_or_unresolved"
    if primary.startswith("substitution:"):
        return "other_non_synonymous"
    return "complex_or_unresolved"


def summarize_hierarchical_events(
    frame: pd.DataFrame,
    gene_columns: tuple[str, ...],
) -> tuple[sparse.csr_matrix, sparse.csr_matrix]:
    """Build row summaries without labels, fitted thresholds, or test statistics."""

    family_index = {name: index for index, name in enumerate(EVENT_FAMILIES)}
    n_rows = len(frame)
    n_families = len(EVENT_FAMILIES)
    event_counts = np.zeros((n_rows, n_families), dtype=np.float32)
    gene_counts = np.zeros((n_rows, n_families), dtype=np.float32)
    status_counts = np.zeros((n_rows, 4), dtype=np.float32)
    mutated_cell_counts = np.zeros(n_rows, dtype=np.float32)
    multi_token_cells = np.zeros(n_rows, dtype=np.float32)
    unresolved_gene_counts = np.zeros(n_rows, dtype=np.float32)
    complex_gene_counts = np.zeros(n_rows, dtype=np.float32)

    cells = extract_non_wt_gene_cells(
        frame,
        gene_columns,
        feature_version=HIERARCHICAL_EVENT_VERSION,
    )
    for row_index, gene_index, cell in zip(
        cells.row_indices, cells.gene_indices, cells.values, strict=True
    ):
        row = int(row_index)
        gene = gene_columns[int(gene_index)]
        parsed = parse_canonical_gene_cell(cell)
        mutated_cell_counts[row] += 1.0
        if len(parsed.events) > 1:
            multi_token_cells[row] += 1.0

        observed_families: set[int] = set()
        unresolved_in_gene = False
        complex_in_gene = False
        for event in parsed.events:
            family = hierarchical_event_family(event, gene_symbol=gene)
            index = family_index[family]
            event_counts[row, index] += 1.0
            observed_families.add(index)

            status = str(event.parse_status).lower()
            if status == "complete":
                status_counts[row, 0] += 1.0
            elif status == "partial":
                status_counts[row, 1] += 1.0
            elif status == "unresolved":
                status_counts[row, 2] += 1.0
            else:
                status_counts[row, 3] += 1.0

            if status == "unresolved" or family == "complex_or_unresolved":
                unresolved_in_gene = True
            if family in {
                "delins_or_complex_replacement",
                "complex_or_unresolved",
            }:
                complex_in_gene = True

        for index in observed_families:
            gene_counts[row, index] += 1.0
        unresolved_gene_counts[row] += float(unresolved_in_gene)
        complex_gene_counts[row] += float(complex_in_gene)

    total_events = event_counts.sum(axis=1)
    event_denominator = np.maximum(total_events, 1.0)
    ratios = event_counts / event_denominator[:, None]

    no_change = event_counts[:, family_index["no_change"]]
    unresolved = event_counts[:, family_index["complex_or_unresolved"]]
    non_synonymous = total_events - no_change - unresolved
    indel = sum(
        event_counts[:, family_index[name]]
        for name in (
            "deletion",
            "insertion",
            "duplication",
            "delins_or_complex_replacement",
        )
    )
    truncating = (
        event_counts[:, family_index["stop_gain"]]
        + event_counts[:, family_index["frameshift"]]
    )
    distinct = (event_counts > 0).sum(axis=1).astype(np.float32)

    interleaved = np.empty((n_rows, n_families * 3), dtype=np.float32)
    interleaved[:, 0::3] = event_counts
    interleaved[:, 1::3] = gene_counts
    interleaved[:, 2::3] = ratios
    summary = np.column_stack(
        (
            non_synonymous,
            non_synonymous / event_denominator,
            indel,
            indel / event_denominator,
            truncating,
            truncating / event_denominator,
            distinct,
        )
    ).astype(np.float32)
    event_matrix = sparse.csr_matrix(np.hstack((interleaved, summary)))

    status_denominator = np.maximum(status_counts.sum(axis=1), 1.0)
    status_ratios = status_counts / status_denominator[:, None]
    qc = np.column_stack(
        (
            status_ratios,
            status_counts[:, 0] / status_denominator,
            (status_counts[:, 2] > 0).astype(np.float32),
            unresolved_gene_counts,
            complex_gene_counts,
            multi_token_cells,
            multi_token_cells / np.maximum(mutated_cell_counts, 1.0),
        )
    ).astype(np.float32)
    return event_matrix, sparse.csr_matrix(qc)


@dataclass(frozen=True)
class _CachedFeatures:
    train_event: sparse.csr_matrix
    test_event: sparse.csr_matrix
    train_qc: sparse.csr_matrix
    test_qc: sparse.csr_matrix


_CACHE: _CachedFeatures | None = None


class Exp640AugmentedFoldBuilder:
    """Append one preregistered EXP-640 arm to the fixed EXP-567 input."""

    def __init__(self, arm: Arm) -> None:
        global _CACHE
        self.arm = arm
        self.parent = build_parser_plus_cosine_features()
        if _CACHE is None:
            train_event, train_qc = summarize_hierarchical_events(
                self.parent.train, tuple(self.parent.gene_columns)
            )
            test_event, test_qc = summarize_hierarchical_events(
                self.parent.test, tuple(self.parent.gene_columns)
            )
            _CACHE = _CachedFeatures(train_event, test_event, train_qc, test_qc)
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
        if self.arm == "event_family":
            train_extra = self.cache.train_event[train_indices]
            valid_extra = self.cache.train_event[valid_indices]
            test_extra = self.cache.test_event
            names = EVENT_FEATURE_NAMES
        elif self.arm == "parser_qc":
            train_extra = self.cache.train_qc[train_indices]
            valid_extra = self.cache.train_qc[valid_indices]
            test_extra = self.cache.test_qc
            names = QC_FEATURE_NAMES
        else:
            train_extra = sparse.hstack(
                [self.cache.train_event[train_indices], self.cache.train_qc[train_indices]],
                format="csr",
            )
            valid_extra = sparse.hstack(
                [self.cache.train_event[valid_indices], self.cache.train_qc[valid_indices]],
                format="csr",
            )
            test_extra = sparse.hstack(
                [self.cache.test_event, self.cache.test_qc], format="csr"
            )
            names = EVENT_FEATURE_NAMES + QC_FEATURE_NAMES

        family_name = f"exp640_{self.arm}"
        registry = {
            **parent.registry,
            family_name: {
                "definition_version": HIERARCHICAL_EVENT_VERSION,
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


def build_event_family_features() -> Exp640AugmentedFoldBuilder:
    return Exp640AugmentedFoldBuilder("event_family")


def build_parser_qc_features() -> Exp640AugmentedFoldBuilder:
    return Exp640AugmentedFoldBuilder("parser_qc")


def build_combined_features() -> Exp640AugmentedFoldBuilder:
    return Exp640AugmentedFoldBuilder("combined")
