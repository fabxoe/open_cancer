from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from scipy import sparse

from open_cancer.mutation_features import build_mutation_features
from open_cancer.robust_mutation_parser import (
    POSITION_SANITATION_PARSER_CONTRACT,
    STOP_NOTATION_PARSER_CONTRACT,
    parse_position_sanitized_cell,
    parse_stop_notation_invariant_cell,
)


def _write_pair(root: Path, *, g1: str, g2: str = "WT") -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    train = root / "train.csv"
    test = root / "test.csv"
    with train.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ID", "SUBCLASS", "G1", "G2"])
        writer.writerow(["TR1", "ACC", g1, g2])
    with test.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ID", "G1", "G2"])
        writer.writerow(["TE1", g1, g2])
    return train, test


def _matrix(
    root: Path,
    token: str,
    *,
    parser=None,
    contract=None,
) -> tuple[sparse.csr_matrix, list[str]]:
    train, test = _write_pair(root, g1=token)
    kwargs = {}
    if parser is not None:
        kwargs = {
            "mutation_cell_parser": parser,
            "mutation_parser_contract": contract,
        }
    build_mutation_features(
        train,
        test,
        root / "features",
        selected_position_features=("max_residue_position",),
        **kwargs,
    )
    matrix = sparse.load_npz(root / "features" / "train_features.npz")
    names = json.loads(
        (root / "features" / "feature_names.json").read_text(encoding="utf-8")
    )
    return matrix, names


def test_stop_notation_canonical_feature_matrix_is_identical(tmp_path: Path) -> None:
    matrices = []
    names = []
    for index, token in enumerate(("R213*", "R213X", "R213Ter")):
        matrix, feature_names = _matrix(
            tmp_path / str(index),
            token,
            parser=parse_stop_notation_invariant_cell,
            contract=STOP_NOTATION_PARSER_CONTRACT,
        )
        matrices.append(matrix)
        names.append(feature_names)
    assert names[0] == names[1] == names[2]
    assert (matrices[0] != matrices[1]).nnz == 0
    assert (matrices[0] != matrices[2]).nnz == 0


def test_v1_feature_matrix_exposes_stop_notation_blind_spot(tmp_path: Path) -> None:
    star, names = _matrix(tmp_path / "star", "R213*")
    x_stop, _ = _matrix(tmp_path / "x", "R213X")
    assert (star != x_stop).nnz > 0
    assert star[0, names.index("sample__nonsense_count")] == 1
    assert x_stop[0, names.index("sample__complex_count")] == 1
    assert star[0, names.index("G1__nonsense")] == 1
    assert x_stop[0, names.index("G1__complex")] == 1


def test_position_sanitizer_preserves_type_but_removes_ambiguous_positions(
    tmp_path: Path,
) -> None:
    train, test = _write_pair(tmp_path, g1="-287fs", g2="*261*")
    build_mutation_features(
        train,
        test,
        tmp_path / "features",
        selected_position_features=("max_residue_position",),
        mutation_cell_parser=parse_position_sanitized_cell,
        mutation_parser_contract=POSITION_SANITATION_PARSER_CONTRACT,
    )
    matrix = sparse.load_npz(tmp_path / "features" / "train_features.npz")
    names = json.loads(
        (tmp_path / "features" / "feature_names.json").read_text(encoding="utf-8")
    )
    assert matrix[0, names.index("G1__frameshift")] == 1
    assert matrix[0, names.index("G2__complex")] == 1
    assert matrix[0, names.index("G1__max_residue_position")] == 0
    assert matrix[0, names.index("G2__max_residue_position")] == 0


def test_custom_parser_requires_versioned_contract(tmp_path: Path) -> None:
    train, test = _write_pair(tmp_path, g1="R213X")
    try:
        build_mutation_features(
            train,
            test,
            tmp_path / "features",
            mutation_cell_parser=parse_stop_notation_invariant_cell,
        )
    except ValueError as error:
        assert "versioned parser contract" in str(error)
    else:
        raise AssertionError("custom parser without contract must fail")
