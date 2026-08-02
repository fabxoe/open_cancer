"""Fold-local resampling utilities for canonical experiments.

Resampling is deliberately isolated from feature construction.  A caller may
pass a resampler to the common CV runner, which invokes it only after the
outer-fold training rows have been selected.  Validation and test matrices are
never passed to this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import sparse

from open_cancer.model_runner import ModelRunnerError, OptionalModelDependencyError


@dataclass(frozen=True)
class FoldLocalSmote:
    """Apply standard SMOTE to one outer-fold training matrix only."""

    k_neighbors: int = 5
    sampling_strategy: str = "not majority"
    base_seed: int = 42

    def __post_init__(self) -> None:
        if self.k_neighbors < 1:
            raise ModelRunnerError("SMOTE k_neighbors는 1 이상이어야 합니다.")
        if self.sampling_strategy != "not majority":
            raise ModelRunnerError(
                "이 프로젝트의 표준 SMOTE sampling_strategy는 'not majority'만 허용합니다."
            )

    def __call__(
        self,
        features: sparse.csr_matrix,
        targets: np.ndarray,
        fold: int,
    ) -> tuple[sparse.csr_matrix, np.ndarray, dict[str, Any]]:
        """Return a resampled copy of one fold's training data and its audit data."""
        try:
            from imblearn.over_sampling import SMOTE
        except ImportError as error:
            raise OptionalModelDependencyError(
                "SMOTE 실험 전 `uv sync --frozen`로 imbalanced-learn을 설치하세요."
            ) from error

        if not sparse.isspmatrix_csr(features):
            raise ModelRunnerError("SMOTE 입력 feature는 CSR sparse matrix여야 합니다.")
        if targets.ndim != 1 or len(targets) != features.shape[0]:
            raise ModelRunnerError("SMOTE feature/target 행 계약 불일치")

        seed = self.base_seed + fold
        sampler = SMOTE(
            k_neighbors=self.k_neighbors,
            sampling_strategy=self.sampling_strategy,
            random_state=seed,
        )
        sampled_features, sampled_targets = sampler.fit_resample(features, targets)
        sampled_features = sparse.csr_matrix(sampled_features)
        sampled_targets = np.asarray(sampled_targets, dtype=targets.dtype)
        if sampled_features.shape[1] != features.shape[1]:
            raise ModelRunnerError("SMOTE가 feature 차원을 변경했습니다.")
        if len(sampled_targets) != sampled_features.shape[0]:
            raise ModelRunnerError("SMOTE 결과 feature/target 행 계약 불일치")

        return (
            sampled_features,
            sampled_targets,
            {
                "method": "SMOTE",
                "fold": fold,
                "k_neighbors": self.k_neighbors,
                "sampling_strategy": self.sampling_strategy,
                "random_state": seed,
                "input_rows": int(features.shape[0]),
                "output_rows": int(sampled_features.shape[0]),
            },
        )
