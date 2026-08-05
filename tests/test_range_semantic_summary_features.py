from __future__ import annotations

import pandas as pd
import pytest

from open_cancer.range_semantic_summary_features import (
    RANGE_SEMANTIC_FEATURE_NAMES,
    RangeSemanticSummaryFamily,
)


def test_range_summary_counts_unique_genes_and_keeps_stop_no_change_separate() -> None:
    frame = pd.DataFrame(
        {
            "G1": ["300_301LE>F* 2126_2127WE>*K", "236_237LL>LL", "WT"],
            "G2": ["197_198YQ>**", "236_237LL>LL", "1436_1437SI>RF"],
            "G3": ["R213*", "R132R", "SDEL133fs"],
        }
    )
    fitted = RangeSemanticSummaryFamily(("G1", "G2", "G3")).fit(frame)
    matrix = fitted.transform(frame).toarray()

    assert fitted.descriptor.feature_names == RANGE_SEMANTIC_FEATURE_NAMES
    assert matrix.tolist() == [
        [2.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 2.0, 1.0],
        [0.0, 0.0, 0.0, 0.0],
    ]


def test_range_summary_is_invariant_to_order_case_and_stop_spelling() -> None:
    frame = pd.DataFrame(
        {
            "G1": [
                "300_301LE>F* 236_237LL>LL",
                "236_237ll>ll 300_301le>fx",
                "300_301LE>FTer 236_237LL>LL",
            ]
        }
    )
    matrix = RangeSemanticSummaryFamily(("G1",)).fit(frame).transform(frame).toarray()
    assert matrix.tolist() == [[1.0, 1.0, 1.0, 1.0]] * 3


def test_range_summary_does_not_promote_non_range_stop_or_frameshift() -> None:
    frame = pd.DataFrame({"G1": ["R213*", "SDEL133fs", "721_722LA>FS"]})
    matrix = RangeSemanticSummaryFamily(("G1",)).fit(frame).transform(frame)
    assert matrix.nnz == 0


def test_range_summary_rejects_missing_gene_columns() -> None:
    frame = pd.DataFrame({"G1": ["WT"]})
    with pytest.raises(ValueError, match="유전자 열"):
        RangeSemanticSummaryFamily(("G1", "G2")).fit(frame)
