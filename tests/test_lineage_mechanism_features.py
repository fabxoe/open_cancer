from __future__ import annotations

import json

import numpy as np
import pandas as pd

from open_cancer.lineage_mechanism_features import LineageMechanismFamily


def test_lineage_mechanism_counts_mutation_type_proxies(tmp_path) -> None:
    knowledge = tmp_path / "mechanisms.json"
    knowledge.write_text(
        json.dumps(
            {
                "version": "test-v1",
                "license": "test-only",
                "source": "fixture",
                "source_url": "https://example.test/mechanisms",
                "modules": {
                    "demo": {
                        "missense_signal_genes": ["A", "B"],
                        "lof_signal_genes": ["B", "C"],
                        "context_genes": ["C", "D"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    frame = pd.DataFrame(
        {
            "A": ["A1V", "WT", "A1V"],
            "B": ["WT", "W2*", "W2V"],
            "C": ["C3fs", "WT", "WT"],
            "D": ["WT", "D4D", "WT"],
        }
    )
    fitted = LineageMechanismFamily(tuple(frame.columns), knowledge).fit(frame)
    actual = fitted.transform(frame).toarray()
    expected = np.asarray(
        [
            [1, 1, 1, 1],
            [0, 1, 1, 0],
            [2, 0, 0, 0],
        ],
        dtype=np.float32,
    )
    np.testing.assert_array_equal(actual, expected)
    assert fitted.descriptor.output_dimension == 4


def test_repository_mechanism_catalog_is_fixed_and_cautious() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    document = json.loads(
        (
            root
            / "knowledge"
            / "cancer_lineage_mechanism_patterns_tcga_v1.json"
        ).read_text(encoding="utf-8")
    )
    assert len(document["modules"]) == 8
    assert "do not prove activation" in document["interpretation_limit"]
    assert "SUBCLASS" not in json.dumps(document)
