from __future__ import annotations

import numpy as np
import pytest

from open_cancer.constants import CLASS_LABELS
from open_cancer.multitask_mlp import (
    MultitaskMLPConfig,
    build_multitask_mlp,
    hierarchy_targets,
    multitask_loss,
)


torch = pytest.importorskip("torch")


def test_hierarchy_targets_do_not_duplicate_rows() -> None:
    indices = np.asarray(
        [CLASS_LABELS.index(label) for label in ("KIPAN", "KIRC", "GBMLGG", "LGG", "BRCA")]
    )
    targets = hierarchy_targets(indices, tuple(CLASS_LABELS))
    assert targets["kidney_pair_mask"].tolist() == [True, True, False, False, False]
    assert targets["glioma_pair_mask"].tolist() == [False, False, True, True, False]
    assert targets["kidney_pair"].tolist()[:2] == [0, 1]
    assert targets["glioma_pair"].tolist()[2:4] == [0, 1]
    assert len(targets["kidney_family"]) == len(indices)


def test_main_inference_shape_is_fixed_26_class() -> None:
    model = build_multitask_mlp(MultitaskMLPConfig(input_dim=16)).eval()
    with torch.no_grad():
        outputs = model(torch.zeros((7, 16), dtype=torch.float32))
    assert outputs["main"].shape == (7, 26)
    assert outputs["kidney_pair"].shape == (7, 2)


def test_zero_auxiliary_weight_equals_main_cross_entropy() -> None:
    model = build_multitask_mlp(MultitaskMLPConfig(input_dim=8))
    values = torch.randn(5, 8)
    labels = torch.tensor([0, 1, 2, 3, 4])
    raw = hierarchy_targets(labels.numpy(), tuple(CLASS_LABELS))
    auxiliary = {
        key: torch.as_tensor(value)
        for key, value in raw.items()
    }
    outputs = model(values)
    loss, parts = multitask_loss(
        outputs, labels, auxiliary, auxiliary_weight=0.0
    )
    expected = torch.nn.functional.cross_entropy(outputs["main"], labels)
    assert torch.allclose(loss, expected)
    assert float(parts["auxiliary_mean"]) == 0.0
