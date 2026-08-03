from __future__ import annotations

import json

import numpy as np
import pandas as pd

from open_cancer.molecular_constellation_features import MolecularConstellationFamily


def test_molecular_constellation_counts_and_joint_states(tmp_path) -> None:
    knowledge = tmp_path / "modules.json"
    knowledge.write_text(
        json.dumps(
            {
                "version": "test-v1",
                "license": "test-only",
                "source": "fixture",
                "source_url": "https://example.test/modules",
                "modules": {
                    "demo": {
                        "core_genes": ["A", "B"],
                        "partner_genes": ["C", "D"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    frame = pd.DataFrame(
        {
            "A": ["p.A1V", "WT", "p.A1V", ""],
            "B": ["WT", "WT", "p.B2*", "WT"],
            "C": ["p.C3V", "p.C3V", "WT", ""],
            "D": ["WT", "WT", "p.D4V", "WT"],
        }
    )
    fitted = MolecularConstellationFamily(tuple(frame.columns), knowledge).fit(frame)
    actual = fitted.transform(frame).toarray()
    expected = np.asarray(
        [
            [2, 1, 1],
            [1, 0, 0],
            [3, 1, 1],
            [0, 0, 0],
        ],
        dtype=np.float32,
    )
    np.testing.assert_array_equal(actual, expected)
    assert fitted.descriptor.fit_scope == "stateless"
    assert fitted.descriptor.output_dimension == 3


def test_repository_module_catalog_is_target_independent() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    document = json.loads(
        (root / "knowledge" / "cancer_lineage_modules_tcga_v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert document["rule_review_status"].startswith("NO_PROHIBITION_IDENTIFIED")
    assert "no external patient data" in document["competition_rule_basis"]
    assert len(document["modules"]) == 7
    assert "SUBCLASS" not in json.dumps(document)
