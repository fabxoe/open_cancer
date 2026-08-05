from __future__ import annotations

import pandas as pd
from scipy import sparse

from open_cancer.range_replacement_features import (
    OrdinaryRangeReplacementGeneFamily,
)


def test_fold_train_selection_does_not_use_validation_or_test() -> None:
    fold_train = pd.DataFrame(
        {"TP53": ["10_11AA>RF", "WT"], "EGFR": ["WT", "WT"]}
    )
    validation = pd.DataFrame(
        {"TP53": ["WT"], "EGFR": ["20_21AA>RF"]}
    )
    fitted = OrdinaryRangeReplacementGeneFamily(("TP53", "EGFR")).fit(
        fold_train
    )
    assert fitted.selected_genes == ("TP53",)
    assert sparse.isspmatrix_csr(fitted.transform(validation))
    assert fitted.transform(validation).shape == (1, 1)


def test_stop_containing_range_does_not_activate_indicator() -> None:
    frame = pd.DataFrame({"TP53": ["10_11AA>RF", "10_11AA>F*"]})
    fitted = OrdinaryRangeReplacementGeneFamily(("TP53",)).fit(frame.iloc[[0]])
    assert fitted.transform(frame).toarray().tolist() == [[1.0], [0.0]]
