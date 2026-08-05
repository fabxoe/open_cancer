"""Fold-safe class profiles for sparse parser-semantic patient vectors."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FeatureFamilyDescriptor


ProfileMethod = Literal["cosine", "mean_log_likelihood"]
CLASS_SEMANTIC_PROFILE_VERSION = "1.0.0"


def _as_csr_nonnegative(matrix: sparse.spmatrix | np.ndarray) -> sparse.csr_matrix:
    result = sparse.csr_matrix(matrix, dtype=np.float64)
    if result.ndim != 2 or result.shape[1] == 0:
        raise ValueError("환자 semantic 행렬은 하나 이상의 열을 가진 2차원이어야 합니다.")
    if result.data.size and (not np.isfinite(result.data).all() or result.data.min() < 0):
        raise ValueError("class profile 입력은 유한한 비음수 count여야 합니다.")
    return result


def _profile_sha256(array: np.ndarray) -> str:
    contiguous = np.ascontiguousarray(array.astype("<f8", copy=False))
    return hashlib.sha256(contiguous.tobytes()).hexdigest()


@dataclass(frozen=True)
class FittedClassSemanticProfiles:
    """Profiles fitted on one outer-train partition only."""

    descriptor: FeatureFamilyDescriptor
    class_labels: tuple[str, ...]
    method: ProfileMethod
    profiles: np.ndarray
    class_support: tuple[int, ...]
    alpha: float
    include_class_prior: bool
    profile_sha256: str

    def transform(self, matrix: sparse.spmatrix | np.ndarray) -> sparse.csr_matrix:
        values = _as_csr_nonnegative(matrix)
        if values.shape[1] != self.profiles.shape[1]:
            raise ValueError(
                "profile 입력 차원이 다릅니다: "
                f"expected={self.profiles.shape[1]}, actual={values.shape[1]}"
            )

        row_totals = np.asarray(values.sum(axis=1)).ravel()
        nonzero = row_totals > 0
        if self.method == "cosine":
            scores = np.asarray(values @ self.profiles.T, dtype=np.float64)
            row_norms = np.sqrt(np.asarray(values.power(2).sum(axis=1)).ravel())
            scores[nonzero] /= row_norms[nonzero, None]
            scores[~nonzero] = 0.0
        else:
            scores = np.asarray(values @ self.profiles.T, dtype=np.float64)
            scores[nonzero] /= row_totals[nonzero, None]
            scores[~nonzero] = 0.0
            if self.include_class_prior:
                support = np.asarray(self.class_support, dtype=np.float64)
                prior = (support + self.alpha) / (
                    support.sum() + self.alpha * len(self.class_labels)
                )
                scores += np.log(prior)[None, :]
        return sparse.csr_matrix(scores.astype(np.float32))

    def audit_record(self) -> dict[str, object]:
        return {
            "definition_version": self.descriptor.version,
            "method": self.method,
            "class_labels": list(self.class_labels),
            "class_support": dict(zip(self.class_labels, self.class_support, strict=True)),
            "input_dimension": int(self.profiles.shape[1]),
            "output_dimension": len(self.class_labels),
            "alpha": self.alpha,
            "include_class_prior": self.include_class_prior,
            "profile_sha256": self.profile_sha256,
            "feature_names_sha256": self.descriptor.feature_names_sha256,
        }


@dataclass(frozen=True)
class ClassSemanticProfileFamily:
    """Fit class centroids or smoothed token likelihoods without fold leakage."""

    class_labels: tuple[str, ...]
    method: ProfileMethod = "cosine"
    alpha: float = 1.0
    include_class_prior: bool = False
    version: str = CLASS_SEMANTIC_PROFILE_VERSION

    def fit(
        self,
        train_matrix: sparse.spmatrix | np.ndarray,
        target: pd.Series | np.ndarray,
    ) -> FittedClassSemanticProfiles:
        matrix = _as_csr_nonnegative(train_matrix)
        raw_labels = np.asarray(target)
        if raw_labels.ndim != 1 or len(raw_labels) != matrix.shape[0]:
            raise ValueError("target 길이는 outer-train 행 수와 같아야 합니다.")
        if np.issubdtype(raw_labels.dtype, np.integer):
            if raw_labels.size and (
                raw_labels.min() < 0 or raw_labels.max() >= len(self.class_labels)
            ):
                raise ValueError("정수 target이 고정 class order 범위를 벗어났습니다.")
            labels = np.asarray(
                [self.class_labels[int(index)] for index in raw_labels], dtype=str
            )
        else:
            labels = raw_labels.astype(str)
        if not self.class_labels or len(self.class_labels) != len(set(self.class_labels)):
            raise ValueError("고정 class label은 하나 이상이며 중복되지 않아야 합니다.")
        unknown = sorted(set(labels) - set(self.class_labels))
        if unknown:
            raise ValueError(f"고정 class order에 없는 target입니다: {unknown}")
        if self.method not in {"cosine", "mean_log_likelihood"}:
            raise ValueError(f"지원하지 않는 class profile method입니다: {self.method}")
        if self.alpha <= 0:
            raise ValueError("likelihood smoothing alpha는 양수여야 합니다.")

        support: list[int] = []
        rows: list[np.ndarray] = []
        for class_label in self.class_labels:
            mask = labels == class_label
            count = int(mask.sum())
            support.append(count)
            summed = np.asarray(matrix[mask].sum(axis=0)).ravel()
            if self.method == "cosine":
                centroid = summed / max(count, 1)
                norm = float(np.linalg.norm(centroid))
                rows.append(centroid / norm if norm > 0 else np.zeros_like(centroid))
            else:
                probability = (summed + self.alpha) / (
                    summed.sum() + self.alpha * matrix.shape[1]
                )
                rows.append(np.log(probability))

        profiles = np.vstack(rows).astype(np.float64, copy=False)
        prefix = "cosine" if self.method == "cosine" else "mean_log_likelihood"
        feature_names = tuple(
            f"sample__parser_v4_class_profile_{prefix}__{label}"
            for label in self.class_labels
        )
        descriptor = FeatureFamilyDescriptor(
            name=f"parser_v4_class_profile_{prefix}",
            version=self.version,
            fit_scope="fold_train",
            feature_names=feature_names,
        )
        return FittedClassSemanticProfiles(
            descriptor=descriptor,
            class_labels=self.class_labels,
            method=self.method,
            profiles=profiles,
            class_support=tuple(support),
            alpha=float(self.alpha),
            include_class_prior=self.include_class_prior,
            profile_sha256=_profile_sha256(profiles),
        )
