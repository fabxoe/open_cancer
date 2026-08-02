"""Fold-safe, target-independent feature selection primitives.

The selectors in this module are fit on one outer training fold only.  Their
saved selection documents let a checkpoint inference path replay exactly the
same feature mask without looking at validation or test rows.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence

import numpy as np
from scipy import sparse

from open_cancer.hashing import sha256_lines


class FoldFeatureSelectionError(ValueError):
    """Raised when a selector or its persisted mask violates the contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FoldFeatureSelectionError(message)


def feature_name_sha256(feature_names: Sequence[str]) -> str:
    """Hash the complete, ordered model input schema."""
    return sha256_lines(str(name) for name in feature_names)


def selected_feature_sha256(indices: Sequence[int], feature_names: Sequence[str]) -> str:
    """Hash selected indices together with their names and order."""
    return sha256_lines(f"{index}:{feature_names[index]}" for index in indices)


@dataclass(frozen=True)
class FoldFeatureSelection:
    """One outer-fold feature mask and an auditable selection explanation."""

    selected_indices: tuple[int, ...]
    metadata: dict[str, Any]


class FoldFeatureSelector(Protocol):
    """Fit a feature mask from one outer training matrix only."""

    def select(
        self,
        features: sparse.csr_matrix,
        targets: np.ndarray,
        feature_names: Sequence[str],
        fold: int,
    ) -> FoldFeatureSelection: ...


def write_fold_feature_selection(
    *,
    selection: FoldFeatureSelection,
    feature_names: Sequence[str],
    path: Path,
) -> Path:
    """Persist a replayable feature mask with ordered-schema hashes."""
    indices = _validated_indices(selection.selected_indices, len(feature_names))
    document = {
        "feature_name_sha256": feature_name_sha256(feature_names),
        "selected_feature_sha256": selected_feature_sha256(indices, feature_names),
        "selected_feature_count": len(indices),
        "selected_indices": indices,
        "metadata": selection.metadata,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_fold_feature_selection(path: Path, feature_names: Sequence[str]) -> np.ndarray:
    """Load a persisted mask and reject reordered or mismatched features."""
    document = json.loads(path.read_text(encoding="utf-8"))
    _require(
        document.get("feature_name_sha256") == feature_name_sha256(feature_names),
        "저장된 feature schema hash가 현재 입력과 다릅니다.",
    )
    indices = _validated_indices(document.get("selected_indices", []), len(feature_names))
    _require(
        document.get("selected_feature_sha256") == selected_feature_sha256(indices, feature_names),
        "저장된 selected feature hash가 현재 입력과 다릅니다.",
    )
    return np.asarray(indices, dtype=np.int64)


def _validated_indices(indices: Sequence[int], feature_count: int) -> list[int]:
    values = [int(index) for index in indices]
    _require(values == sorted(set(values)), "선택 feature index는 오름차순·중복 없이 저장해야 합니다.")
    _require(values, "선택 feature가 비어 있습니다.")
    _require(values[0] >= 0 and values[-1] < feature_count, "선택 feature index 범위를 벗어났습니다.")
    return values


@dataclass(frozen=True)
class PhiJaccardGreedyPruner:
    """Prune only redundant ``GENE__mutated`` columns from one outer fold.

    Candidate pairs are sorted by Phi, Jaccard, joint mutation count, then
    gene name.  Greedy non-overlap matching prevents a chain of moderately
    related genes from deleting a whole component.  For each matched pair, the
    less prevalent mutation-presence feature is removed; an exact prevalence
    tie removes the lexicographically later gene.
    """

    phi_min: float
    jaccard_min: float
    min_joint_count: int

    def select(
        self,
        features: sparse.csr_matrix,
        targets: np.ndarray,
        feature_names: Sequence[str],
        fold: int,
    ) -> FoldFeatureSelection:
        del targets
        _require(sparse.isspmatrix_csr(features), "feature selector 입력은 CSR sparse matrix여야 합니다.")
        _require(features.shape[1] == len(feature_names), "feature matrix와 feature 이름 수가 다릅니다.")
        _require(features.shape[0] >= 2, "Phi 계산에는 최소 두 학습 행이 필요합니다.")
        _require(self.min_joint_count >= 1, "min_joint_count는 1 이상이어야 합니다.")

        mutation_indices = [
            index for index, name in enumerate(feature_names) if str(name).endswith("__mutated")
        ]
        _require(mutation_indices, "gene__mutated feature를 찾지 못했습니다.")
        presence = features[:, mutation_indices].astype(np.int32, copy=True).tocsr()
        _require((presence.data >= 0).all(), "mutation-presence feature에 음수가 있습니다.")
        presence.eliminate_zeros()
        presence.data = np.ones_like(presence.data, dtype=np.int32)
        prevalence = np.asarray(presence.sum(axis=0)).ravel().astype(np.int64)
        joint = (presence.T @ presence).tocoo()
        row_count = int(presence.shape[0])
        candidates: list[dict[str, Any]] = []

        for left, right, joint_count in zip(joint.row, joint.col, joint.data, strict=True):
            if left >= right or joint_count < self.min_joint_count:
                continue
            left_count = int(prevalence[left])
            right_count = int(prevalence[right])
            denominator = math.sqrt(
                left_count * (row_count - left_count) * right_count * (row_count - right_count)
            )
            if denominator == 0:
                continue
            phi = (row_count * int(joint_count) - left_count * right_count) / denominator
            union = left_count + right_count - int(joint_count)
            jaccard = int(joint_count) / union
            if phi < self.phi_min or jaccard < self.jaccard_min:
                continue
            left_name = str(feature_names[mutation_indices[left]]).removesuffix("__mutated")
            right_name = str(feature_names[mutation_indices[right]]).removesuffix("__mutated")
            candidates.append(
                {
                    "left_local_index": int(left),
                    "right_local_index": int(right),
                    "left_gene": left_name,
                    "right_gene": right_name,
                    "left_prevalence": left_count,
                    "right_prevalence": right_count,
                    "joint_mutation_count": int(joint_count),
                    "phi": float(phi),
                    "jaccard": float(jaccard),
                }
            )

        candidates.sort(
            key=lambda pair: (
                -pair["phi"],
                -pair["jaccard"],
                -pair["joint_mutation_count"],
                pair["left_gene"],
                pair["right_gene"],
            )
        )
        used_local_indices: set[int] = set()
        dropped_global_indices: set[int] = set()
        matched_pairs: list[dict[str, Any]] = []
        for pair in candidates:
            left = pair["left_local_index"]
            right = pair["right_local_index"]
            if left in used_local_indices or right in used_local_indices:
                continue
            used_local_indices.update((left, right))
            if pair["left_prevalence"] < pair["right_prevalence"]:
                drop_local = left
            elif pair["left_prevalence"] > pair["right_prevalence"]:
                drop_local = right
            else:
                drop_local = left if pair["left_gene"] > pair["right_gene"] else right
            drop_global = mutation_indices[drop_local]
            pair["dropped_gene"] = str(feature_names[drop_global]).removesuffix("__mutated")
            pair.pop("left_local_index")
            pair.pop("right_local_index")
            dropped_global_indices.add(drop_global)
            matched_pairs.append(pair)

        selected_indices = tuple(
            index for index in range(features.shape[1]) if index not in dropped_global_indices
        )
        metadata = {
            "selector": "phi_jaccard_greedy_mutation_presence_pruner",
            "fold": int(fold),
            "fit_rows": row_count,
            "parameters": {
                "phi_min": self.phi_min,
                "jaccard_min": self.jaccard_min,
                "min_joint_count": self.min_joint_count,
            },
            "mutation_presence_feature_count": len(mutation_indices),
            "candidate_pair_count": len(candidates),
            "candidate_pairs": [
                {
                    key: value
                    for key, value in pair.items()
                    if key not in {"left_local_index", "right_local_index", "dropped_gene"}
                }
                for pair in candidates
            ],
            "matched_pair_count": len(matched_pairs),
            "dropped_feature_names": [str(feature_names[index]) for index in sorted(dropped_global_indices)],
            "dropped_gene_names": [
                str(feature_names[index]).removesuffix("__mutated") for index in sorted(dropped_global_indices)
            ],
            "matched_pairs": matched_pairs,
        }
        return FoldFeatureSelection(selected_indices, metadata)
