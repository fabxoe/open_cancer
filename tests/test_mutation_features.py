from __future__ import annotations

import json
from pathlib import Path

from scipy import sparse

from open_cancer.mutation_features import (
    GENE_FEATURES,
    GLOBAL_FEATURES,
    ROBUST_GLOBAL_FEATURES,
    build_mutation_features,
    classify_mutation_token,
    feature_names,
)


def test_classify_mutation_tokens() -> None:
    assert classify_mutation_token("S27N") == "missense"
    assert classify_mutation_token("R895R") == "synonymous"
    assert classify_mutation_token("R1538*") == "nonsense"
    assert classify_mutation_token("L1854fs") == "frameshift"
    assert classify_mutation_token("WQ288fs") == "frameshift"
    assert classify_mutation_token("468_469LG>F*") == "complex"


def test_feature_names_are_stable() -> None:
    names = feature_names(["GENE1", "GENE2"])
    assert names[: len(GLOBAL_FEATURES)] == list(GLOBAL_FEATURES)
    assert len(names) == len(GLOBAL_FEATURES) + 2 * len(GENE_FEATURES)
    assert "GENE1__frameshift" in names
    assert "GENE2__missing" in names
    robust_names = feature_names(["GENE1"], include_robust_aggregates=True)
    assert robust_names[len(GLOBAL_FEATURES) : len(GLOBAL_FEATURES) + len(ROBUST_GLOBAL_FEATURES)] == list(
        ROBUST_GLOBAL_FEATURES
    )


def test_build_sparse_train_test_features(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    test = tmp_path / "test.csv"
    output = tmp_path / "features"
    train.write_text(
        "ID,SUBCLASS,GENE1,GENE2\n"
        'T1,A,"S27N R28R",WT\n'
        "T2,B,L1854fs,\n",
        encoding="utf-8",
    )
    test.write_text(
        "ID,GENE1,GENE2\n"
        "E1,R1538*,468_469LG>F*\n",
        encoding="utf-8",
    )

    report = build_mutation_features(train, test, output)
    train_matrix = sparse.load_npz(output / "train_features.npz")
    test_matrix = sparse.load_npz(output / "test_features.npz")
    names = json.loads((output / "feature_names.json").read_text(encoding="utf-8"))

    assert train_matrix.shape == (2, len(names))
    assert test_matrix.shape == (1, len(names))
    assert report["feature_contract"]["target_used_for_features"] is False
    assert train_matrix[0, names.index("sample__total_variant_count")] == 2
    assert train_matrix[0, names.index("GENE1__missense")] == 1
    assert train_matrix[0, names.index("GENE1__synonymous")] == 1
    assert train_matrix[1, names.index("GENE2__missing")] == 1
    assert test_matrix[0, names.index("GENE1__nonsense")] == 1
    assert test_matrix[0, names.index("GENE2__complex")] == 1


def test_robust_aggregate_features_are_finite_and_safe(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    test = tmp_path / "test.csv"
    output = tmp_path / "features"
    train.write_text(
        "ID,SUBCLASS,GENE1,GENE2\n"
        "T1,A,WT,WT\n"
        'T2,B,"S27N R28R",\n',
        encoding="utf-8",
    )
    test.write_text("ID,GENE1,GENE2\nE1,R1538*,L1854fs\n", encoding="utf-8")

    build_mutation_features(
        train,
        test,
        output,
        include_robust_aggregates=True,
    )
    matrix = sparse.load_npz(output / "train_features.npz")
    names = json.loads((output / "feature_names.json").read_text(encoding="utf-8"))
    robust_indices = [names.index(name) for name in ROBUST_GLOBAL_FEATURES]
    robust = matrix[:, robust_indices].toarray()

    assert all(value == 0 for value in robust[0])
    assert all(value == value for value in robust.ravel())
    assert matrix[1, names.index("sample__missense_ratio")] == 0.5
    assert matrix[1, names.index("sample__synonymous_ratio")] == 0.5
    assert matrix[1, names.index("sample__multi_variant_gene_ratio")] == 1.0
    assert matrix[1, names.index("sample__missing_gene_ratio")] == 0.5
