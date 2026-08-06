from __future__ import annotations

import numpy as np
import pytest

from open_cancer.constants import CLASS_LABELS
from open_cancer.hierarchical_specialist import split_merged_probabilities


def test_split_merged_probabilities_preserves_mass_and_unrelated_classes() -> None:
    merged = tuple(label for label in CLASS_LABELS if label not in {"KIRC", "LGG"})
    probability = np.zeros((1, len(merged)), dtype=np.float64)
    probability[0, merged.index("KIPAN")] = 0.4
    probability[0, merged.index("GBMLGG")] = 0.3
    probability[0, merged.index("BRCA")] = 0.3

    output = split_merged_probabilities(
        probability,
        merged_class_labels=merged,
        output_class_labels=CLASS_LABELS,
        kipan_conditional=np.array([[0.25, 0.75]]),
        gbmlgg_conditional=np.array([[0.8, 0.2]]),
    )

    assert output.sum() == pytest.approx(1.0)
    assert output[0, CLASS_LABELS.index("KIPAN")] == pytest.approx(0.1)
    assert output[0, CLASS_LABELS.index("KIRC")] == pytest.approx(0.3)
    assert output[0, CLASS_LABELS.index("GBMLGG")] == pytest.approx(0.24)
    assert output[0, CLASS_LABELS.index("LGG")] == pytest.approx(0.06)
    assert output[0, CLASS_LABELS.index("BRCA")] == pytest.approx(0.3)


def test_split_rejects_non_normalized_specialist_probability() -> None:
    merged = tuple(label for label in CLASS_LABELS if label not in {"KIRC", "LGG"})
    base = np.full((1, len(merged)), 1 / len(merged))
    with pytest.raises(ValueError, match="행합"):
        split_merged_probabilities(
            base,
            merged_class_labels=merged,
            output_class_labels=CLASS_LABELS,
            kipan_conditional=np.array([[0.2, 0.2]]),
            gbmlgg_conditional=np.array([[0.5, 0.5]]),
        )
