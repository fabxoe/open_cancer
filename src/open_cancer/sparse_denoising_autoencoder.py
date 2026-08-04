"""Fold-safe sparse denoising autoencoder for gene mutation presence."""

from __future__ import annotations

import csv
import hashlib
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from scipy import sparse


@dataclass(frozen=True)
class AutoencoderConfig:
    input_dim: int = 4384
    hidden_dim: int = 128
    latent_dim: int = 64
    positive_mask_rate: float = 0.20
    positive_weight_cap: float = 50.0
    dropout: float = 0.10
    weight_decay: float = 1e-4
    gradient_clip_norm: float = 5.0
    learning_rate: float = 1e-3
    batch_size: int = 128
    max_epochs: int = 40
    early_stopping_patience: int = 6
    seed: int = 42
    device: str = "auto"


def load_gene_presence_csv(
    path: Path, *, has_labels: bool
) -> tuple[sparse.csr_matrix, list[str], list[str], list[str] | None]:
    """Stream a competition CSV into a binary CSR gene-presence matrix."""

    rows: list[int] = []
    columns: list[int] = []
    ids: list[str] = []
    labels: list[str] | None = [] if has_labels else None
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        prefix = ["ID", "SUBCLASS"] if has_labels else ["ID"]
        if header[: len(prefix)] != prefix:
            raise ValueError(f"{path}: expected prefix {prefix}")
        genes = header[len(prefix) :]
        for row_index, row in enumerate(reader):
            if len(row) != len(header):
                raise ValueError(f"{path}: row {row_index + 2} width mismatch")
            ids.append(row[0])
            if labels is not None:
                labels.append(row[1])
            offset = 2 if has_labels else 1
            for column_index, value in enumerate(row[offset:]):
                if value not in {"", "WT"}:
                    rows.append(row_index)
                    columns.append(column_index)
    matrix = sparse.csr_matrix(
        (
            np.ones(len(rows), dtype=np.float32),
            (np.asarray(rows), np.asarray(columns)),
        ),
        shape=(len(ids), len(genes)),
        dtype=np.float32,
    )
    return matrix, ids, genes, labels


def deterministic_holdout(
    indices: Sequence[int], *, fraction: float, seed: int
) -> tuple[np.ndarray, np.ndarray]:
    """Split outer-train indices without using target labels."""

    if not 0.0 < fraction < 1.0:
        raise ValueError("holdout fraction must be between zero and one")
    values = np.asarray(indices, dtype=np.int64)
    if values.size < 2:
        raise ValueError("at least two rows are required")
    rng = np.random.default_rng(seed)
    shuffled = values.copy()
    rng.shuffle(shuffled)
    holdout_size = max(1, int(round(values.size * fraction)))
    return np.sort(shuffled[holdout_size:]), np.sort(shuffled[:holdout_size])


def train_autoencoder(
    matrix: sparse.csr_matrix,
    train_indices: Sequence[int],
    validation_indices: Sequence[int],
    *,
    config: AutoencoderConfig,
    checkpoint_path: Path,
) -> dict[str, Any]:
    """Fit only on supplied outer-train rows and save the best checkpoint."""

    torch = _torch()
    _validate_config(config, matrix.shape[1])
    _set_determinism(torch, config.seed)
    device = _resolve_device(torch, config.device)
    model = _build_model(torch, config).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    train_indices_array = np.asarray(train_indices, dtype=np.int64)
    validation_indices_array = np.asarray(validation_indices, dtype=np.int64)
    positive_entries = int(matrix[train_indices_array].nnz)
    total_entries = int(train_indices_array.size * matrix.shape[1])
    raw_positive_weight = (total_entries - positive_entries) / max(positive_entries, 1)
    positive_weight = min(config.positive_weight_cap, raw_positive_weight)
    loss_function = torch.nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor(positive_weight, dtype=torch.float32, device=device)
    )

    history: list[dict[str, float | int]] = []
    best_loss = float("inf")
    best_epoch = -1
    best_state: dict[str, Any] | None = None
    epochs_without_improvement = 0
    generator = torch.Generator(device="cpu").manual_seed(config.seed)
    for epoch in range(config.max_epochs):
        model.train()
        permutation = torch.randperm(train_indices_array.size, generator=generator).numpy()
        training_losses: list[float] = []
        for start in range(0, permutation.size, config.batch_size):
            batch_indices = train_indices_array[permutation[start : start + config.batch_size]]
            target = _dense_batch(torch, matrix, batch_indices, device)
            corrupted = _mask_positive_entries(
                torch, target, rate=config.positive_mask_rate, generator=generator
            )
            optimizer.zero_grad(set_to_none=True)
            logits, _ = model(corrupted)
            loss = loss_function(logits, target)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.gradient_clip_norm)
            optimizer.step()
            training_losses.append(float(loss.detach().cpu()))

        validation_loss = _reconstruction_loss(
            torch,
            model,
            matrix,
            validation_indices_array,
            loss_function,
            config.batch_size,
            device,
        )
        history.append(
            {
                "epoch": epoch,
                "train_loss": float(np.mean(training_losses)),
                "validation_loss": validation_loss,
            }
        )
        if validation_loss < best_loss - 1e-7:
            best_loss = validation_loss
            best_epoch = epoch
            best_state = {
                key: value.detach().cpu().clone() for key, value in model.state_dict().items()
            }
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= config.early_stopping_patience:
                break

    if best_state is None:
        raise RuntimeError("autoencoder training did not produce a checkpoint")
    model.load_state_dict(best_state)
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "config": asdict(config),
            "state_dict": best_state,
            "input_dim": matrix.shape[1],
            "best_epoch": best_epoch,
            "best_validation_loss": best_loss,
            "positive_weight": positive_weight,
        },
        checkpoint_path,
    )
    audit = reconstruction_audit(
        matrix,
        validation_indices_array,
        config=config,
        checkpoint_path=checkpoint_path,
    )
    return {
        "config": asdict(config),
        "device": str(device),
        "train_rows": int(train_indices_array.size),
        "validation_rows": int(validation_indices_array.size),
        "positive_entries": positive_entries,
        "positive_weight_raw": raw_positive_weight,
        "positive_weight_used": positive_weight,
        "best_epoch": best_epoch,
        "best_validation_loss": best_loss,
        "epochs_completed": len(history),
        "history": history,
        "validation_audit": audit,
        "checkpoint_sha256": _sha256(checkpoint_path),
    }


def transform_autoencoder(
    matrix: sparse.csr_matrix,
    indices: Sequence[int],
    *,
    checkpoint_path: Path,
    device: str = "auto",
) -> np.ndarray:
    """Transform rows with a saved encoder without fitting on them."""

    torch = _torch()
    payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    config = AutoencoderConfig(**payload["config"])
    selected_device = _resolve_device(torch, device)
    model = _build_model(torch, config).to(selected_device)
    model.load_state_dict(payload["state_dict"])
    model.eval()
    output: list[np.ndarray] = []
    values = np.asarray(indices, dtype=np.int64)
    with torch.no_grad():
        for start in range(0, values.size, config.batch_size):
            batch = _dense_batch(
                torch, matrix, values[start : start + config.batch_size], selected_device
            )
            latent = model.encode(batch)
            output.append(latent.detach().cpu().numpy().astype(np.float32))
    return np.vstack(output) if output else np.empty((0, config.latent_dim), dtype=np.float32)


def reconstruction_audit(
    matrix: sparse.csr_matrix,
    indices: Sequence[int],
    *,
    config: AutoencoderConfig,
    checkpoint_path: Path,
) -> dict[str, float]:
    """Measure weighted reconstruction and zero-collapse diagnostics."""

    torch = _torch()
    payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    device = _resolve_device(torch, config.device)
    model = _build_model(torch, config).to(device)
    model.load_state_dict(payload["state_dict"])
    model.eval()
    values = np.asarray(indices, dtype=np.int64)
    positive_probabilities: list[np.ndarray] = []
    negative_probabilities: list[np.ndarray] = []
    unweighted_losses: list[float] = []
    with torch.no_grad():
        for start in range(0, values.size, config.batch_size):
            target = _dense_batch(
                torch, matrix, values[start : start + config.batch_size], device
            )
            logits, _ = model(target)
            probabilities = torch.sigmoid(logits)
            unweighted_losses.append(
                float(torch.nn.functional.binary_cross_entropy(probabilities, target).cpu())
            )
            target_bool = target.bool()
            positive_probabilities.append(probabilities[target_bool].cpu().numpy())
            negative_probabilities.append(probabilities[~target_bool].cpu().numpy())
    positive = np.concatenate(positive_probabilities)
    negative = np.concatenate(negative_probabilities)
    return {
        "unweighted_bce": float(np.mean(unweighted_losses)),
        "mean_probability_true_positive": float(positive.mean()),
        "mean_probability_true_zero": float(negative.mean()),
        "probability_separation": float(positive.mean() - negative.mean()),
        "zero_collapse": bool(positive.mean() <= negative.mean()),
    }


def prevalence_baseline_bce(
    matrix: sparse.csr_matrix,
    fit_indices: Sequence[int],
    evaluation_indices: Sequence[int],
    *,
    epsilon: float = 1e-6,
    batch_size: int = 256,
) -> float:
    """Score a gene-wise prevalence baseline fit without evaluation rows."""

    fit = np.asarray(fit_indices, dtype=np.int64)
    evaluation = np.asarray(evaluation_indices, dtype=np.int64)
    if fit.size == 0 or evaluation.size == 0:
        raise ValueError("fit and evaluation indices must not be empty")
    prevalence = np.asarray(matrix[fit].mean(axis=0)).ravel().astype(np.float64)
    prevalence = np.clip(prevalence, epsilon, 1.0 - epsilon)
    loss_sum = 0.0
    entry_count = 0
    for start in range(0, evaluation.size, batch_size):
        dense = matrix[evaluation[start : start + batch_size]].toarray().astype(
            np.float64, copy=False
        )
        loss = -(dense * np.log(prevalence) + (1.0 - dense) * np.log1p(-prevalence))
        loss_sum += float(loss.sum())
        entry_count += int(loss.size)
    return float(loss_sum / entry_count)


def latent_audit(latent: np.ndarray, burden: np.ndarray) -> dict[str, Any]:
    """Audit constant dimensions and burden replication."""

    means = latent.mean(axis=0)
    variances = latent.var(axis=0)
    correlations = []
    for column in range(latent.shape[1]):
        if variances[column] <= 1e-12 or np.var(burden) <= 1e-12:
            correlations.append(0.0)
        else:
            correlations.append(float(np.corrcoef(latent[:, column], burden)[0, 1]))
    return {
        "dimension": int(latent.shape[1]),
        "near_constant_dimensions": int(np.sum(variances <= 1e-8)),
        "max_abs_burden_correlation": float(np.max(np.abs(correlations))),
        "mean_sha256": hashlib.sha256(means.astype(np.float32).tobytes()).hexdigest(),
        "variance_sha256": hashlib.sha256(
            variances.astype(np.float32).tobytes()
        ).hexdigest(),
        "means": means.tolist(),
        "variances": variances.tolist(),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _torch():
    try:
        import torch
    except ModuleNotFoundError as error:
        raise RuntimeError(
            "PyTorch가 필요합니다. uv sync --frozen --group experiment를 실행하세요."
        ) from error
    return torch


def _build_model(torch, config: AutoencoderConfig):
    class Model(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.encoder = torch.nn.Sequential(
                torch.nn.Linear(config.input_dim, config.hidden_dim),
                torch.nn.ReLU(),
                torch.nn.Dropout(config.dropout),
                torch.nn.Linear(config.hidden_dim, config.latent_dim),
            )
            self.decoder = torch.nn.Sequential(
                torch.nn.Linear(config.latent_dim, config.hidden_dim),
                torch.nn.ReLU(),
                torch.nn.Dropout(config.dropout),
                torch.nn.Linear(config.hidden_dim, config.input_dim),
            )

        def encode(self, values):
            return self.encoder(values)

        def forward(self, values):
            latent = self.encode(values)
            return self.decoder(latent), latent

    return Model()


def _set_determinism(torch, seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)


def _resolve_device(torch, requested: str):
    if requested != "auto":
        return torch.device(requested)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _dense_batch(torch, matrix, indices: np.ndarray, device):
    dense = matrix[indices].toarray().astype(np.float32, copy=False)
    return torch.from_numpy(dense).to(device)


def _mask_positive_entries(torch, target, *, rate: float, generator):
    random_values = torch.rand(target.shape, generator=generator, device="cpu").to(
        target.device
    )
    mask = (target > 0) & (random_values < rate)
    corrupted = target.clone()
    corrupted[mask] = 0.0
    return corrupted


def _reconstruction_loss(
    torch, model, matrix, indices, loss_function, batch_size: int, device
) -> float:
    model.eval()
    losses: list[float] = []
    with torch.no_grad():
        for start in range(0, indices.size, batch_size):
            target = _dense_batch(
                torch, matrix, indices[start : start + batch_size], device
            )
            logits, _ = model(target)
            losses.append(float(loss_function(logits, target).cpu()))
    return float(np.mean(losses))


def _validate_config(config: AutoencoderConfig, actual_input_dim: int) -> None:
    if actual_input_dim != config.input_dim:
        raise ValueError(
            f"input dimension mismatch: config={config.input_dim}, data={actual_input_dim}"
        )
    if not 0.0 < config.positive_mask_rate < 1.0:
        raise ValueError("positive_mask_rate must be between zero and one")
    if config.hidden_dim <= config.latent_dim or config.latent_dim < 1:
        raise ValueError("expected input > hidden > latent dimensions")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
