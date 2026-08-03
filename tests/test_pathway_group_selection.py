from __future__ import annotations

import pytest

from open_cancer.pathway_group_selection import select_recurrent_positive_groups


def test_selects_only_recurrently_positive_groups() -> None:
    records = [
        {"group": "tp53", "mean_delta": 0.02},
        {"group": "tp53", "mean_delta": 0.01},
        {"group": "tp53", "mean_delta": -0.001},
        {"group": "wnt", "mean_delta": 0.03},
        {"group": "wnt", "mean_delta": -0.02},
        {"group": "wnt", "mean_delta": -0.01},
    ]

    selected, summary = select_recurrent_positive_groups(
        records, minimum_positive_inner_folds=2
    )

    assert selected == ("tp53",)
    assert summary["tp53"]["positive_inner_folds"] == 2
    assert summary["wnt"]["mean_delta"] == pytest.approx(0.0)


def test_rejects_invalid_positive_fold_threshold() -> None:
    with pytest.raises(ValueError, match="1 이상"):
        select_recurrent_positive_groups([], minimum_positive_inner_folds=0)
