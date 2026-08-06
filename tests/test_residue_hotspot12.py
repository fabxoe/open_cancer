from __future__ import annotations

import json

import numpy as np
import pandas as pd

from open_cancer.residue_hotspot12 import (
    ResidueHotspot12Family,
    metadata_json,
    summarize_fold_stability,
)


def _frame(g1: list[str], g2: list[str] | None = None) -> pd.DataFrame:
    values: dict[str, list[str]] = {"G1": g1}
    if g2 is not None:
        values["G2"] = g2
    return pd.DataFrame(values)


def test_fit_learns_deterministic_width_12_window() -> None:
    train = _frame(["R10H", "R11H", "R20H", "R21H", "R100H"])
    fitted = ResidueHotspot12Family(("G1",)).fit(train)

    assert len(fitted.profiles) == 1
    profile = fitted.profiles[0]
    assert (profile.window_start, profile.window_end) == (10, 21)
    assert profile.window_event_support == 4
    assert profile.total_event_support == 5
    assert np.isclose(profile.window_fraction, 0.8)


def test_fit_deduplicates_patient_gene_position() -> None:
    train = _frame(["R10H R10C R11H", "R10H", "R100H", "R200H"])
    fitted = ResidueHotspot12Family(
        ("G1",), min_event_support=4, min_window_fraction=0.5
    ).fit(train)

    profile = fitted.profiles[0]
    assert profile.total_event_support == 5
    assert profile.window_event_support == 3
    assert np.isclose(profile.window_fraction, 0.6)


def test_only_resolved_positive_missense_positions_are_eligible() -> None:
    train = _frame(["R10H", "R11R", "R12*", "R13fs", "R14H"])
    fitted = ResidueHotspot12Family(
        ("G1",), min_event_support=2, min_window_fraction=1.0
    ).fit(train)

    assert fitted.profiles[0].total_event_support == 2
    assert fitted.profiles[0].window_event_support == 2


def test_transform_keeps_stable_gene_registry_and_aggregates() -> None:
    train = _frame(
        ["R10H", "R11H", "R12H", "R13H", "R100H"],
        ["WT", "WT", "WT", "WT", "WT"],
    )
    fitted = ResidueHotspot12Family(("G1", "G2")).fit(train)
    transformed = fitted.transform(_frame(["R10H R100H", "R100H", "WT"], ["WT"] * 3))
    values = transformed.toarray()

    assert transformed.shape == (3, 5)
    assert fitted.descriptor.feature_names[:2] == (
        "gene__G1__hotspot12_hit",
        "gene__G2__hotspot12_hit",
    )
    assert np.allclose(values[0], [1, 0, 1, 1, 0.5])
    assert np.allclose(values[1], [0, 0, 0, 0, 0])
    assert np.all(values[2] == 0)


def test_target_and_transform_partitions_do_not_change_fit_metadata() -> None:
    train = _frame(["R10H", "R11H", "R12H", "R13H", "R100H"])
    family = ResidueHotspot12Family(("G1",))
    first = family.fit(train, pd.Series(["A", "B", "C", "D", "E"]))
    second = family.fit(train, pd.Series(["A"] * 5))
    before = metadata_json(first)
    first.transform(_frame(["R9999H"]))

    assert first.metadata() == second.metadata()
    assert metadata_json(first) == before
    assert first.metadata()["target_used_for_fit"] is False
    assert first.metadata()["validation_used_for_fit"] is False
    assert first.metadata()["test_distribution_used_for_fit"] is False


def test_empty_support_produces_zero_features() -> None:
    train = _frame(["R10H", "R100H", "WT"])
    fitted = ResidueHotspot12Family(("G1",)).fit(train)

    assert fitted.profiles == ()
    assert np.all(fitted.transform(train).toarray() == 0)


def test_metadata_and_fold_stability_are_reproducible() -> None:
    first = ResidueHotspot12Family(("G1",)).fit(
        _frame(["R10H", "R11H", "R12H", "R13H", "R100H"])
    )
    second = ResidueHotspot12Family(("G1",)).fit(
        _frame(["R10H", "R11H", "R12H", "R13H", "R101H"])
    )
    metadata = json.loads(metadata_json(first))
    stability = summarize_fold_stability((first, second))

    assert metadata["deduplication_unit"] == "patient_gene_residue_position"
    assert metadata["selected_gene_count"] == 1
    assert len(metadata["window_profiles_sha256"]) == 64
    assert stability["selected_gene_counts"] == [1, 1]
    assert stability["mean_pairwise_gene_jaccard"] == 1.0
    assert stability["genes_with_exact_window_in_all_folds"] == 1
