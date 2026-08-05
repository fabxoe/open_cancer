from __future__ import annotations

import pandas as pd

from open_cancer.range_replacement_features import (
    OrdinaryRangeReplacementGeneFamily,
    is_ordinary_range_replacement,
)


def test_ordinary_range_excludes_synonymous_and_stop_containing_subtypes() -> None:
    assert is_ordinary_range_replacement("1436_1437SI>RF")
    assert not is_ordinary_range_replacement("236_237LL>LL")
    assert not is_ordinary_range_replacement("300_301LE>F*")
    assert not is_ordinary_range_replacement("197_198YQ>**")


def test_family_fits_only_outer_train_observed_genes_and_transforms_consistently() -> None:
    train = pd.DataFrame(
        {
            "TP53": ["1436_1437SI>RF", "WT", "236_237LL>LL"],
            "EGFR": ["WT", "300_301LE>F*", "WT"],
            "KRAS": ["WT", "WT", "WT"],
        }
    )
    fitted = OrdinaryRangeReplacementGeneFamily(
        ("TP53", "EGFR", "KRAS")
    ).fit(train)
    assert fitted.selected_genes == ("TP53",)
    assert fitted.descriptor.fit_scope == "fold_train"
    assert fitted.descriptor.feature_names == (
        "gene__TP53__range_replacement_any",
    )
    transformed = fitted.transform(
        pd.DataFrame({"TP53": ["WT", "59_60HY>QH"], "EGFR": ["WT"] * 2, "KRAS": ["WT"] * 2})
    ).toarray()
    assert transformed.tolist() == [[0.0], [1.0]]
