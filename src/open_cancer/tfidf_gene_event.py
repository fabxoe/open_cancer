"""Fold-safe sparse views for parser-native gene-event TF-IDF screening."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import sparse
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.preprocessing import Normalizer


def native_gene_event_indices(feature_names: tuple[str, ...]) -> np.ndarray:
    """Select only parser-v4 native-v3 gene-level semantic indicator columns."""

    indices = np.asarray(
        [
            index
            for index, name in enumerate(feature_names)
            if name.startswith("gene__")
            and "__native_v3_" in name
            and name.endswith("_any")
        ],
        dtype=np.int64,
    )
    if indices.size == 0:
        raise ValueError("parser-v4 native gene-event 열을 찾지 못했습니다.")
    return indices


@dataclass(frozen=True)
class SparseScreeningViews:
    raw_train: sparse.csr_matrix
    raw_validation: sparse.csr_matrix
    l2_train: sparse.csr_matrix
    l2_validation: sparse.csr_matrix
    tfidf_l2_train: sparse.csr_matrix
    tfidf_l2_validation: sparse.csr_matrix
    idf: np.ndarray


def build_sparse_screening_views(
    train: sparse.spmatrix,
    validation: sparse.spmatrix,
) -> SparseScreeningViews:
    """Build raw, row-L2 and train-fit TF-IDF+L2 views.

    The validation matrix is transform-only.  IDF is fitted exclusively on the
    supplied outer-train matrix, preventing fold leakage.
    """

    raw_train = sparse.csr_matrix(train, dtype=np.float32)
    raw_validation = sparse.csr_matrix(validation, dtype=np.float32)
    if raw_train.shape[1] != raw_validation.shape[1]:
        raise ValueError("train/validation feature dimension이 다릅니다.")

    normalizer = Normalizer(norm="l2", copy=True)
    l2_train = sparse.csr_matrix(normalizer.transform(raw_train), dtype=np.float32)
    l2_validation = sparse.csr_matrix(
        normalizer.transform(raw_validation), dtype=np.float32
    )

    transformer = TfidfTransformer(
        norm="l2",
        use_idf=True,
        smooth_idf=True,
        sublinear_tf=False,
    )
    tfidf_l2_train = sparse.csr_matrix(
        transformer.fit_transform(raw_train), dtype=np.float32
    )
    tfidf_l2_validation = sparse.csr_matrix(
        transformer.transform(raw_validation), dtype=np.float32
    )
    return SparseScreeningViews(
        raw_train=raw_train,
        raw_validation=raw_validation,
        l2_train=l2_train,
        l2_validation=l2_validation,
        tfidf_l2_train=tfidf_l2_train,
        tfidf_l2_validation=tfidf_l2_validation,
        idf=np.asarray(transformer.idf_, dtype=np.float64),
    )
