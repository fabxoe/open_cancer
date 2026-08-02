from __future__ import annotations

import pandas as pd
import pytest

from open_cancer.correlation_audit import phi_jaccard_audit, raw_mutation_presence


def test_raw_mutation_presence_excludes_wt_and_blank_without_using_target() -> None:
    frame = pd.DataFrame(
        {
            "ID": ["a", "b", "c"],
            "SUBCLASS": ["BRCA", "BRCA", "LGG"],
            "A": ["WT", "R1H", ""],
            "B": ["K2fs", "WT", "V3E"],
        }
    )

    matrix, names = raw_mutation_presence(frame)

    assert names == ("A__mutated", "B__mutated")
    assert matrix.toarray().tolist() == [[0, 1], [1, 0], [0, 1]]


def test_phi_jaccard_audit_uses_common_selector_and_preserves_candidate_details() -> None:
    frame = pd.DataFrame(
        {
            "ID": [str(index) for index in range(6)],
            "SUBCLASS": ["BRCA"] * 6,
            "A": ["R1H", "R1H", "R1H", "WT", "WT", "WT"],
            "B": ["K2fs", "K2fs", "WT", "WT", "WT", "WT"],
        }
    )
    matrix, names = raw_mutation_presence(frame)

    result = phi_jaccard_audit(matrix, names, phi_min=0.3, jaccard_min=0.4, min_joint_count=2)

    assert result.metadata["candidate_pair_count"] == 1
    pair = result.metadata["candidate_pairs"][0]
    assert pair["left_gene"] == "A"
    assert pair["right_gene"] == "B"
    assert pair["left_prevalence"] == 3
    assert pair["right_prevalence"] == 2
    assert pair["joint_mutation_count"] == 2
    assert pair["phi"] == pytest.approx(1 / 2**0.5)
    assert pair["jaccard"] == pytest.approx(2 / 3)
