from pathlib import Path

import pandas as pd
import pytest
from scipy import sparse

from open_cancer.hotspot_features import (
    build_hotspot_matrix,
    hotspot_feature_names,
    resolve_hotspot_config,
)
from open_cancer.parser_baseline_features import (
    ParserBaselineFoldBuilder,
    legacy_five_family_feature_names,
    validate_controlled_parser_baseline_config,
)


def _write_frames(tmp_path: Path) -> tuple[Path, Path]:
    train = pd.DataFrame(
        {
            "ID": ["T1", "T2", "T3"],
            "SUBCLASS": ["A", "B", "A"],
            "TP53": ["R1H R2X", "WT", "3_4AA>BB"],
            "EGFR": ["WT", "E5fs", "E6E"],
        }
    )
    test = pd.DataFrame(
        {"ID": ["S1"], "TP53": ["R2Ter"], "EGFR": ["WT"]}
    )
    train_path, test_path = tmp_path / "train.csv", tmp_path / "test.csv"
    train.to_csv(train_path, index=False)
    test.to_csv(test_path, index=False)
    return train_path, test_path


@pytest.mark.parametrize("representation", ["compatibility", "native"])
def test_parser_baseline_builder_replaces_five_family(
    tmp_path: Path, representation: str
) -> None:
    train_path, test_path = _write_frames(tmp_path)
    builder = ParserBaselineFoldBuilder(
        representation=representation,  # type: ignore[arg-type]
        train_path=train_path,
        test_path=test_path,
    )
    base_names = legacy_five_family_feature_names(("TP53", "EGFR"))
    base = sparse.csr_matrix((3, len(base_names)), dtype="float32")
    bundle = builder(
        fold=0,
        train_indices=[0, 1],
        valid_indices=[2],
        base_train=base[:2],
        base_validation=base[2:],
        base_test=sparse.csr_matrix((1, len(base_names))),
        base_feature_names=base_names,
        target=[0, 1],
    )
    assert bundle.base_feature_names_to_drop == base_names
    assert bundle.train.shape[0] == 2
    assert bundle.validation.shape[0] == 1
    assert bundle.test.shape[0] == 1
    assert bundle.registry["parser_baseline_projection"]["representation"] == representation


def test_disabled_hotspot_table_has_zero_columns(tmp_path: Path) -> None:
    train_path, _ = _write_frames(tmp_path)
    hotspots, evidence, minimum = resolve_hotspot_config(
        {"table": "none", "evidence_scope": "none", "minimum_matching_train_rows": 1}
    )
    assert hotspots == evidence == ()
    assert minimum == 1
    assert hotspot_feature_names(hotspots) == ()
    assert build_hotspot_matrix(train_path, 2, hotspots).shape == (3, 0)


def test_controlled_config_rejects_confounders() -> None:
    base = {
        "parser_baseline": {"representation": "native"},
        "hotspots": {"table": "none"},
        "features": {"robust_aggregates": [], "residue_position": {"enabled": False}},
        "training": {
            "checkpoint_selection": "macro_f1_validation",
            "balanced_sample_weight": True,
        },
    }
    assert validate_controlled_parser_baseline_config(base) == "native"
    base["hotspots"]["table"] = "extended_34"
    with pytest.raises(ValueError, match="hotspot"):
        validate_controlled_parser_baseline_config(base)


def test_large_parser_schema_is_identified_by_count_and_hash() -> None:
    names = legacy_five_family_feature_names(("TP53", "EGFR"))
    assert len(names) == 15
    assert names[:5] == (
        "sample__missense_count",
        "sample__synonymous_count",
        "sample__nonsense_count",
        "sample__frameshift_count",
        "sample__complex_count",
    )
