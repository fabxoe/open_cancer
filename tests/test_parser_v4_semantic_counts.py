import numpy as np
import pandas as pd

from open_cancer.parser_v4_semantic_counts import (
    FEATURE_NAMES,
    ParserV4SemanticCountFamily,
)


def test_patient_semantic_counts_cover_all_parser_routes() -> None:
    frame = pd.DataFrame({
        "G1": ["R132H R132R R132* WQ288fs E28del E378_V380delinsD S261_P262insQE"],
        "G2": ["300_301LE>F* 236_237LL>LL"],
    })
    fitted = ParserV4SemanticCountFamily(("G1", "G2")).fit(frame)
    values = fitted.transform(frame).toarray()[0]
    counts = dict(zip(FEATURE_NAMES, values, strict=True))
    assert counts["sample__parser_v4_total_token_count"] == 9
    assert counts["sample__parser_v4_missense_count"] == 1
    assert counts["sample__parser_v4_no_change_count"] == 1
    assert counts["sample__parser_v4_nonsense_count"] == 1
    assert counts["sample__parser_v4_frameshift_count"] == 1
    assert counts["sample__parser_v4_deletion_count"] == 1
    assert counts["sample__parser_v4_delins_count"] == 1
    assert counts["sample__parser_v4_insertion_count"] == 1
    assert counts["sample__parser_v4_range_stop_count"] == 1
    assert counts["sample__parser_v4_range_no_change_count"] == 1


def test_vectorized_scan_keeps_whitespace_wt_and_row_values_stable() -> None:
    frame = pd.DataFrame(
        {
            "G1": ["WT", " wt ", "R132H", None],
            "G2": ["R132*", "", "E28del", "WQ288fs"],
        }
    )
    fitted = ParserV4SemanticCountFamily(("G1", "G2")).fit(frame)
    values = fitted.transform(frame).toarray()
    total = FEATURE_NAMES.index("sample__parser_v4_total_token_count")
    assert np.array_equal(values[:, total], np.asarray([1, 0, 2, 1]))
