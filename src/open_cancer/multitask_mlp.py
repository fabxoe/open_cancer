"""Shared-encoder MLP with hierarchical auxiliary heads.

The 26-class head is the only inference head.  Auxiliary heads regularize the
shared representation during training and never rewrite final probabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
import random

import numpy as np


class MultitaskMLPError(ValueError):
    """Raised when the multi-task hierarchy contract is violated."""


@dataclass(frozen=True)
class MultitaskMLPConfig:
    input_dim: int
    n_classes: int = 26
    hidden_dim: int = 256
    embedding_dim: int = 128
    dropout: float = 0.20

    def validate(self) -> None:
        if self.input_dim < 1:
            raise MultitaskMLPError("input_dim은 양수여야 합니다.")
        if self.n_classes != 26:
            raise MultitaskMLPError("main head는 고정 26-class여야 합니다.")
        if self.hidden_dim < 1 or self.embedding_dim < 1:
            raise MultitaskMLPError("hidden dimension은 양수여야 합니다.")
        if not 0.0 <= self.dropout < 1.0:
            raise MultitaskMLPError("dropout 범위가 잘못됐습니다.")


def set_multitask_determinism(seed: int) -> None:
    torch = _torch()
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)


def build_multitask_mlp(config: MultitaskMLPConfig):
    """Build one encoder and five heads (main plus four auxiliaries)."""

    config.validate()
    torch = _torch()

    class MultitaskMLP(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.encoder = torch.nn.Sequential(
                torch.nn.Linear(config.input_dim, config.hidden_dim),
                torch.nn.LayerNorm(config.hidden_dim),
                torch.nn.GELU(),
                torch.nn.Dropout(config.dropout),
                torch.nn.Linear(config.hidden_dim, config.embedding_dim),
                torch.nn.LayerNorm(config.embedding_dim),
                torch.nn.GELU(),
                torch.nn.Dropout(config.dropout / 2.0),
            )
            self.main_head = torch.nn.Linear(config.embedding_dim, config.n_classes)
            self.kidney_family_head = torch.nn.Linear(config.embedding_dim, 1)
            self.glioma_family_head = torch.nn.Linear(config.embedding_dim, 1)
            self.kidney_pair_head = torch.nn.Linear(config.embedding_dim, 2)
            self.glioma_pair_head = torch.nn.Linear(config.embedding_dim, 2)

        def forward(self, values):
            if values.ndim != 2 or values.shape[1] != config.input_dim:
                raise MultitaskMLPError(
                    f"입력 shape 오류: {tuple(values.shape)} != (*, {config.input_dim})"
                )
            embedding = self.encoder(values)
            return {
                "embedding": embedding,
                "main": self.main_head(embedding),
                "kidney_family": self.kidney_family_head(embedding).squeeze(-1),
                "glioma_family": self.glioma_family_head(embedding).squeeze(-1),
                "kidney_pair": self.kidney_pair_head(embedding),
                "glioma_pair": self.glioma_pair_head(embedding),
            }

    return MultitaskMLP()


def hierarchy_targets(labels: np.ndarray, class_labels: tuple[str, ...]) -> dict[str, np.ndarray]:
    """Create family and pair targets without duplicating patient rows."""

    labels = np.asarray(labels, dtype=np.int64)
    if labels.ndim != 1:
        raise MultitaskMLPError("labels는 1차원이어야 합니다.")
    names = np.asarray(class_labels, dtype=object)[labels]
    kidney_mask = np.isin(names, ("KIPAN", "KIRC"))
    glioma_mask = np.isin(names, ("GBMLGG", "LGG"))
    return {
        "kidney_family": kidney_mask.astype(np.float32),
        "glioma_family": glioma_mask.astype(np.float32),
        "kidney_pair_mask": kidney_mask,
        "glioma_pair_mask": glioma_mask,
        "kidney_pair": (names == "KIRC").astype(np.int64),
        "glioma_pair": (names == "LGG").astype(np.int64),
    }


def multitask_loss(
    outputs,
    main_targets,
    auxiliary_targets,
    *,
    class_weights=None,
    auxiliary_weight: float = 0.1,
):
    """Return main CE plus a bounded mean of available auxiliary losses."""

    torch = _torch()
    if auxiliary_weight < 0.0:
        raise MultitaskMLPError("auxiliary_weight는 음수일 수 없습니다.")
    main = torch.nn.functional.cross_entropy(
        outputs["main"], main_targets, weight=class_weights
    )
    if auxiliary_weight == 0.0:
        return main, {"main": main.detach(), "auxiliary_mean": main.detach() * 0.0}

    auxiliary = [
        torch.nn.functional.binary_cross_entropy_with_logits(
            outputs["kidney_family"], auxiliary_targets["kidney_family"]
        ),
        torch.nn.functional.binary_cross_entropy_with_logits(
            outputs["glioma_family"], auxiliary_targets["glioma_family"]
        ),
    ]
    for prefix in ("kidney", "glioma"):
        mask = auxiliary_targets[f"{prefix}_pair_mask"]
        if bool(mask.any()):
            auxiliary.append(
                torch.nn.functional.cross_entropy(
                    outputs[f"{prefix}_pair"][mask],
                    auxiliary_targets[f"{prefix}_pair"][mask],
                )
            )
    auxiliary_mean = torch.stack(auxiliary).mean()
    total = main + auxiliary_weight * auxiliary_mean
    return total, {"main": main.detach(), "auxiliary_mean": auxiliary_mean.detach()}


def _torch():
    try:
        import torch
    except ImportError as error:  # pragma: no cover
        raise RuntimeError("multi-task MLP 실행에는 torch가 필요합니다.") from error
    return torch
