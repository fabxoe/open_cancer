#!/usr/bin/env python
"""Run EXP-510 limited two-fold SAINT dimension screening."""

from __future__ import annotations

import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics import f1_score, log_loss
import torch
import yaml

from open_cancer.constants import CLASS_LABELS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.hashing import sha256_file
from open_cancer.saint import (
    SaintConfig,
    build_saint_model,
    saint_parameter_count,
    set_saint_determinism,
)
from open_cancer.semantic_compression import FoldSafeSemanticCompressor


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "exp510_saint_dimension_screening.yaml"
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
REPORT_DIR = ROOT / "reports" / "exp510_saint_dimension_screening"
MODEL_DIR = ROOT / "models" / "exp510_saint_dimension_screening"
OOF_DIR = ROOT / "oof"


def iter_batches(indices: np.ndarray, batch_size: int):
    for start in range(0, len(indices), batch_size):
        yield indices[start : start + batch_size]


def balanced_weights(labels: np.ndarray) -> np.ndarray:
    counts = np.bincount(labels, minlength=len(CLASS_LABELS)).astype(np.float64)
    weights = len(labels) / (len(CLASS_LABELS) * counts)
    return weights.astype(np.float32)


def predict_fixed_batches(model, values, *, batch_size: int, device):
    model.eval()
    outputs: list[np.ndarray] = []
    all_indices = np.arange(len(values), dtype=np.int64)
    with torch.no_grad():
        for indices in iter_batches(all_indices, batch_size):
            inputs = torch.from_numpy(values[indices]).to(device)
            outputs.append(torch.softmax(model(inputs), dim=1).cpu().numpy())
    return np.vstack(outputs).astype(np.float32)


def main() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    context = resolve_experiment_context("experiment", cwd=ROOT)
    if context.experiment_id != config["experiment_id"]:
        raise ValueError("브랜치와 config의 EXP-ID가 다릅니다.")
    torch.set_num_threads(int(config["training"]["torch_threads"]))
    device = torch.device(config["training"]["device"])
    cache_dir = ROOT / config["feature_cache"]
    feature_names = tuple(
        str(value)
        for value in json.loads(
            (cache_dir / "feature_names.json").read_text(encoding="utf-8")
        )
    )
    train_features = sparse.load_npz(cache_dir / "train_features.npz").tocsr()
    split_path = ROOT / config["split"]["path"]
    splits = pd.read_csv(split_path)
    train = pd.read_csv(TRAIN_PATH, usecols=["ID", "SUBCLASS"])
    if len(train) != train_features.shape[0] or len(splits) != len(train):
        raise ValueError("train/cache/split 행 수가 다릅니다.")
    if train["ID"].astype(str).tolist() != splits["ID"].astype(str).tolist():
        raise ValueError("train과 split의 ID 순서가 다릅니다.")
    class_to_index = {label: index for index, label in enumerate(CLASS_LABELS)}
    labels = train["SUBCLASS"].map(class_to_index).to_numpy(dtype=np.int64)
    folds = splits["fold"].to_numpy(dtype=np.int64)
    dimensions = tuple(int(value) for value in config["semantic_compression"]["dimensions"])
    batch_size = int(config["training"]["batch_size"])
    max_epochs = int(config["training"]["max_epochs"])
    patience = int(config["training"]["early_stopping_patience"])
    base_seed = int(config["seed"])

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    OOF_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "config.resolved.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    results: dict[str, object] = {
        "experiment_id": context.experiment_id,
        "issue_number": context.issue_number,
        "record_role": "screening",
        "canonical_five_fold_score": False,
        "source_commit": _git_commit(),
        "config_sha256": sha256_file(CONFIG_PATH),
        "split_sha256": sha256_file(split_path),
        "feature_names_sha256": sha256_file(cache_dir / "feature_names.json"),
        "device": str(device),
        "torch_version": torch.__version__,
        "folds": {},
    }
    oof_by_dimension = {
        dimension: np.full((len(train), len(CLASS_LABELS)), np.nan, dtype=np.float32)
        for dimension in dimensions
    }
    run_started = time.perf_counter()
    for fold in config["split"]["folds"]:
        fold = int(fold)
        train_rows = np.flatnonzero(folds != fold)
        valid_rows = np.flatnonzero(folds == fold)
        compressor = FoldSafeSemanticCompressor(
            target_dimensions=dimensions,
            min_support=int(config["semantic_compression"]["min_support"]),
            inner_splits=int(config["semantic_compression"]["inner_splits"]),
            seed=base_seed,
        )
        fitted = compressor.fit(train_features[train_rows], feature_names, fold=fold)
        fold_result: dict[str, object] = {}
        for dimension in dimensions:
            arm_started = time.perf_counter()
            arm_seed = base_seed + fold * 1000 + dimension
            set_saint_determinism(arm_seed)
            train_dataset = fitted.build_saint_dataset(
                train_features[train_rows], dimension=dimension
            )
            valid_dataset = fitted.build_saint_dataset(
                train_features[valid_rows], dimension=dimension
            )
            model_config = SaintConfig(
                input_dim=dimension,
                binary_indices=train_dataset.binary_indices,
                continuous_indices=train_dataset.continuous_indices,
                n_classes=len(CLASS_LABELS),
                token_dim=int(config["model"]["token_dim"]),
                depth=int(config["model"]["depth"]),
                heads=int(config["model"]["heads"]),
                dropout=float(config["model"]["dropout"]),
                use_row_attention=True,
            )
            model = build_saint_model(model_config).to(device)
            optimizer = torch.optim.AdamW(
                model.parameters(),
                lr=float(config["training"]["learning_rate"]),
                weight_decay=float(config["training"]["weight_decay"]),
            )
            criterion = torch.nn.CrossEntropyLoss(
                weight=torch.from_numpy(balanced_weights(labels[train_rows])).to(device)
            )
            best_score = -1.0
            best_epoch = -1
            stale = 0
            epochs: list[dict[str, float | int]] = []
            checkpoint_path = MODEL_DIR / f"fold_{fold}_dimension_{dimension}.pt"
            for epoch in range(1, max_epochs + 1):
                epoch_started = time.perf_counter()
                permutation = np.random.default_rng(arm_seed + epoch).permutation(
                    len(train_rows)
                )
                model.train()
                losses: list[float] = []
                for local_indices in iter_batches(permutation, batch_size):
                    inputs = torch.from_numpy(
                        train_dataset.values[local_indices]
                    ).to(device)
                    targets = torch.from_numpy(labels[train_rows][local_indices]).to(device)
                    optimizer.zero_grad(set_to_none=True)
                    logits = model(inputs)
                    loss = criterion(logits, targets)
                    if not torch.isfinite(loss):
                        raise RuntimeError("SAINT loss가 finite하지 않습니다.")
                    loss.backward()
                    optimizer.step()
                    losses.append(float(loss.detach().cpu()))
                probabilities = predict_fixed_batches(
                    model,
                    valid_dataset.values,
                    batch_size=batch_size,
                    device=device,
                )
                predictions = probabilities.argmax(axis=1)
                macro_f1 = float(
                    f1_score(labels[valid_rows], predictions, average="macro", zero_division=0)
                )
                loss_value = float(
                    log_loss(labels[valid_rows], probabilities, labels=np.arange(len(CLASS_LABELS)))
                )
                epoch_record = {
                    "epoch": epoch,
                    "train_loss": float(np.mean(losses)),
                    "validation_macro_f1": macro_f1,
                    "validation_log_loss": loss_value,
                    "runtime_seconds": float(time.perf_counter() - epoch_started),
                }
                epochs.append(epoch_record)
                print(
                    f"fold={fold} dim={dimension} epoch={epoch} "
                    f"macro_f1={macro_f1:.8f} log_loss={loss_value:.6f}",
                    flush=True,
                )
                if macro_f1 > best_score:
                    best_score = macro_f1
                    best_epoch = epoch
                    stale = 0
                    torch.save(
                        {
                            "state_dict": model.state_dict(),
                            "model_config": model_config.__dict__,
                            "selector": fitted.manifest(dimension).to_dict(),
                            "batch_policy": config["training"]["validation_batch_policy"],
                            "seed": arm_seed,
                        },
                        checkpoint_path,
                    )
                else:
                    stale += 1
                    if stale >= patience:
                        break
            payload = torch.load(checkpoint_path, map_location=device, weights_only=False)
            model.load_state_dict(payload["state_dict"])
            best_probabilities = predict_fixed_batches(
                model, valid_dataset.values, batch_size=batch_size, device=device
            )
            replay = predict_fixed_batches(
                model, valid_dataset.values, batch_size=batch_size, device=device
            )
            if not np.array_equal(best_probabilities, replay):
                raise RuntimeError("checkpoint fixed-batch inference가 재현되지 않습니다.")
            oof_by_dimension[dimension][valid_rows] = best_probabilities
            best_predictions = best_probabilities.argmax(axis=1)
            per_class = f1_score(
                labels[valid_rows],
                best_predictions,
                labels=np.arange(len(CLASS_LABELS)),
                average=None,
                zero_division=0,
            )
            fold_result[str(dimension)] = {
                "seed": arm_seed,
                "parameter_count": saint_parameter_count(model),
                "selector_feature_names_sha256": fitted.manifest(
                    dimension
                ).selected_feature_names_sha256,
                "best_epoch": best_epoch,
                "validation_macro_f1": float(
                    f1_score(
                        labels[valid_rows], best_predictions, average="macro", zero_division=0
                    )
                ),
                "validation_log_loss": float(
                    log_loss(
                        labels[valid_rows],
                        best_probabilities,
                        labels=np.arange(len(CLASS_LABELS)),
                    )
                ),
                "class_f1": {
                    label: float(per_class[index])
                    for index, label in enumerate(CLASS_LABELS)
                },
                "epochs": epochs,
                "runtime_seconds": float(time.perf_counter() - arm_started),
                "checkpoint_path": str(checkpoint_path.relative_to(ROOT)),
                "checkpoint_sha256": sha256_file(checkpoint_path),
                "fixed_batch_inference_exact": True,
            }
            _write_json(REPORT_DIR / "metrics.partial.json", {**results, "folds": {**results["folds"], str(fold): fold_result}})
        results["folds"][str(fold)] = fold_result
    for dimension, probabilities in oof_by_dimension.items():
        path = OOF_DIR / f"exp510_saint_dimension_{dimension}_twofold.npy"
        np.save(path, probabilities)
    results["runtime_seconds"] = float(time.perf_counter() - run_started)
    results["peak_rss_bytes"] = _peak_rss_bytes()
    _write_json(REPORT_DIR / "metrics.json", results)
    print(REPORT_DIR / "metrics.json")


def _write_json(path: Path, document: object) -> None:
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _git_commit() -> str:
    import subprocess

    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


if __name__ == "__main__":
    main()
