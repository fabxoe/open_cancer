"""EXP-611 combined Parser-v4 QC and event-span feature builder."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import sparse

from open_cancer.feature_family import FoldFeatureBundle
from open_cancer.hashing import sha256_lines
from exp527_lightgbm_ablation_builders import build_parser_plus_cosine_features
from exp571_data_centric_feature_builders import (
    EVENT_SPAN_NAMES,
    PARSER_QC_NAMES,
    summarize_frame,
)


COMBINED_FEATURE_NAMES = PARSER_QC_NAMES + EVENT_SPAN_NAMES


@dataclass(frozen=True)
class _CombinedSummaries:
    train_qc: sparse.csr_matrix
    test_qc: sparse.csr_matrix
    train_span: sparse.csr_matrix
    test_span: sparse.csr_matrix


_CACHE: _CombinedSummaries | None = None


class Exp611CombinedFoldBuilder:
    """Append both accepted stateless EXP-571 summary families."""

    def __init__(self) -> None:
        global _CACHE
        self.parent = build_parser_plus_cosine_features()
        if _CACHE is None:
            train_qc, train_span = summarize_frame(
                self.parent.train,
                tuple(self.parent.gene_columns),
            )
            test_qc, test_span = summarize_frame(
                self.parent.test,
                tuple(self.parent.gene_columns),
            )
            _CACHE = _CombinedSummaries(
                train_qc=train_qc,
                test_qc=test_qc,
                train_span=train_span,
                test_span=test_span,
            )
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
        train_extra = sparse.hstack(
            (
                self.cache.train_qc[train_indices],
                self.cache.train_span[train_indices],
            ),
            format="csr",
            dtype=np.float32,
        )
        validation_extra = sparse.hstack(
            (
                self.cache.train_qc[valid_indices],
                self.cache.train_span[valid_indices],
            ),
            format="csr",
            dtype=np.float32,
        )
        test_extra = sparse.hstack(
            (self.cache.test_qc, self.cache.test_span),
            format="csr",
            dtype=np.float32,
        )
        registry = {
            **parent.registry,
            "exp571_parser_status_ratios": {
                "definition_version": "1.0.0",
                "enabled": True,
                "output_dimension": len(PARSER_QC_NAMES),
                "feature_names_sha256": sha256_lines(PARSER_QC_NAMES),
                "fit_scope": "stateless",
                "external_knowledge": None,
            },
            "exp571_parser_event_span_summary": {
                "definition_version": "1.0.0",
                "enabled": True,
                "output_dimension": len(EVENT_SPAN_NAMES),
                "feature_names_sha256": sha256_lines(EVENT_SPAN_NAMES),
                "fit_scope": "stateless",
                "external_knowledge": None,
            },
        }
        return FoldFeatureBundle(
            train=sparse.hstack(
                (parent.train, train_extra),
                format="csr",
                dtype=np.float32,
            ),
            validation=sparse.hstack(
                (parent.validation, validation_extra),
                format="csr",
                dtype=np.float32,
            ),
            test=sparse.hstack(
                (parent.test, test_extra),
                format="csr",
                dtype=np.float32,
            ),
            fitted_families=parent.fitted_families,
            feature_names=parent.feature_names + COMBINED_FEATURE_NAMES,
            registry=registry,
            base_feature_names_to_drop=parent.base_feature_names_to_drop,
        )


def build_combined_features() -> Exp611CombinedFoldBuilder:
    return Exp611CombinedFoldBuilder()
