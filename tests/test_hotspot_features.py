from __future__ import annotations

import json
from pathlib import Path

from scipy import sparse

from open_cancer.hotspot_features import (
    HOTSPOT_FEATURE_NAMES,
    build_hotspot_augmented_features,
    build_hotspot_matrix,
)


def test_build_hotspot_matrix_counts_and_filters_mismatched_reference(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    train.write_text(
        "ID,SUBCLASS,BRAF,TP53,OTHERGENE\n"
        # T1: real BRAF V600E hotspot hit.
        "T1,A,V600E,WT,WT\n"
        # T2: TP53 175 with the WRONG reference AA (H instead of canonical R) -> must not count.
        "T2,B,WT,H175Q,WT\n"
        # T3: position matches a hotspot gene but not a curated hotspot position -> must not count.
        "T3,C,V601E,WT,WT\n",
        encoding="utf-8",
    )
    test = tmp_path / "test.csv"
    test.write_text(
        "ID,BRAF,TP53,OTHERGENE\n"
        # E1: two curated hotspots in one patient (BRAF + TP53 175 with correct reference).
        "E1,V600E,R175H,WT\n",
        encoding="utf-8",
    )

    train_matrix = build_hotspot_matrix(train, gene_start_column=2)
    test_matrix = build_hotspot_matrix(test, gene_start_column=1)
    names = list(HOTSPOT_FEATURE_NAMES)

    def value(matrix: sparse.csr_matrix, row: int, name: str) -> float:
        return matrix[row, names.index(name)]

    assert value(train_matrix, 0, "hotspot__BRAF_600") == 1
    assert value(train_matrix, 0, "hotspot__known_hotspot_total_count") == 1
    # Wrong reference AA at a real hotspot position must not count.
    assert value(train_matrix, 1, "hotspot__TP53_175") == 0
    assert value(train_matrix, 1, "hotspot__known_hotspot_total_count") == 0
    # Non-hotspot position in a hotspot gene must not count.
    assert value(train_matrix, 2, "hotspot__BRAF_600") == 0

    assert value(test_matrix, 0, "hotspot__BRAF_600") == 1
    assert value(test_matrix, 0, "hotspot__TP53_175") == 1
    assert value(test_matrix, 0, "hotspot__known_hotspot_total_count") == 2


def test_build_hotspot_augmented_features_appends_to_base_names(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    test = tmp_path / "test.csv"
    output = tmp_path / "features"
    train.write_text(
        "ID,SUBCLASS,BRAF,GENE2\nT1,A,V600E,WT\nT2,B,WT,WT\n",
        encoding="utf-8",
    )
    test.write_text("ID,BRAF,GENE2\nE1,WT,S27N\n", encoding="utf-8")

    report = build_hotspot_augmented_features(train, test, output)
    names = json.loads((output / "feature_names.json").read_text(encoding="utf-8"))
    train_matrix = sparse.load_npz(output / "train_features.npz")

    assert names[-len(HOTSPOT_FEATURE_NAMES) :] == list(HOTSPOT_FEATURE_NAMES)
    assert train_matrix.shape[1] == len(names)
    assert report["feature_contract"]["hotspot_features"] == list(HOTSPOT_FEATURE_NAMES)
