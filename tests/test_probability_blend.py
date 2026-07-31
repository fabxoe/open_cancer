from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from open_cancer.probability_blend import (
    ProbabilityBlendError,
    blend_probability_frames,
    validate_weights,
)


PROBABILITY_COLUMNS = ("PROBA_A", "PROBA_B")


def frame(first_probability: float, second_probability: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ID": ["ROW_1", "ROW_2"],
            "SUBCLASS_TRUE": ["A", "B"],
            "SUBCLASS_PRED": ["A", "B"],
            "FOLD": [0, 1],
            "PROBA_A": [first_probability, second_probability],
            "PROBA_B": [1 - first_probability, 1 - second_probability],
        }
    )


def test_fixed_probability_blend_preserves_metadata_and_averages() -> None:
    result = blend_probability_frames(
        [frame(0.8, 0.2), frame(0.6, 0.4)],
        weights=[0.5, 0.5],
        metadata_columns=("ID", "SUBCLASS_TRUE", "FOLD"),
        ignored_columns=("SUBCLASS_PRED",),
        probability_columns=PROBABILITY_COLUMNS,
    )

    assert list(result.columns) == ["ID", "SUBCLASS_TRUE", "FOLD", *PROBABILITY_COLUMNS]
    np.testing.assert_allclose(result.loc[:, PROBABILITY_COLUMNS], [[0.7, 0.3], [0.3, 0.7]])


def test_probability_blend_rejects_metadata_mismatch() -> None:
    changed = frame(0.6, 0.4)
    changed.loc[0, "FOLD"] = 2
    with pytest.raises(ProbabilityBlendError, match="메타데이터"):
        blend_probability_frames(
            [frame(0.8, 0.2), changed],
            weights=[0.5, 0.5],
            metadata_columns=("ID", "SUBCLASS_TRUE", "FOLD"),
            ignored_columns=("SUBCLASS_PRED",),
            probability_columns=PROBABILITY_COLUMNS,
        )


@pytest.mark.parametrize("weights", ([0.4, 0.4], [1.1, -0.1], [0.5]))
def test_probability_blend_rejects_invalid_weights(weights: list[float]) -> None:
    with pytest.raises(ProbabilityBlendError):
        validate_weights(weights, component_count=2)


def test_probability_blend_rejects_invalid_probability_rows() -> None:
    invalid = frame(0.6, 0.4)
    invalid.loc[0, "PROBA_B"] = 0.6
    with pytest.raises(ProbabilityBlendError, match="행 합"):
        blend_probability_frames(
            [frame(0.8, 0.2), invalid],
            weights=[0.5, 0.5],
            metadata_columns=("ID", "SUBCLASS_TRUE", "FOLD"),
            ignored_columns=("SUBCLASS_PRED",),
            probability_columns=PROBABILITY_COLUMNS,
        )
