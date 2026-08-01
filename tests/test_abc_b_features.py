from __future__ import annotations

import pandas as pd
import pytest

from open_cancer.abc_b_features import (
    COMPLEX_MORPHOLOGY_FEATURES,
    FREQUENCY_TIER_FEATURES,
    ComplexMorphologyFamily,
    FrequencyTierSpectrumFamily,
    classify_complex_morphology,
)
from open_cancer.feature_family import fit_transform_family_set, transform_checked


def test_complex_morphologies_are_disjoint() -> None:
    assert classify_complex_morphology("10_11AA>Q") == "multi_position_complex"
    assert classify_complex_morphology("A12del") == "inframe_or_delins"
    assert classify_complex_morphology("UNKNOWN") == "other_complex"
    assert classify_complex_morphology("R2H") is None


def test_complex_morphology_features_use_token_denominator() -> None:
    frame = pd.DataFrame(
        {
            "ID": ["T1"],
            "G1": ["10_11AA>Q A12del UNKNOWN R2H R3R R4* R5fs"],
        }
    )
    fitted = ComplexMorphologyFamily(("G1",)).fit(frame)
    values = transform_checked(fitted, frame).toarray()[0]

    assert fitted.descriptor.feature_names == COMPLEX_MORPHOLOGY_FEATURES
    assert values[:3].tolist() == [1.0, 1.0, 1.0]
    assert values[3:6].tolist() == pytest.approx([1 / 7, 1 / 7, 1 / 7])
    assert values[6] == pytest.approx(2 / 7)
    assert values[7] == pytest.approx(3.0)


def test_frequency_tiers_are_fit_only_from_fold_train() -> None:
    fold_train = pd.DataFrame(
        {
            "ID": ["T1", "T2", "T3", "T4"],
            "G1": ["WT", "WT", "WT", "WT"],
            "G2": ["R1H", "WT", "WT", "WT"],
            "G3": ["R1H", "R2H", "WT", "WT"],
            "G4": ["R1H", "R2H", "R3H", "WT"],
        }
    )
    validation = pd.DataFrame(
        {
            "ID": ["V1"],
            "G1": ["R1H"],
            "G2": ["R1R"],
            "G3": ["R1*"],
            "G4": ["R1fs"],
        }
    )
    family = FrequencyTierSpectrumFamily(("G1", "G2", "G3", "G4"))
    fitted = family.fit(fold_train)

    assert fitted.gene_tiers == {"G1": 0, "G2": 1, "G3": 2, "G4": 3}
    assert fitted.descriptor.feature_names == FREQUENCY_TIER_FEATURES
    values = transform_checked(fitted, validation).toarray()[0]
    assert values[0] == 1
    assert values[5 + 1] == 1
    assert values[10 + 2] == 1
    assert values[15 + 3] == 1
    assert values[20] == pytest.approx(0.25)


def test_b_families_can_be_toggled_as_an_independent_set() -> None:
    frame = pd.DataFrame(
        {
            "ID": ["T1", "T2", "T3", "T4"],
            "G1": ["R1H", "WT", "R2H", "WT"],
            "G2": ["UNKNOWN", "WT", "WT", "R1R"],
            "G3": ["WT", "WT", "WT", "WT"],
            "G4": ["WT", "R1fs", "WT", "WT"],
        }
    )
    bundle = fit_transform_family_set(
        [ComplexMorphologyFamily(tuple(frame.columns[1:]))],
        fold_train=frame,
        validation=frame.iloc[:1],
        test=frame.iloc[1:2],
    )

    assert bundle.train.shape == (4, 8)
    assert set(bundle.registry) == {"complex_morphology"}
