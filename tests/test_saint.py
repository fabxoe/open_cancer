from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from open_cancer.saint import (  # noqa: E402
    SaintConfig,
    SaintError,
    build_saint_model,
    saint_parameter_count,
    set_saint_determinism,
)


def _config(*, row_attention: bool = True) -> SaintConfig:
    return SaintConfig(
        input_dim=8,
        binary_indices=(2, 3, 4, 5, 6, 7),
        continuous_indices=(0, 1),
        n_classes=4,
        token_dim=8,
        depth=2,
        heads=2,
        dropout=0.0,
        use_row_attention=row_attention,
    )


def _values() -> torch.Tensor:
    values = np.asarray(
        [
            [2, 1, 1, 0, 1, 0, 0, 1],
            [1, 3, 0, 1, 0, 1, 1, 0],
            [4, 0, 1, 1, 0, 0, 1, 0],
            [2, 2, 0, 0, 1, 1, 0, 1],
        ],
        dtype=np.float32,
    )
    return torch.from_numpy(values)


def test_config_requires_complete_non_overlapping_type_partition() -> None:
    with pytest.raises(SaintError, match="정확히 분할"):
        SaintConfig(
            input_dim=4,
            binary_indices=(0, 1),
            continuous_indices=(2,),
        ).validate()
    with pytest.raises(SaintError, match="겹칩니다"):
        SaintConfig(
            input_dim=4,
            binary_indices=(0, 1),
            continuous_indices=(1, 2, 3),
        ).validate()


@pytest.mark.parametrize("row_attention", [False, True])
def test_forward_shape_and_finite_training_step(row_attention: bool) -> None:
    set_saint_determinism(42)
    model = build_saint_model(_config(row_attention=row_attention))
    values = _values()
    labels = torch.tensor([0, 1, 2, 3], dtype=torch.long)
    logits = model(values)
    assert logits.shape == (4, 4)
    assert torch.isfinite(logits).all()
    loss = torch.nn.functional.cross_entropy(logits, labels)
    loss.backward()
    assert torch.isfinite(loss)
    assert all(
        parameter.grad is None or torch.isfinite(parameter.grad).all()
        for parameter in model.parameters()
    )
    assert saint_parameter_count(model) > 0


def test_eval_inference_is_exactly_deterministic_for_fixed_batch() -> None:
    set_saint_determinism(77)
    model = build_saint_model(_config()).eval()
    values = _values()
    with torch.no_grad():
        first = model(values)
        second = model(values.clone())
    assert torch.equal(first, second)


def test_rebuilding_with_same_seed_reproduces_logits() -> None:
    values = _values()
    set_saint_determinism(123)
    first = build_saint_model(_config()).eval()
    with torch.no_grad():
        first_logits = first(values)
    set_saint_determinism(123)
    second = build_saint_model(_config()).eval()
    with torch.no_grad():
        second_logits = second(values)
    assert torch.equal(first_logits, second_logits)


def test_invalid_shape_and_nonfinite_input_are_rejected() -> None:
    model = build_saint_model(_config())
    with pytest.raises(SaintError, match="shape"):
        model(torch.ones((4, 7), dtype=torch.float32))
    values = _values()
    values[0, 0] = float("nan")
    with pytest.raises(SaintError, match="NaN"):
        model(values)
