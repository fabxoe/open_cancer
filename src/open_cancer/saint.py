"""Small, auditable SAINT components for parser-v4 semantic features."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any

import numpy as np


class SaintError(ValueError):
    """Raised when the SAINT input or architecture contract is invalid."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SaintError(message)


@dataclass(frozen=True)
class SaintConfig:
    input_dim: int
    binary_indices: tuple[int, ...]
    continuous_indices: tuple[int, ...]
    n_classes: int = 26
    token_dim: int = 32
    depth: int = 2
    heads: int = 4
    dropout: float = 0.1
    use_row_attention: bool = True

    def validate(self) -> None:
        _require(self.input_dim >= 1, "input_dim은 양수여야 합니다.")
        _require(self.n_classes >= 2, "n_classes는 2 이상이어야 합니다.")
        _require(self.token_dim >= 4, "token_dim은 4 이상이어야 합니다.")
        _require(self.depth >= 1, "depth는 1 이상이어야 합니다.")
        _require(self.heads >= 1, "heads는 1 이상이어야 합니다.")
        _require(
            self.token_dim % self.heads == 0,
            "token_dim은 heads로 나누어떨어져야 합니다.",
        )
        _require(0.0 <= self.dropout < 1.0, "dropout 범위가 잘못됐습니다.")
        binary = tuple(int(value) for value in self.binary_indices)
        continuous = tuple(int(value) for value in self.continuous_indices)
        _require(len(set(binary)) == len(binary), "binary index가 중복됩니다.")
        _require(
            len(set(continuous)) == len(continuous),
            "continuous index가 중복됩니다.",
        )
        _require(
            not set(binary).intersection(continuous),
            "binary와 continuous index가 겹칩니다.",
        )
        _require(
            set(binary).union(continuous) == set(range(self.input_dim)),
            "binary와 continuous index가 전체 입력 열을 정확히 분할해야 합니다.",
        )


def set_saint_determinism(seed: int) -> None:
    """Set deterministic seeds before constructing a model."""

    torch = _torch()
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)


def build_saint_model(config: SaintConfig):
    """Build a compact SAINT-like row/column attention classifier.

    Binary events use per-feature 0/1 embeddings. Continuous burden/count
    columns use a learned per-feature scalar projection. Column attention is
    applied within each sample and row attention across the fixed mini-batch.
    """

    config.validate()
    torch = _torch()

    class SaintModel(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            feature_count = config.input_dim
            token_dim = config.token_dim
            self.config = config
            self.feature_bias = torch.nn.Parameter(
                torch.empty(feature_count, token_dim)
            )
            self.continuous_weight = torch.nn.Parameter(
                torch.empty(feature_count, token_dim)
            )
            self.binary_embedding = torch.nn.Parameter(
                torch.empty(feature_count, 2, token_dim)
            )
            binary_mask = torch.zeros(feature_count, dtype=torch.bool)
            if config.binary_indices:
                binary_mask[list(config.binary_indices)] = True
            self.register_buffer("binary_mask", binary_mask, persistent=True)
            self.column_layers = torch.nn.ModuleList(
                [_attention_layer(torch, config) for _ in range(config.depth)]
            )
            self.row_layers = torch.nn.ModuleList(
                [_attention_layer(torch, config) for _ in range(config.depth)]
                if config.use_row_attention
                else []
            )
            self.output_norm = torch.nn.LayerNorm(token_dim)
            self.classifier = torch.nn.Linear(token_dim, config.n_classes)
            self.reset_parameters()

        def reset_parameters(self) -> None:
            torch.nn.init.normal_(self.feature_bias, std=0.02)
            torch.nn.init.normal_(self.continuous_weight, std=0.02)
            torch.nn.init.normal_(self.binary_embedding, std=0.02)
            torch.nn.init.xavier_uniform_(self.classifier.weight)
            torch.nn.init.zeros_(self.classifier.bias)

        def tokenize(self, values):
            if values.ndim != 2 or values.shape[1] != config.input_dim:
                raise SaintError(
                    "SAINT 입력 shape가 잘못됐습니다: "
                    f"{tuple(values.shape)} != (*, {config.input_dim})"
                )
            if not torch.isfinite(values).all():
                raise SaintError("SAINT 입력에 NaN 또는 Inf가 있습니다.")
            continuous_tokens = (
                values.unsqueeze(-1) * self.continuous_weight.unsqueeze(0)
                + self.feature_bias.unsqueeze(0)
            )
            binary_values = values.round().to(dtype=torch.long).clamp(0, 1)
            feature_indices = torch.arange(
                config.input_dim, device=values.device
            ).unsqueeze(0)
            binary_tokens = self.binary_embedding[
                feature_indices, binary_values
            ]
            return torch.where(
                self.binary_mask.view(1, -1, 1),
                binary_tokens,
                continuous_tokens,
            )

        def forward(self, values):
            tokens = self.tokenize(values)
            for index, column_layer in enumerate(self.column_layers):
                tokens = column_layer(tokens)
                if config.use_row_attention:
                    # feature axis acts as independent batches; the fixed
                    # mini-batch axis becomes the row-attention sequence.
                    tokens = self.row_layers[index](tokens.transpose(0, 1)).transpose(
                        0, 1
                    )
            pooled = self.output_norm(tokens.mean(dim=1))
            return self.classifier(pooled)

    return SaintModel()


def saint_parameter_count(model: Any) -> int:
    return int(sum(parameter.numel() for parameter in model.parameters()))


def _attention_layer(torch, config: SaintConfig):
    return torch.nn.TransformerEncoderLayer(
        d_model=config.token_dim,
        nhead=config.heads,
        dim_feedforward=config.token_dim * 2,
        dropout=config.dropout,
        activation="gelu",
        batch_first=True,
        norm_first=True,
    )


def _torch():
    try:
        import torch
    except ImportError as error:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "SAINT 실행에는 experiment group의 torch가 필요합니다."
        ) from error
    return torch
