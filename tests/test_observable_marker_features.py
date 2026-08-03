from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from open_cancer.observable_marker_features import (
    ObservableMarkerFamily,
    ObservableMarkerFeatureError,
)


def _write_catalog(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "version": "test-v1",
                "license": "test-only",
                "source": "fixture",
                "source_url": "https://example.test/markers",
                "feature_policy": {
                    "target_used": False,
                    "public_leaderboard_used": False,
                },
                "panels": {
                    "demo_proxy": {
                        "genes": ["A", "B"],
                        "interpretation": "Observed mutation proxy only",
                    },
                    "single_proxy": {
                        "genes": ["C"],
                        "interpretation": "Observed mutation proxy only",
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def test_marker_proxy_outputs_are_small_binary_and_target_independent(tmp_path) -> None:
    knowledge = tmp_path / "markers.json"
    _write_catalog(knowledge)
    frame = pd.DataFrame(
        {
            "A": ["A1V", "WT", "A2A", "A3*"],
            "B": ["WT", "B2fs", "B2V", "B4V"],
            "C": ["WT", "C3V", "WT", "C5C"],
        }
    )
    family = ObservableMarkerFamily(tuple(frame.columns), knowledge)
    fitted_one = family.fit(frame, pd.Series([0, 0, 0, 0]))
    fitted_two = family.fit(frame, pd.Series([9, 8, 7, 6]))
    actual_one = fitted_one.transform(frame).toarray()
    actual_two = fitted_two.transform(frame).toarray()
    np.testing.assert_array_equal(actual_one, actual_two)
    np.testing.assert_array_equal(
        actual_one,
        np.asarray(
            [
                [1, 1, 0, 0, 0, 0, 0, 0],
                [1, 1, 1, 0, 1, 1, 0, 0],
                [1, 1, 0, 1, 0, 0, 0, 0],
                [1, 1, 1, 1, 1, 0, 0, 0],
            ],
            dtype=np.float32,
        ),
    )
    assert fitted_one.descriptor.fit_scope == "stateless"
    assert fitted_one.descriptor.output_dimension == 8
    assert set(np.unique(actual_one)).issubset({0.0, 1.0})


def test_marker_proxy_records_missing_catalog_genes_and_uses_fixed_intersection(tmp_path) -> None:
    knowledge = tmp_path / "markers.json"
    _write_catalog(knowledge)
    frame = pd.DataFrame({"A": ["A1V"], "B": ["WT"], "C": ["WT"]})
    fitted = ObservableMarkerFamily(("A", "C"), knowledge).fit(frame[["A", "C"]])
    assert fitted.intersections == {"demo_proxy": ("A",), "single_proxy": ("C",)}
    assert fitted.missing_catalog_genes == ("B",)


def test_marker_proxy_rejects_panel_with_no_competition_gene(tmp_path) -> None:
    knowledge = tmp_path / "markers.json"
    _write_catalog(knowledge)
    frame = pd.DataFrame({"A": ["WT"], "B": ["WT"]})
    with pytest.raises(ObservableMarkerFeatureError, match="교집합이 없는"):
        ObservableMarkerFamily(tuple(frame.columns), knowledge).fit(frame)


def test_repository_catalog_is_cautious_and_does_not_use_target() -> None:
    root = Path(__file__).resolve().parents[1]
    document = json.loads(
        (root / "knowledge" / "fixed_observable_cancer_markers_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert document["feature_policy"]["target_used"] is False
    assert document["feature_policy"]["public_leaderboard_used"] is False
    assert any(
        "gene fusion" in item for item in document["input_contract"]["not_observable"]
    )
    assert "MSI or dMMR assay status" in document["input_contract"]["not_observable"]
    assert "do not reproduce clinical biomarker assays" in document["interpretation_limit"]
    assert "SUBCLASS" not in json.dumps(document)
