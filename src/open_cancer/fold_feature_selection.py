"""Fold-safe, target-independent feature selection primitives.

The selectors in this module are fit on one outer training fold only.  Their
saved selection documents let a checkpoint inference path replay exactly the
same feature mask without looking at validation or test rows.
"""

from __future__ import annotations

import json
import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence

import numpy as np
from scipy import sparse
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold, StratifiedShuffleSplit

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


@dataclass(frozen=True)
class RareMutationPresencePruner:
    """Remove only mutation-presence features that are too rare in outer-train."""

    min_positive_count: int

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
        _require(self.min_positive_count >= 1, "min_positive_count는 1 이상이어야 합니다.")
        mutation_indices = [
            index for index, name in enumerate(feature_names) if str(name).endswith("__mutated")
        ]
        _require(mutation_indices, "gene__mutated feature를 찾지 못했습니다.")
        presence = features[:, mutation_indices].astype(np.int32, copy=True).tocsr()
        presence.eliminate_zeros()
        presence.data = np.ones_like(presence.data, dtype=np.int32)
        prevalence = np.asarray(presence.sum(axis=0)).ravel().astype(np.int64)
        dropped_global_indices = [
            mutation_indices[local_index]
            for local_index, count in enumerate(prevalence)
            if int(count) < self.min_positive_count
        ]
        selected_indices = tuple(
            index for index in range(features.shape[1]) if index not in set(dropped_global_indices)
        )
        metadata = {
            "selector": "rare_mutation_presence_pruner",
            "fold": int(fold),
            "fit_rows": int(features.shape[0]),
            "parameters": {"min_positive_count": self.min_positive_count},
            "mutation_presence_feature_count": len(mutation_indices),
            "dropped_feature_names": [str(feature_names[index]) for index in dropped_global_indices],
            "dropped_gene_names": [
                str(feature_names[index]).removesuffix("__mutated") for index in dropped_global_indices
            ],
            "dropped_prevalence": {
                str(feature_names[mutation_indices[local_index]]).removesuffix("__mutated"): int(count)
                for local_index, count in enumerate(prevalence)
                if int(count) < self.min_positive_count
            },
        }
        return FoldFeatureSelection(selected_indices, metadata)


def _mutation_presence_indices_and_genes(
    feature_names: Sequence[str],
) -> tuple[list[int], tuple[str, ...]]:
    indices = [
        index for index, name in enumerate(feature_names) if str(name).endswith("__mutated")
    ]
    _require(indices, "gene__mutated feature를 찾지 못했습니다.")
    genes = tuple(str(feature_names[index]).removesuffix("__mutated") for index in indices)
    _require(len(genes) == len(set(genes)), "gene__mutated 유전자명이 중복되었습니다.")
    return indices, genes


def _fit_elastic_net_model(
    features: sparse.csr_matrix,
    targets: np.ndarray,
    *,
    c_value: float,
    l1_ratio: float,
    max_iter: int,
    random_state: int,
) -> LogisticRegression:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        model = LogisticRegression(
            C=float(c_value),
            class_weight="balanced",
            l1_ratio=float(l1_ratio),
            max_iter=int(max_iter),
            random_state=int(random_state),
            solver="saga",
        )
        model.fit(features, targets)
    return model


def _elastic_net_inner_score(
    features: sparse.csr_matrix,
    targets: np.ndarray,
    fit_index: np.ndarray,
    valid_index: np.ndarray,
    *,
    c_value: float,
    l1_ratio: float,
    max_iter: int,
    random_state: int,
) -> tuple[float, float]:
    model = _fit_elastic_net_model(
        features[fit_index], targets[fit_index], c_value=c_value, l1_ratio=l1_ratio,
        max_iter=max_iter, random_state=random_state,
    )
    prediction = model.predict(features[valid_index])
    return c_value, float(f1_score(targets[valid_index], prediction, average="macro", zero_division=0))


def _elastic_net_subsample_support(
    features: sparse.csr_matrix,
    targets: np.ndarray,
    fit_index: np.ndarray,
    *,
    c_value: float,
    l1_ratio: float,
    max_iter: int,
    random_state: int,
) -> np.ndarray:
    model = _fit_elastic_net_model(
        features[fit_index], targets[fit_index], c_value=c_value, l1_ratio=l1_ratio,
        max_iter=max_iter, random_state=random_state,
    )
    return np.flatnonzero(np.any(np.abs(model.coef_) > 1e-12, axis=0))


@dataclass(frozen=True)
class ElasticNetStabilitySelector:
    """Select stable gene blocks with outer-train-only Elastic Net fits.

    The classifier sees only mutation-presence columns while choosing genes.
    The returned mask preserves every v1 channel for selected genes plus all
    non-gene features (sample aggregates and fixed hotspot features).
    """

    c_values: tuple[float, ...]
    l1_ratio: float
    inner_splits: int
    subsample_fraction: float
    repetitions: int
    min_frequency: int
    min_genes: int
    max_genes: int
    seed: int
    max_iter: int = 500
    n_jobs: int = 1

    def select(
        self,
        features: sparse.csr_matrix,
        targets: np.ndarray,
        feature_names: Sequence[str],
        fold: int,
    ) -> FoldFeatureSelection:
        _require(sparse.isspmatrix_csr(features), "feature selector 입력은 CSR sparse matrix여야 합니다.")
        _require(features.shape[1] == len(feature_names), "feature matrix와 feature 이름 수가 다릅니다.")
        _require(0 < self.l1_ratio <= 1, "l1_ratio는 (0, 1] 범위여야 합니다.")
        _require(self.inner_splits >= 2, "inner_splits는 2 이상이어야 합니다.")
        _require(0 < self.subsample_fraction < 1, "subsample_fraction은 (0, 1) 범위여야 합니다.")
        _require(self.repetitions >= 1, "repetitions는 1 이상이어야 합니다.")
        _require(self.min_frequency >= 1, "min_frequency는 1 이상이어야 합니다.")
        _require(1 <= self.min_genes <= self.max_genes, "min_genes/max_genes 범위가 잘못되었습니다.")
        _require(self.n_jobs >= 1, "n_jobs는 1 이상이어야 합니다.")
        c_values = tuple(sorted({float(value) for value in self.c_values}))
        _require(c_values and c_values[0] > 0, "C 후보는 양수여야 합니다.")

        mutation_indices, genes = _mutation_presence_indices_and_genes(feature_names)
        presence = features[:, mutation_indices].astype(np.float64, copy=False).tocsr()
        class_counts = np.bincount(np.asarray(targets, dtype=np.int64))
        _require(
            class_counts.size >= 2 and int(class_counts.min()) >= self.inner_splits,
            "inner StratifiedKFold에 필요한 클래스별 학습 행이 부족합니다.",
        )
        inner_cv = StratifiedKFold(
            n_splits=self.inner_splits,
            shuffle=True,
            random_state=self.seed + int(fold),
        )
        inner_tasks: list[tuple[float, np.ndarray, np.ndarray, int]] = []
        for c_index, c_value in enumerate(c_values):
            for inner_fold, (fit_index, valid_index) in enumerate(inner_cv.split(presence, targets)):
                inner_tasks.append(
                    (
                        c_value,
                        fit_index,
                        valid_index,
                        self.seed + int(fold) * 10_000 + c_index * 100 + inner_fold,
                    )
                )
        from joblib import Parallel, delayed

        inner_results = Parallel(n_jobs=self.n_jobs, prefer="processes")(
            delayed(_elastic_net_inner_score)(
                presence, targets, fit_index, valid_index,
                c_value=c_value, l1_ratio=self.l1_ratio, max_iter=self.max_iter,
                random_state=random_state,
            )
            for c_value, fit_index, valid_index, random_state in inner_tasks
        )
        inner_scores: dict[float, list[float]] = {value: [] for value in c_values}
        for c_value, score in inner_results:
            inner_scores[c_value].append(score)
        mean_scores = {value: float(np.mean(scores)) for value, scores in inner_scores.items()}
        best_value = max(c_values, key=lambda value: (mean_scores[value], -value))
        best_scores = np.asarray(inner_scores[best_value], dtype=np.float64)
        one_se = float(best_scores.std(ddof=1) / math.sqrt(self.inner_splits))
        eligible = [value for value in c_values if mean_scores[value] >= mean_scores[best_value] - one_se]
        selected_c = min(eligible)

        subsample_indices: list[tuple[np.ndarray, int]] = []
        for repetition in range(self.repetitions):
            split = StratifiedShuffleSplit(
                n_splits=1,
                train_size=self.subsample_fraction,
                random_state=self.seed + int(fold) * 100 + repetition,
            )
            fit_index, _ = next(split.split(presence, targets))
            subsample_indices.append(
                (fit_index, self.seed + int(fold) * 100 + repetition)
            )
        supports = Parallel(n_jobs=self.n_jobs, prefer="processes")(
            delayed(_elastic_net_subsample_support)(
                presence, targets, fit_index,
                c_value=selected_c, l1_ratio=self.l1_ratio, max_iter=self.max_iter,
                random_state=random_state,
            )
            for fit_index, random_state in subsample_indices
        )
        frequencies = np.zeros(len(genes), dtype=np.int64)
        for selected_local in supports:
            frequencies[selected_local] += 1

        ranked_local = sorted(range(len(genes)), key=lambda index: (-int(frequencies[index]), genes[index]))
        stable_local = [index for index in ranked_local if int(frequencies[index]) >= self.min_frequency]
        if len(stable_local) < self.min_genes:
            stable_local = ranked_local[: self.min_genes]
        else:
            stable_local = stable_local[: self.max_genes]
        selected_genes = tuple(genes[index] for index in stable_local)
        selected_gene_set = set(selected_genes)
        raw_gene_set = set(genes)
        selected_indices = tuple(
            index
            for index, name in enumerate(feature_names)
            if str(name).split("__", 1)[0] not in raw_gene_set
            or str(name).split("__", 1)[0] in selected_gene_set
        )
        _require(selected_indices, "Elastic Net selector가 빈 feature mask를 만들었습니다.")
        metadata = {
            "selector": "elastic_net_stability_selection",
            "fold": int(fold),
            "fit_rows": int(features.shape[0]),
            "parameters": {
                "c_values": list(c_values),
                "l1_ratio": self.l1_ratio,
                "inner_splits": self.inner_splits,
                "subsample_fraction": self.subsample_fraction,
                "repetitions": self.repetitions,
                "min_frequency": self.min_frequency,
                "min_genes": self.min_genes,
                "max_genes": self.max_genes,
                "seed": self.seed,
                "max_iter": self.max_iter,
                "n_jobs": self.n_jobs,
            },
            "mutation_presence_feature_count": len(genes),
            "inner_cv_macro_f1": {str(value): mean_scores[value] for value in c_values},
            "best_mean_c": best_value,
            "best_mean_one_se": one_se,
            "selected_c": selected_c,
            "selected_gene_count": len(selected_genes),
            "selected_gene_names": list(selected_genes),
            "selection_frequency": {genes[index]: int(frequencies[index]) for index in ranked_local},
            "selected_feature_count": len(selected_indices),
            "retained_non_gene_feature_count": sum(
                1 for name in feature_names if str(name).split("__", 1)[0] not in raw_gene_set
            ),
        }
        return FoldFeatureSelection(selected_indices, metadata)
