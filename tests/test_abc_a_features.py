from __future__ import annotations

from pathlib import Path

import pandas as pd

from open_cancer.abc_a_features import (
    AMINO_ACID_FEATURES,
    AminoAcidChangeFamily,
    RecurrentExactTokenFamily,
    classify_amino_acid_change,
    load_amino_acid_properties,
)
from open_cancer.feature_family import build_family_registry, transform_checked


def test_exact_token_vocabulary_is_fit_on_train_only_and_ties_are_stable() -> None:
    train = pd.DataFrame(
        {
            "ID": ["T1", "T2", "T3"],
            "G1": ["R1H A2V", "R1H", "WT"],
            "G2": ["D3N", "WT", "D3N"],
        }
    )
    valid = pd.DataFrame(
        {
            "ID": ["V1", "V2"],
            "G1": ["R1H NEW99X", "A2V"],
            "G2": ["D3N", "WT"],
        }
    )
    fitted = RecurrentExactTokenFamily(
        gene_columns=("G1", "G2"), min_support=2, max_features=2
    ).fit(train)

    assert fitted.vocabulary == (("G1", "R1H"), ("G2", "D3N"))
    assert fitted.support == (2, 2)
    matrix = transform_checked(fitted, valid).toarray()
    assert matrix.tolist() == [[1.0, 1.0], [0.0, 0.0]]
    assert all("NEW99X" not in name for name in fitted.descriptor.feature_names)


def test_exact_token_counts_one_hit_per_sample_even_when_token_repeats() -> None:
    frame = pd.DataFrame({"ID": ["T1"], "G1": ["R1H R1H"]})
    fitted = RecurrentExactTokenFamily(
        gene_columns=("G1",), min_support=1, max_features=10
    ).fit(frame)

    assert transform_checked(fitted, frame).toarray().tolist() == [[1.0]]
    assert fitted.support == (1,)


def test_amino_acid_change_uses_fixed_property_transitions() -> None:
    root = Path(__file__).resolve().parents[1]
    property_path = root / "knowledge" / "amino_acid_properties_v1.json"
    frame = pd.DataFrame(
        {
            "ID": ["T1"],
            "G1": ["A1V D2K F3Y R4* G5G"],
            "G2": ["WT"],
        }
    )
    fitted = AminoAcidChangeFamily(
        gene_columns=("G1", "G2"), property_path=property_path
    ).fit(frame)

    assert transform_checked(fitted, frame).toarray().tolist() == [[2.0, 1.0, 1.0, 1.0]]
    assert fitted.descriptor.feature_names == AMINO_ACID_FEATURES
    assert fitted.descriptor.fit_scope == "stateless"
    assert len(fitted.descriptor.external_knowledge[0].sha256) == 64
    assert build_family_registry([fitted])["amino_acid_change"]["output_dimension"] == 4


def test_stop_gain_is_classified_but_not_duplicated_as_new_feature() -> None:
    root = Path(__file__).resolve().parents[1]
    properties = load_amino_acid_properties(
        root / "knowledge" / "amino_acid_properties_v1.json"
    )

    assert classify_amino_acid_change("R175*", properties) == "stop_gain"
    assert not any("stop" in name for name in AMINO_ACID_FEATURES)
