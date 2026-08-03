from __future__ import annotations

import json

import numpy as np
import pytest
from scipy import sparse

from open_cancer.fold_feature_selection import (
    FoldFeatureSelectionError,
    PhiJaccardGreedyPruner,
    load_fold_feature_selection,
    write_fold_feature_selection,
)


def _names(*genes: str) -> list[str]:
    return [f"{gene}__mutated" for gene in genes] + [
        "TP53__missense",
        "TP53__missing",
        "TP53__max_residue_position",
        "sample__mutated_gene_count",
        "hotspot__TP53_R175H",
    ]


def _matrix(rows: list[list[int]], gene_count: int) -> sparse.csr_matrix:
    suffix = np.zeros((len(rows), 5), dtype=np.int32)
    return sparse.csr_matrix(np.hstack([np.asarray(rows, dtype=np.int32), suffix]))


def test_pruner_drops_only_less_prevalent_mutation_presence_column() -> None:
    names = _names("A", "B")
    features = _matrix(
        [
            [1, 1],
            [1, 1],
            [1, 0],
            [1, 0],
            [0, 0],
            [0, 0],
        ],
        2,
    )
    result = PhiJaccardGreedyPruner(phi_min=0.3, jaccard_min=0.4, min_joint_count=2).select(
        features, np.zeros(features.shape[0], dtype=np.int32), names, fold=2
    )

    assert result.metadata["candidate_pair_count"] == 1
    assert result.metadata["dropped_feature_names"] == ["B__mutated"]
    assert result.metadata["matched_pairs"][0]["phi"] == pytest.approx(0.5)
    assert 1 not in result.selected_indices
    # Mutation type, missingness, residue position, global and hotspot columns survive.
    assert result.selected_indices == (0, 2, 3, 4, 5, 6)


def test_pruner_ignores_rare_high_phi_pair_below_joint_support() -> None:
    names = _names("A", "B")
    features = _matrix([[1, 1], [0, 0], [0, 0], [0, 0]], 2)
    result = PhiJaccardGreedyPruner(phi_min=0.1, jaccard_min=0.1, min_joint_count=2).select(
        features, np.zeros(4, dtype=np.int32), names, fold=0
    )
    assert result.selected_indices == tuple(range(len(names)))
    assert result.metadata["candidate_pair_count"] == 0


def test_pruner_uses_deterministic_non_overlapping_greedy_matching() -> None:
    names = _names("A", "B", "C")
    # A/B and B/C are tied candidates. A/B wins the final lexicographic key;
    # B then cannot be used again for B/C.
    features = _matrix(
        [
            [1, 1, 0],
            [1, 1, 0],
            [1, 0, 0],
            [0, 1, 1],
            [0, 1, 1],
            [0, 0, 1],
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
        ],
        3,
    )
    selector = PhiJaccardGreedyPruner(phi_min=0.3, jaccard_min=0.3, min_joint_count=2)
    first = selector.select(features, np.zeros(10, dtype=np.int32), names, fold=0)
    second = selector.select(features, np.zeros(10, dtype=np.int32), names, fold=0)

    assert first == second
    assert first.metadata["candidate_pair_count"] == 2
    assert first.metadata["matched_pair_count"] == 1
    assert first.metadata["matched_pairs"][0]["left_gene"] == "A"
    assert first.metadata["dropped_feature_names"] == ["A__mutated"]


def test_persisted_mask_rejects_feature_order_change(tmp_path) -> None:
    names = _names("A", "B")
    features = _matrix([[1, 1], [1, 1], [1, 0], [0, 0]], 2)
    selection = PhiJaccardGreedyPruner(phi_min=0.2, jaccard_min=0.2, min_joint_count=2).select(
        features, np.zeros(4, dtype=np.int32), names, fold=0
    )
    path = write_fold_feature_selection(selection=selection, feature_names=names, path=tmp_path / "fold.json")

    assert load_fold_feature_selection(path, names).tolist() == list(selection.selected_indices)
    with pytest.raises(FoldFeatureSelectionError, match="schema hash"):
        load_fold_feature_selection(path, list(reversed(names)))


def test_persisted_mask_rejects_modified_selected_hash(tmp_path) -> None:
    names = _names("A", "B")
    features = _matrix([[1, 1], [1, 1], [1, 0], [0, 0]], 2)
    selection = PhiJaccardGreedyPruner(phi_min=0.2, jaccard_min=0.2, min_joint_count=2).select(
        features, np.zeros(4, dtype=np.int32), names, fold=0
    )
    path = write_fold_feature_selection(selection=selection, feature_names=names, path=tmp_path / "fold.json")
    document = json.loads(path.read_text(encoding="utf-8"))
    document["selected_feature_sha256"] = "not-a-real-hash"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(FoldFeatureSelectionError, match="selected feature hash"):
        load_fold_feature_selection(path, names)
