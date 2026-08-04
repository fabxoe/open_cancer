from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from scipy import sparse

pytest.importorskip("torch")

from open_cancer.sparse_denoising_autoencoder import (  # noqa: E402
    AutoencoderConfig,
    deterministic_holdout,
    latent_audit,
    load_gene_presence_csv,
    prevalence_baseline_bce,
    train_autoencoder,
    transform_autoencoder,
)


def test_presence_loader_streams_binary_gene_matrix(tmp_path: Path) -> None:
    path = tmp_path / "train.csv"
    path.write_text(
        "ID,SUBCLASS,G1,G2,G3\n"
        "A,X,WT,R2H,\n"
        'B,Y,"R2H A3V",WT,UNKNOWN\n',
        encoding="utf-8",
    )
    matrix, ids, genes, labels = load_gene_presence_csv(path, has_labels=True)
    assert ids == ["A", "B"]
    assert genes == ["G1", "G2", "G3"]
    assert labels == ["X", "Y"]
    assert matrix.toarray().tolist() == [[0, 1, 0], [1, 0, 1]]


def test_holdout_is_deterministic_and_disjoint() -> None:
    train_a, valid_a = deterministic_holdout(range(20), fraction=0.2, seed=42)
    train_b, valid_b = deterministic_holdout(range(20), fraction=0.2, seed=42)
    assert np.array_equal(train_a, train_b)
    assert np.array_equal(valid_a, valid_b)
    assert len(valid_a) == 4
    assert not set(train_a) & set(valid_a)


def test_prevalence_baseline_uses_fit_rows_only() -> None:
    matrix = sparse.csr_matrix(
        np.asarray(
            [[1, 0, 0], [1, 1, 0], [0, 0, 1], [0, 0, 1]],
            dtype=np.float32,
        )
    )
    score_a = prevalence_baseline_bce(matrix, [0, 1], [2])
    changed = matrix.copy().tolil()
    changed[3, :] = [1, 1, 1]
    score_b = prevalence_baseline_bce(changed.tocsr(), [0, 1], [2])
    assert score_a == score_b
    assert np.isfinite(score_a)


def test_train_checkpoint_transform_and_latent_audit(tmp_path: Path) -> None:
    rng = np.random.default_rng(42)
    dense = (rng.random((24, 8)) < 0.25).astype(np.float32)
    dense[:, 0] = np.arange(24) % 2
    matrix = sparse.csr_matrix(dense)
    checkpoint = tmp_path / "model.pt"
    config = AutoencoderConfig(
        input_dim=8,
        hidden_dim=6,
        latent_dim=3,
        positive_mask_rate=0.2,
        positive_weight_cap=5.0,
        dropout=0.0,
        batch_size=4,
        max_epochs=3,
        early_stopping_patience=2,
        seed=7,
        device="cpu",
    )
    result = train_autoencoder(
        matrix,
        np.arange(18),
        np.arange(18, 24),
        config=config,
        checkpoint_path=checkpoint,
    )
    assert checkpoint.is_file()
    assert result["train_rows"] == 18
    assert result["validation_rows"] == 6
    assert result["checkpoint_sha256"]
    latent_a = transform_autoencoder(
        matrix, np.arange(24), checkpoint_path=checkpoint, device="cpu"
    )
    latent_b = transform_autoencoder(
        matrix, np.arange(24), checkpoint_path=checkpoint, device="cpu"
    )
    assert latent_a.shape == (24, 3)
    assert np.array_equal(latent_a, latent_b)
    audit = latent_audit(latent_a, np.asarray(matrix.sum(axis=1)).ravel())
    assert audit["dimension"] == 3
    assert audit["near_constant_dimensions"] <= 3
    assert audit["mean_sha256"]
