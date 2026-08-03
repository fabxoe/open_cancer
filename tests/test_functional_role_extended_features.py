from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from open_cancer.abc_c_features import load_fixed_groups
from open_cancer.functional_role_extended_features import (
    FunctionalRoleBurdenExtendedError,
    functional_role_burden_extended_family,
)


def knowledge_path() -> Path:
    return Path(__file__).resolve().parents[1] / "knowledge/abc_c_compact_groups_v1.json"


def gene_universe() -> tuple[str, ...]:
    roles, _ = load_fixed_groups(knowledge_path(), kind="functional_roles")
    genes = sorted({gene for members in roles.values() for gene in members})
    return tuple(genes)


def _onco_genes() -> tuple[str, ...]:
    roles, _ = load_fixed_groups(knowledge_path(), kind="functional_roles")
    return roles["oncogene"]


def _tsg_genes() -> tuple[str, ...]:
    roles, _ = load_fixed_groups(knowledge_path(), kind="functional_roles")
    return roles["tumor_suppressor"]


def make_frame(n: int, *, onco_hits: np.ndarray, tsg_hits: np.ndarray, filler_hits: int = 0) -> pd.DataFrame:
    """Build an n-row frame with controllable per-row mutated-gene counts.

    onco_hits[i]/tsg_hits[i] genes (from the front of each role list) are set
    to a nonsense token; filler_hits additional non-role genes are mutated in
    every row to vary total mutated-gene burden independent of the roles.
    """
    genes = gene_universe()
    onco_genes = _onco_genes()
    tsg_genes = _tsg_genes()
    filler_genes = tuple(f"FILLER{i}" for i in range(filler_hits))
    all_columns = tuple(genes) + filler_genes
    rows = []
    for i in range(n):
        row = {gene: "WT" for gene in all_columns}
        for gene in onco_genes[: int(onco_hits[i])]:
            row[gene] = "R1*"
        for gene in tsg_genes[: int(tsg_hits[i])]:
            row[gene] = "R2*"
        for gene in filler_genes:
            row[gene] = "R3*"
        rows.append(row)
    frame = pd.DataFrame(rows)
    frame.insert(0, "ID", [f"T{i}" for i in range(n)])
    return frame


def test_no_gate_triggered_keeps_all_eight_candidates() -> None:
    n = 200
    rng = np.random.default_rng(0)
    # integers(0, 10) leaves ~10% exact zeros -> P(zero) > 5% (no saturation)
    # and ~90% nonzero -> P(nonzero) > 1% (no sparse gate).
    onco_hits = rng.integers(0, 10, size=n)
    tsg_hits = rng.integers(0, 10, size=n)
    frame = make_frame(n, onco_hits=onco_hits, tsg_hits=tsg_hits, filler_hits=5)
    target = rng.integers(0, 26, size=n)  # spread across classes -> no dominance

    family = functional_role_burden_extended_family(
        tuple(frame.columns[1:]), knowledge_path()
    )
    fitted = family.fit(frame, target)
    assert fitted.allowed_kinds["oncogene"] == ("raw", "frac", "resid", "log1p")
    assert fitted.allowed_kinds["tumor_suppressor"] == ("raw", "frac", "resid", "log1p")
    assert fitted.descriptor.output_dimension == 8

    matrix = fitted.transform(frame).toarray()
    names = fitted.descriptor.feature_names
    onco_genes = _onco_genes()
    expected_raw = np.array([min(onco_hits[i], len(onco_genes)) for i in range(n)], dtype=np.float64)
    np.testing.assert_allclose(
        matrix[:, names.index("sample__role_oncogene__count_raw")], expected_raw
    )
    np.testing.assert_allclose(
        matrix[:, names.index("sample__role_oncogene__count_frac")],
        expected_raw / len(onco_genes),
    )
    np.testing.assert_allclose(
        matrix[:, names.index("sample__role_oncogene__count_log1p")],
        np.log1p(expected_raw),
    )


def test_sparse_gate_drops_entire_group() -> None:
    n = 200
    onco_hits = np.zeros(n)  # every row has zero oncogene hits -> P(nonzero) = 0 < 1%
    tsg_hits = np.full(n, 5)
    frame = make_frame(n, onco_hits=onco_hits, tsg_hits=tsg_hits)
    target = np.arange(n) % 26

    family = functional_role_burden_extended_family(
        tuple(frame.columns[1:]), knowledge_path()
    )
    fitted = family.fit(frame, target)
    assert fitted.allowed_kinds["oncogene"] == ()
    assert fitted.gate_summary["oncogene"]["gate_triggered"] == "sparse"
    assert all(not name.startswith("sample__role_oncogene__") for name in fitted.descriptor.feature_names)


def test_saturation_gate_drops_raw_and_log1p() -> None:
    n = 200
    rng = np.random.default_rng(1)
    onco_hits = rng.integers(1, 10, size=n)  # every row has >=1 hit -> P(zero) = 0 < 5%
    tsg_hits = rng.integers(1, 10, size=n)
    frame = make_frame(n, onco_hits=onco_hits, tsg_hits=tsg_hits)
    target = rng.integers(0, 26, size=n)

    family = functional_role_burden_extended_family(
        tuple(frame.columns[1:]), knowledge_path()
    )
    fitted = family.fit(frame, target)
    assert fitted.allowed_kinds["oncogene"] == ("frac", "resid")
    assert fitted.gate_summary["oncogene"]["gate_triggered"] == "saturation"


def test_dominance_gate_drops_raw_and_frac() -> None:
    n = 300
    rng = np.random.default_rng(2)
    onco_hits = rng.integers(0, 3, size=n)
    onco_hits[rng.random(n) < 0.5] = 0  # keep plenty of zero rows (avoid saturation)
    tsg_hits = rng.integers(1, 10, size=n)
    frame = make_frame(n, onco_hits=onco_hits, tsg_hits=tsg_hits)
    target = rng.integers(0, 26, size=n)
    # Force 90%+ of oncogene-positive rows into a single class (0).
    positive = onco_hits > 0
    positive_idx = np.flatnonzero(positive)
    force_count = int(0.95 * len(positive_idx))
    target = target.copy()
    target[positive_idx[:force_count]] = 0

    family = functional_role_burden_extended_family(
        tuple(frame.columns[1:]), knowledge_path()
    )
    fitted = family.fit(frame, target)
    assert fitted.gate_summary["oncogene"]["dominance_at_nonzero"] >= 0.8
    assert fitted.allowed_kinds["oncogene"] == ("resid", "log1p")


def test_fit_requires_target() -> None:
    frame = make_frame(5, onco_hits=np.array([1, 2, 3, 4, 5]), tsg_hits=np.array([1, 1, 1, 1, 1]))
    family = functional_role_burden_extended_family(
        tuple(frame.columns[1:]), knowledge_path()
    )
    with pytest.raises(FunctionalRoleBurdenExtendedError):
        family.fit(frame, None)


def test_resid_has_near_zero_mean_on_fit_partition() -> None:
    n = 200
    rng = np.random.default_rng(3)
    onco_hits = rng.integers(1, 10, size=n)
    tsg_hits = rng.integers(1, 10, size=n)
    frame = make_frame(n, onco_hits=onco_hits, tsg_hits=tsg_hits, filler_hits=8)
    target = rng.integers(0, 26, size=n)

    family = functional_role_burden_extended_family(
        tuple(frame.columns[1:]), knowledge_path()
    )
    fitted = family.fit(frame, target)
    matrix = fitted.transform(frame).toarray()
    names = fitted.descriptor.feature_names
    resid_col = matrix[:, names.index("sample__role_tumor_suppressor__count_resid")]
    assert abs(resid_col.mean()) < 1e-6
