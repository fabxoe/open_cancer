from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd

from open_cancer.abc_c_features import (
    fixed_pathway_burden_family,
    pathway_mutation_type_family,
)
from open_cancer.hotspot_features import build_hotspot_matrix
from open_cancer.robust_mutation_parser import (
    normalize_stop_notation_token,
    parse_stop_notation_invariant_token,
)


def _knowledge(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "source": "test",
                "version": "1",
                "license": "test",
                "source_url": "https://example.test",
                "pathways": {"P": ["TP53"]},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_pathway_features_are_invariant_to_stop_notation(tmp_path: Path) -> None:
    knowledge = _knowledge(tmp_path / "knowledge.json")
    frames = [pd.DataFrame({"TP53": [token]}) for token in ("R175*", "R175X", "R175Ter")]
    burden = fixed_pathway_burden_family(
        ("TP53",),
        knowledge,
        token_parser=parse_stop_notation_invariant_token,
        version="2.1.0",
    ).fit(frames[0])
    composition = pathway_mutation_type_family(
        ("TP53",),
        knowledge,
        token_parser=parse_stop_notation_invariant_token,
        version="2.1.0",
    ).fit(frames[0])
    burden_matrices = [burden.transform(frame) for frame in frames]
    composition_matrices = [composition.transform(frame) for frame in frames]
    assert all((burden_matrices[0] != matrix).nnz == 0 for matrix in burden_matrices[1:])
    assert all(
        (composition_matrices[0] != matrix).nnz == 0
        for matrix in composition_matrices[1:]
    )


def test_hotspot_features_are_invariant_to_stop_notation(tmp_path: Path) -> None:
    matrices = []
    for index, token in enumerate(("R175*", "R175X", "R175Ter")):
        path = tmp_path / f"{index}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["ID", "TP53"])
            writer.writerow(["S1", token])
        matrices.append(
            build_hotspot_matrix(
                path,
                gene_start_column=1,
                hotspots=(("TP53", 175, "R"),),
                token_normalizer=normalize_stop_notation_token,
            )
        )
    assert all((matrices[0] != matrix).nnz == 0 for matrix in matrices[1:])
    assert matrices[0][0, 0] == 1
    assert matrices[0][0, 1] == 1
