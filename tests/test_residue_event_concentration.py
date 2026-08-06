from __future__ import annotations

import json

import numpy as np
import pandas as pd

from open_cancer.residue_event_concentration import (
    FEATURE_NAMES,
    ResidueEventConcentrationFamily,
    metadata_json,
)


def _frame(g1: list[str], g2: list[str] | None = None) -> pd.DataFrame:
    values: dict[str, list[str]] = {"G1": g1}
    if g2 is not None:
        values["G2"] = g2
    return pd.DataFrame(values)


def test_fit_deduplicates_patient_gene_bin_and_computes_distribution() -> None:
    train = _frame(["R10H R20H R49H", "R60H", "R70H", "WT"])
    fitted = ResidueEventConcentrationFamily(
        ("G1",), bin_width=50, min_patient_bin_support=2
    ).fit(train)

    assert fitted.descriptor.feature_names == FEATURE_NAMES
    assert len(fitted.profiles) == 1
    profile = fitted.profiles[0]
    assert profile.bin_counts == ((0, 1), (1, 2))
    assert profile.patient_bin_support == 3
    assert profile.patient_support == 3
    assert profile.top_bin == 1
    assert np.isclose(profile.hhi, 5 / 9)


def test_transform_uses_frozen_train_distribution_and_handles_unseen_bins() -> None:
    train = _frame(["R10H", "R60H", "R70H"])
    fitted = ResidueEventConcentrationFamily(
        ("G1",), bin_width=50, min_patient_bin_support=2
    ).fit(train)
    before = metadata_json(fitted)
    transformed = fitted.transform(_frame(["R70H", "R510H", "WT"])).toarray()

    assert np.isclose(transformed[0, 0], 1.0)
    assert np.isclose(transformed[0, 1], 2 / 3)
    assert np.isclose(transformed[1, 0], 0.0)
    assert np.isclose(transformed[1, 1], 0.0)
    assert transformed[1, 2] > 0
    assert transformed[1, 3] > 0
    assert np.all(transformed[2] == 0)
    assert metadata_json(fitted) == before


def test_fit_ignores_target_and_validation_data() -> None:
    train = _frame(["R10H", "R60H", "R70H"])
    family = ResidueEventConcentrationFamily(
        ("G1",), bin_width=50, min_patient_bin_support=2
    )
    first = family.fit(train, pd.Series(["A", "B", "C"]))
    second = family.fit(train, pd.Series(["C", "C", "C"]))
    assert first.metadata() == second.metadata()

    first.transform(_frame(["R9999H"]))
    assert first.metadata() == second.metadata()
    metadata = first.metadata()
    assert metadata["target_used_for_fit"] is False
    assert metadata["validation_used_for_fit"] is False
    assert metadata["test_distribution_used_for_fit"] is False


def test_gate_excludes_low_support_and_single_bin_genes() -> None:
    train = _frame(["R10H", "R60H", "WT"], ["R10H", "R20H", "R30H"])
    fitted = ResidueEventConcentrationFamily(
        ("G1", "G2"), bin_width=50, min_patient_bin_support=3
    ).fit(train)
    assert fitted.profiles == ()
    assert np.all(fitted.transform(train).toarray() == 0)


def test_unresolved_and_position_ineligible_tokens_do_not_create_bins() -> None:
    train = _frame(["-287fs", "*261*", "SDEL133fs", "R10H", "R60H"])
    fitted = ResidueEventConcentrationFamily(
        ("G1",), bin_width=50, min_patient_bin_support=2
    ).fit(train)
    assert len(fitted.profiles) == 1
    assert fitted.profiles[0].bin_counts == ((0, 1), (1, 1), (2, 1))


def test_metadata_contains_support_distributions_and_stable_hashes() -> None:
    fitted = ResidueEventConcentrationFamily(
        ("G1",), bin_width=50, min_patient_bin_support=2
    ).fit(_frame(["R10H", "R60H", "R70H"]))
    metadata = json.loads(metadata_json(fitted))
    assert metadata["deduplication_unit"] == "patient_gene_bin"
    assert metadata["gene_profiles"][0]["bin_counts"] == {"0": 1, "1": 2}
    assert len(metadata["gene_profiles_sha256"]) == 64
    assert len(metadata["feature_names_sha256"]) == 64
    assert len(metadata["gene_columns_sha256"]) == 64
