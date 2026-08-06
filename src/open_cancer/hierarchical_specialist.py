"""Probability-preserving expansion of merged cancer superclass outputs."""

from __future__ import annotations

import numpy as np


def split_merged_probabilities(
    merged_probability: np.ndarray,
    *,
    merged_class_labels: tuple[str, ...],
    output_class_labels: tuple[str, ...],
    kipan_conditional: np.ndarray,
    gbmlgg_conditional: np.ndarray,
) -> np.ndarray:
    """Expand two merged superclass probabilities into the original 26 labels.

    Conditional columns must be ordered `(KIPAN, KIRC)` and `(GBMLGG, LGG)`.
    All unrelated class probabilities are copied exactly.
    """
    base = np.asarray(merged_probability, dtype=np.float64)
    kipan = np.asarray(kipan_conditional, dtype=np.float64)
    gbmlgg = np.asarray(gbmlgg_conditional, dtype=np.float64)
    if base.ndim != 2 or base.shape[1] != len(merged_class_labels):
        raise ValueError("병합 확률 형상이 class order와 다릅니다.")
    if kipan.shape != (base.shape[0], 2) or gbmlgg.shape != (base.shape[0], 2):
        raise ValueError("specialist 조건부 확률은 (행 수, 2)여야 합니다.")
    for name, values in (("base", base), ("kipan", kipan), ("gbmlgg", gbmlgg)):
        if not np.isfinite(values).all() or (values < 0).any():
            raise ValueError(f"{name} 확률에 음수·NaN·무한대가 있습니다.")
        if not np.allclose(values.sum(axis=1), 1.0, atol=1e-6, rtol=1e-6):
            raise ValueError(f"{name} 확률 행합이 1이 아닙니다.")
    required_merged = {"KIPAN", "GBMLGG"}
    if not required_merged <= set(merged_class_labels):
        raise ValueError("병합 class order에 KIPAN 또는 GBMLGG가 없습니다.")
    if not {"KIPAN", "KIRC", "GBMLGG", "LGG"} <= set(output_class_labels):
        raise ValueError("출력 class order에 원래 혼돈쌍 라벨이 없습니다.")

    output = np.zeros((base.shape[0], len(output_class_labels)), dtype=np.float64)
    merged_index = {label: index for index, label in enumerate(merged_class_labels)}
    output_index = {label: index for index, label in enumerate(output_class_labels)}
    for label in merged_class_labels:
        if label not in required_merged:
            output[:, output_index[label]] = base[:, merged_index[label]]
    kipan_mass = base[:, merged_index["KIPAN"]]
    gbmlgg_mass = base[:, merged_index["GBMLGG"]]
    output[:, output_index["KIPAN"]] = kipan_mass * kipan[:, 0]
    output[:, output_index["KIRC"]] = kipan_mass * kipan[:, 1]
    output[:, output_index["GBMLGG"]] = gbmlgg_mass * gbmlgg[:, 0]
    output[:, output_index["LGG"]] = gbmlgg_mass * gbmlgg[:, 1]
    if not np.allclose(output.sum(axis=1), 1.0, atol=1e-6, rtol=1e-6):
        raise ValueError("복원된 26-class 확률 행합이 1이 아닙니다.")
    return output.astype(np.float32)
