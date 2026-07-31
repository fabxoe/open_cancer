from __future__ import annotations

import json
from pathlib import Path

from scipy import sparse

from open_cancer.cosmic_mutation_features import (
    COSMIC_CROSS_FEATURES,
    build_cosmic_mutation_features,
    load_protect_genes,
)


def test_load_protect_genes(tmp_path: Path) -> None:
    path = tmp_path / "protected_genes.csv"
    path.write_text("gene,tier\nGENE1,1\nGENE3,2\n", encoding="utf-8")
    assert load_protect_genes(path) == ["GENE1", "GENE3"]


def test_build_cosmic_cross_features(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    test = tmp_path / "test.csv"
    protect = tmp_path / "protected_genes.csv"
    output = tmp_path / "features"

    # GENE1 is on the protect whitelist, GENE2 is not.
    train.write_text(
        "ID,SUBCLASS,GENE1,GENE2\n"
        'T1,A,"R1538* L1854fs",S27N\n'
        "T2,B,WT,WT\n",
        encoding="utf-8",
    )
    test.write_text(
        "ID,GENE1,GENE2\n"
        "E1,S27N,R1538*\n",
        encoding="utf-8",
    )
    protect.write_text("gene,tier\nGENE1,1\n", encoding="utf-8")

    report = build_cosmic_mutation_features(train, test, protect, output)
    names = json.loads((output / "feature_names.json").read_text(encoding="utf-8"))
    train_matrix = sparse.load_npz(output / "train_features.npz")
    test_matrix = sparse.load_npz(output / "test_features.npz")

    assert train_matrix.shape[1] == len(names)
    assert names[-len(COSMIC_CROSS_FEATURES) :] == list(COSMIC_CROSS_FEATURES)
    assert report["feature_contract"]["protect_gene_count_matched"] == 1

    def value(matrix: sparse.csr_matrix, row: int, name: str) -> float:
        return matrix[row, names.index(name)]

    # T1: protect gene GENE1 has one nonsense + one frameshift token -> LOF count 2.
    assert value(train_matrix, 0, "cosmic__protect_mutated_count") == 1
    assert value(train_matrix, 0, "cosmic__protect_nonsense_count") == 1
    assert value(train_matrix, 0, "cosmic__protect_frameshift_count") == 1
    assert value(train_matrix, 0, "cosmic__protect_lof_count") == 2
    # GENE2's missense mutation must not leak into the protect-only counts.
    assert value(train_matrix, 0, "cosmic__protect_missense_count") == 0

    # T2: wild-type everywhere.
    assert value(train_matrix, 1, "cosmic__protect_mutated_count") == 0

    # E1 (test): protect gene GENE1 carries a missense mutation only.
    assert value(test_matrix, 0, "cosmic__protect_missense_count") == 1
    assert value(test_matrix, 0, "cosmic__protect_lof_count") == 0
