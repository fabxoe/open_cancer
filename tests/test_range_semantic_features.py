from __future__ import annotations

import pandas as pd

from open_cancer.range_semantic_features import (
    RangeSemanticGeneFamily,
    range_semantic_type,
)


def test_range_semantics_are_disjoint_and_stop_notation_invariant() -> None:
    assert range_semantic_type("300_301LE>F*") == "range_stop"
    assert range_semantic_type("300_301LE>FX") == "range_stop"
    assert range_semantic_type("197_198YQ>**") == "range_stop"
    assert range_semantic_type("236_237LL>LL") == "range_no_change"
    assert range_semantic_type("1436_1437SI>RF") is None
    assert range_semantic_type("R213X") is None


def test_fold_train_selection_and_transform_do_not_use_other_rows() -> None:
    fold_train = pd.DataFrame(
        {
            "TP53": ["300_301LE>F*", "WT"],
            "EGFR": ["236_237LL>LL", "WT"],
            "KRAS": ["WT", "WT"],
        }
    )
    fitted = RangeSemanticGeneFamily(("TP53", "EGFR", "KRAS")).fit(fold_train)
    assert fitted.selected_gene_semantics == (
        ("TP53", "range_stop"),
        ("EGFR", "range_no_change"),
    )
    transformed = fitted.transform(
        pd.DataFrame(
            {
                "TP53": ["WT", "197_198YQ>**"],
                "EGFR": ["236_237LL>LL", "WT"],
                "KRAS": ["1436_1437SI>RF", "WT"],
            }
        )
    ).toarray()
    assert transformed.tolist() == [[0.0, 1.0], [1.0, 0.0]]
