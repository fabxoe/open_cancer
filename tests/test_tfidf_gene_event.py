from __future__ import annotations

import numpy as np
import pytest
from scipy import sparse

from open_cancer.tfidf_gene_event import (
    build_sparse_screening_views,
    native_gene_event_indices,
)


def test_native_gene_event_indices_exclude_sample_and_non_native_columns() -> None:
    names = (
        "sample__native_v3_missense_token_count",
        "TP53__mutated",
        "gene__TP53__native_v3_missense_any",
        "gene__EGFR__native_v3_nonsense_any",
    )
    assert native_gene_event_indices(names).tolist() == [2, 3]


def test_tfidf_idf_is_fit_on_train_only_and_rows_are_l2_normalized() -> None:
    train = sparse.csr_matrix([[1, 0, 0], [1, 1, 0]], dtype=np.float32)
    validation = sparse.csr_matrix([[0, 0, 10]], dtype=np.float32)
    views = build_sparse_screening_views(train, validation)

    # Validation-only feature 2 must receive the smoothed unseen-train IDF.
    expected_unseen_idf = np.log((1 + train.shape[0]) / (1 + 0)) + 1
    assert views.idf[2] == pytest.approx(expected_unseen_idf)
    assert np.allclose(
        np.sqrt(np.asarray(views.tfidf_l2_train.power(2).sum(axis=1)).ravel()),
        1.0,
    )
    assert np.allclose(
        np.sqrt(np.asarray(views.tfidf_l2_validation.power(2).sum(axis=1)).ravel()),
        1.0,
    )
