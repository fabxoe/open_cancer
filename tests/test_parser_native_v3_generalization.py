from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np


def _load_module():
    root = Path(__file__).resolve().parents[1]
    scripts = root / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location(
            "analyze_parser_native_v3_generalization",
            scripts / "analyze_parser_native_v3_generalization.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


def test_native_v3_feature_family_is_total_and_semantic() -> None:
    module = _load_module()
    assert module.native_v3_feature_family("sample__mutated_gene_count") == (
        "base_sample_aggregate"
    )
    assert module.native_v3_feature_family("TP53__mutated") == "gene_mutation_presence"
    assert module.native_v3_feature_family("TP53__missing") == "missingness"
    assert module.native_v3_feature_family(
        "sample__native_v3_range_stop_token_count"
    ) == "native_range_stop"
    assert module.native_v3_feature_family(
        "gene__TP53__native_v3_range_no_change_any"
    ) == "native_range_no_change"


def test_family_index_map_partitions_each_feature_once() -> None:
    module = _load_module()
    names = (
        "sample__mutated_gene_count",
        "TP53__mutated",
        "TP53__missing",
        *(f"sample__native_v3_{value}_token_count" for value in module.MODEL_ACTIVE_V3_CONSEQUENCES),
    )
    groups = module.family_index_map(names)
    covered = np.concatenate(list(groups.values()))
    assert sorted(covered.tolist()) == list(range(len(names)))
    assert len(groups["native_range_stop"]) == 1


def test_range_cooccurrence_covers_every_row() -> None:
    module = _load_module()
    names = (
        "sample__native_v3_range_replacement_token_count",
        "sample__native_v3_range_stop_token_count",
        "sample__native_v3_range_no_change_token_count",
    )
    matrix = module.sparse.csr_matrix(
        [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 0, 1]], dtype=np.float32
    )
    rows = module.range_cooccurrence(matrix, matrix, names)
    assert sum(row["rows"] for row in rows if row["domain"] == "train") == 4
    assert sum(row["rows"] for row in rows if row["domain"] == "test") == 4
