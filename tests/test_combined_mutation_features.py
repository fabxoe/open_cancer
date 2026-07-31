from __future__ import annotations

import json
from pathlib import Path

from scipy import sparse

from open_cancer.combined_mutation_features import (
    LOF_CROSS_FEATURES,
    build_lof_hotspot_features,
)
from open_cancer.hotspot_features import HOTSPOT_FEATURE_NAMES


def test_build_lof_hotspot_features_appends_both_families(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    test = tmp_path / "test.csv"
    protect = tmp_path / "protected_genes.csv"
    output = tmp_path / "features"

    # GENE1 (protect) carries a nonsense mutation (LOF); BRAF carries the V600 hotspot.
    train.write_text(
        "ID,SUBCLASS,GENE1,BRAF\nT1,A,R1538*,V600E\nT2,B,WT,WT\n",
        encoding="utf-8",
    )
    test.write_text("ID,GENE1,BRAF\nE1,WT,WT\n", encoding="utf-8")
    protect.write_text("gene,tier\nGENE1,1\n", encoding="utf-8")

    report = build_lof_hotspot_features(train, test, protect, output)
    names = json.loads((output / "feature_names.json").read_text(encoding="utf-8"))
    train_matrix = sparse.load_npz(output / "train_features.npz")

    tail = list(LOF_CROSS_FEATURES) + list(HOTSPOT_FEATURE_NAMES)
    assert names[-len(tail) :] == tail
    assert train_matrix.shape[1] == len(names)

    def value(matrix: sparse.csr_matrix, row: int, name: str) -> float:
        return matrix[row, names.index(name)]

    assert value(train_matrix, 0, "cosmic__protect_lof_count") == 1
    assert value(train_matrix, 0, "hotspot__BRAF_600") == 1
    assert value(train_matrix, 1, "cosmic__protect_lof_count") == 0
    assert value(train_matrix, 1, "hotspot__BRAF_600") == 0
