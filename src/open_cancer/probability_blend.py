"""Validated probability blending for fixed experiment ensembles."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


class ProbabilityBlendError(ValueError):
    """Raised when component predictions cannot be blended safely."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProbabilityBlendError(message)


def validate_weights(weights: Sequence[float], component_count: int) -> np.ndarray:
    """Return fixed float64 weights after strict validation."""
    values = np.asarray(weights, dtype=np.float64)
    _require(values.ndim == 1, "앙상블 가중치는 1차원이어야 합니다.")
    _require(len(values) == component_count, "컴포넌트 수와 가중치 수가 다릅니다.")
    _require(np.isfinite(values).all(), "앙상블 가중치에 유한하지 않은 값이 있습니다.")
    _require((values >= 0).all(), "앙상블 가중치는 음수일 수 없습니다.")
    _require(np.isclose(values.sum(), 1.0, atol=1e-12, rtol=0), "앙상블 가중치 합은 1이어야 합니다.")
    return values


def blend_probability_frames(
    frames: Sequence[pd.DataFrame],
    *,
    weights: Sequence[float],
    metadata_columns: Sequence[str],
    probability_columns: Sequence[str],
    ignored_columns: Sequence[str] = (),
) -> pd.DataFrame:
    """Blend aligned probability frames while preserving reference metadata."""
    _require(len(frames) >= 2, "확률 blend에는 컴포넌트가 두 개 이상 필요합니다.")
    resolved_weights = validate_weights(weights, len(frames))
    metadata = list(metadata_columns)
    probabilities = list(probability_columns)
    ignored = list(ignored_columns)
    reference = frames[0]
    reference_columns = list(reference.columns)
    reference_non_probability_columns = [
        column for column in reference_columns if column not in probabilities
    ]
    _require(
        reference_columns[-len(probabilities) :] == probabilities,
        "첫 컴포넌트의 확률 열 또는 열 순서가 계약과 다릅니다.",
    )
    _require(
        set(reference_non_probability_columns) == set(metadata + ignored)
        and len(reference_non_probability_columns) == len(metadata + ignored),
        "첫 컴포넌트의 메타데이터 열이 계약과 다릅니다.",
    )
    _require(not reference[metadata[0]].duplicated().any(), "첫 컴포넌트 ID가 중복됐습니다.")

    matrices: list[np.ndarray] = []
    for index, frame in enumerate(frames):
        _require(list(frame.columns) == reference_columns, f"컴포넌트 {index}의 열 또는 열 순서가 다릅니다.")
        _require(len(frame) == len(reference), f"컴포넌트 {index}의 행 수가 다릅니다.")
        _require(
            frame.loc[:, metadata].equals(reference.loc[:, metadata]),
            f"컴포넌트 {index}의 ID·정답·fold 메타데이터가 다릅니다.",
        )
        matrix = frame.loc[:, probabilities].to_numpy(dtype=np.float64)
        _require(np.isfinite(matrix).all(), f"컴포넌트 {index} 확률에 NaN 또는 무한대가 있습니다.")
        _require(((matrix >= 0) & (matrix <= 1)).all(), f"컴포넌트 {index} 확률이 [0, 1] 범위를 벗어났습니다.")
        _require(
            np.allclose(matrix.sum(axis=1), 1.0, atol=1e-5, rtol=1e-5),
            f"컴포넌트 {index} 확률의 행 합이 1이 아닙니다.",
        )
        matrices.append(matrix)

    blended = np.zeros_like(matrices[0], dtype=np.float64)
    for weight, matrix in zip(resolved_weights, matrices, strict=True):
        blended += weight * matrix
    _require(np.allclose(blended.sum(axis=1), 1.0, atol=1e-5, rtol=1e-5), "blend 확률의 행 합이 1이 아닙니다.")

    output = reference.loc[:, metadata].copy()
    output.loc[:, probabilities] = blended
    return output
