from __future__ import annotations

import json
from pathlib import Path

from scipy import sparse

from open_cancer.hotspot_features import (
    EXTENDED_HOTSPOT_FEATURE_NAMES,
    EXTENDED_HOTSPOTS,
    HOTSPOT_FEATURE_NAMES,
    KNOWN_HOTSPOTS,
    build_hotspot_augmented_features,
    build_hotspot_matrix,
    resolve_hotspot_config,
    summarize_hotspot_train_evidence,
    validate_hotspot_train_evidence,
)


def test_resolve_hotspot_config_uses_fixed_34_and_train_only_additions() -> None:
    hotspots, evidence_hotspots, minimum = resolve_hotspot_config({})

    assert hotspots == EXTENDED_HOTSPOTS
    assert evidence_hotspots == EXTENDED_HOTSPOTS[len(KNOWN_HOTSPOTS) :]
    assert minimum == 5


def test_resolve_hotspot_config_rejects_unknown_table_or_invalid_minimum() -> None:
    for config in ({"table": "invented"}, {"minimum_matching_train_rows": 0}):
        try:
            resolve_hotspot_config(config)
        except ValueError:
            pass
        else:
            raise AssertionError("지원하지 않는 hotspot config는 실패해야 합니다.")


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


def test_build_hotspot_augmented_features_can_include_max_position(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    test = tmp_path / "test.csv"
    output = tmp_path / "features"
    train.write_text(
        "ID,SUBCLASS,BRAF,GENE2\nT1,A,V600E S700N,A10V\nT2,B,WT,WT\n",
        encoding="utf-8",
    )
    test.write_text("ID,BRAF,GENE2\nE1,V600E,A20V\n", encoding="utf-8")

    report = build_hotspot_augmented_features(
        train,
        test,
        output,
        selected_position_features=("max_residue_position",),
    )
    names = json.loads((output / "feature_names.json").read_text(encoding="utf-8"))
    matrix = sparse.load_npz(output / "train_features.npz")

    assert matrix[0, names.index("BRAF__max_residue_position")] == 700
    assert matrix[0, names.index("hotspot__BRAF_600")] == 1
    assert report["feature_contract"]["position_features"] == [
        "max_residue_position"
    ]


def test_extended_hotspots_include_known_hotspots_and_new_genes() -> None:
    assert EXTENDED_HOTSPOTS[: len(KNOWN_HOTSPOTS)] == KNOWN_HOTSPOTS
    assert len(EXTENDED_HOTSPOTS) == len(KNOWN_HOTSPOTS) + 15
    assert ("AKT1", 17, "E") in EXTENDED_HOTSPOTS
    assert len(set(EXTENDED_HOTSPOTS)) == len(EXTENDED_HOTSPOTS)
    assert len(EXTENDED_HOTSPOT_FEATURE_NAMES) == len(EXTENDED_HOTSPOTS) + 1


def test_build_hotspot_matrix_with_extended_table(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    train.write_text(
        "ID,SUBCLASS,AKT1,BRAF\nT1,A,E17K,WT\nT2,B,WT,V600E\n",
        encoding="utf-8",
    )
    matrix = build_hotspot_matrix(train, gene_start_column=2, hotspots=EXTENDED_HOTSPOTS)
    names = list(EXTENDED_HOTSPOT_FEATURE_NAMES)
    assert matrix.shape[1] == len(names)
    assert matrix[0, names.index("hotspot__AKT1_17")] == 1
    assert matrix[1, names.index("hotspot__BRAF_600")] == 1
    assert matrix[0, names.index("hotspot__known_hotspot_total_count")] == 1


def test_hotspot_evidence_is_counted_from_train_only(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    train.write_text(
        "ID,SUBCLASS,AKT1\n"
        "T1,A,E17K\n"
        "T2,B,E17K\n"
        "T3,C,E17K\n",
        encoding="utf-8",
    )
    hotspots = (("AKT1", 17, "E"),)

    evidence = summarize_hotspot_train_evidence(train, 2, hotspots)

    assert evidence == [
        {
            "gene": "AKT1",
            "position": 17,
            "expected_reference_aa": "E",
            "matching_train_rows": 3,
            "observed_reference_aas": ["E"],
        }
    ]
    assert validate_hotspot_train_evidence(train, 2, hotspots, 3) == evidence
    fold_train_evidence = summarize_hotspot_train_evidence(
        train, 2, hotspots, include_row_indices={0, 2}
    )
    assert fold_train_evidence[0]["matching_train_rows"] == 2


def test_hotspot_evidence_rejects_low_count_or_reference_noise(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    train.write_text(
        "ID,SUBCLASS,AKT1\nT1,A,E17K\nT2,B,D17N\n",
        encoding="utf-8",
    )

    try:
        validate_hotspot_train_evidence(
            train, 2, (("AKT1", 17, "E"),), minimum_matching_rows=2
        )
    except ValueError as error:
        assert "train-only hotspot 근거 검증" in str(error)
    else:
        raise AssertionError("근거가 부족하거나 reference가 섞이면 실패해야 합니다.")
