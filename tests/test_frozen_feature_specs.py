from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from scipy import sparse

from open_cancer.frozen_feature_specs import (
    FROZEN_BASE_SHA256,
    FrozenFeatureSpecError,
    materialize_frozen_feature_spec,
    resolve_frozen_feature_spec,
)


ROOT = Path(__file__).resolve().parents[1]


def test_resolve_all_frozen_feature_specs() -> None:
    v1 = resolve_frozen_feature_spec(ROOT, "v1")
    performance = resolve_frozen_feature_spec(ROOT, "v2-performance")
    diversity = resolve_frozen_feature_spec(ROOT, "v2-diversity")
    assert v1.families == ()
    assert performance.families == ("fixed_pathway_burden",)
    assert diversity.families == ("amino_acid_change",)
    assert v1.base_feature_spec_sha256 == FROZEN_BASE_SHA256


def test_reject_unknown_feature_spec() -> None:
    with pytest.raises(FrozenFeatureSpecError, match="알 수 없는"):
        resolve_frozen_feature_spec(ROOT, "v3")


@pytest.mark.parametrize(
    ("spec_name", "expected_dimension"),
    (("v2-performance", 21), ("v2-diversity", 5)),
)
def test_materialize_v2_spec_on_fixture(
    tmp_path,
    monkeypatch,
    spec_name,
    expected_dimension,
) -> None:
    pathway_document = json.loads(
        (ROOT / "knowledge" / "canonical_pathways_sanchez_vega_v1.json").read_text(
            encoding="utf-8"
        )
    )
    genes = sorted(
        {
            gene
            for members in pathway_document["pathways"].values()
            for gene in members
        }
    )
    train = pd.DataFrame(
        [
            {"ID": "TRAIN_0", "SUBCLASS": "ACC", **dict.fromkeys(genes, "WT")},
            {"ID": "TRAIN_1", "SUBCLASS": "BLCA", **dict.fromkeys(genes, "G12D")},
        ]
    )
    test = pd.DataFrame(
        [{"ID": "TEST_0", **dict.fromkeys(genes, "G12D")}]
    )
    train_path = tmp_path / "train.csv"
    test_path = tmp_path / "test.csv"
    train.to_csv(train_path, index=False)
    test.to_csv(test_path, index=False)

    def fake_base_builder(train_path, test_path, output_dir, **kwargs):
        del train_path, test_path, kwargs
        output_dir.mkdir(parents=True, exist_ok=True)
        sparse.save_npz(output_dir / "train_features.npz", sparse.csr_matrix([[1], [1]]))
        sparse.save_npz(output_dir / "test_features.npz", sparse.csr_matrix([[1]]))
        (output_dir / "feature_names.json").write_text('["base__fixture"]\n', encoding="utf-8")
        return {"feature_contract": {"feature_spec_sha256": FROZEN_BASE_SHA256}}

    monkeypatch.setattr(
        "open_cancer.frozen_feature_specs.build_hotspot_augmented_features",
        fake_base_builder,
    )
    manifest = materialize_frozen_feature_spec(
        root=ROOT,
        name=spec_name,
        output_dir=tmp_path / "output",
        train_path=train_path,
        test_path=test_path,
    )
    assert manifest["train_shape"] == [2, expected_dimension]
    assert manifest["test_shape"] == [1, expected_dimension]
