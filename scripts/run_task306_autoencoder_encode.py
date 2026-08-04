#!/usr/bin/env python
"""Fit and transform the Issue #306 autoencoder in a Torch-only process."""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from open_cancer.sparse_denoising_autoencoder import (
    AutoencoderConfig,
    deterministic_holdout,
    latent_audit,
    load_gene_presence_csv,
    prevalence_baseline_bce,
    train_autoencoder,
    transform_autoencoder,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "task306_sparse_denoising_autoencoder_fold0.yaml"
TRAIN = ROOT / "data" / "raw" / "train.csv"
TEST = ROOT / "data" / "raw" / "test.csv"
ARTIFACT_DIR = ROOT / "models" / "task306_sparse_denoising_autoencoder"


def main() -> None:
    started = time.perf_counter()
    task = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    values = dict(task["autoencoder"])
    holdout_fraction = float(values.pop("internal_holdout_fraction"))
    seed = int(task["seed"])
    fold = int(task["split"]["outer_fold"])
    matrix, train_ids, genes, _ = load_gene_presence_csv(TRAIN, has_labels=True)
    test_matrix, test_ids, test_genes, _ = load_gene_presence_csv(TEST, has_labels=False)
    if genes != test_genes:
        raise ValueError("train/test gene order mismatch")
    folds = pd.read_csv(ROOT / task["split"]["path"], dtype={"ID": str, "fold": int})
    fold_by_id = folds.set_index("ID")["fold"]
    if set(train_ids) != set(fold_by_id.index):
        raise ValueError("canonical split ID set mismatch")
    fold_values = fold_by_id.loc[train_ids].to_numpy()
    outer_train = np.flatnonzero(fold_values != fold)
    outer_valid = np.flatnonzero(fold_values == fold)
    ae_train, ae_holdout = deterministic_holdout(
        outer_train, fraction=holdout_fraction, seed=seed
    )
    config = AutoencoderConfig(seed=seed, **values)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint = ARTIFACT_DIR / "fold_00_autoencoder.pt"
    training = train_autoencoder(
        matrix, ae_train, ae_holdout, config=config, checkpoint_path=checkpoint
    )
    baseline_bce = prevalence_baseline_bce(matrix, ae_train, ae_holdout)
    latent_train = transform_autoencoder(matrix, outer_train, checkpoint_path=checkpoint)
    latent_valid = transform_autoencoder(matrix, outer_valid, checkpoint_path=checkpoint)
    latent_test = transform_autoencoder(
        test_matrix, np.arange(test_matrix.shape[0]), checkpoint_path=checkpoint
    )
    repeated = transform_autoencoder(matrix, outer_valid, checkpoint_path=checkpoint)
    audit = latent_audit(
        latent_train, np.asarray(matrix[outer_train].sum(axis=1)).ravel()
    )
    np.savez_compressed(
        ARTIFACT_DIR / "fold_00_latent.npz",
        train_indices=outer_train,
        valid_indices=outer_valid,
        train=latent_train,
        validation=latent_valid,
        test=latent_test,
    )
    write_json(
        ARTIFACT_DIR / "fold_00_autoencoder_stage.json",
        {
            "training": training,
            "prevalence_baseline_unweighted_bce": baseline_bce,
            "latent_audit": audit,
            "checkpoint_inference_exact": bool(np.array_equal(latent_valid, repeated)),
            "latent_shape": {
                "outer_train": list(latent_train.shape),
                "outer_validation": list(latent_valid.shape),
                "test": list(latent_test.shape),
            },
            "gene_count": len(genes),
            "test_rows": len(test_ids),
            "runtime_seconds": float(time.perf_counter() - started),
        },
    )
    print(json.dumps({"stage": "autoencoder", "latent_shape": list(latent_train.shape)}))


if __name__ == "__main__":
    main()
