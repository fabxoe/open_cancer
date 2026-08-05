#!/usr/bin/env python
"""Run non-official SAINT shape/OOM/NaN/determinism smoke checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.constants import CLASS_LABELS
from open_cancer.saint import (
    SaintConfig,
    build_saint_model,
    saint_parameter_count,
    set_saint_determinism,
)
from open_cancer.semantic_compression import FoldSafeSemanticCompressor


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=ROOT / "data" / "processed" / "issue475_native_v3_analysis",
    )
    parser.add_argument(
        "--split-path",
        type=Path,
        default=ROOT / "data" / "splits" / "stratified_5fold_seed42.csv",
    )
    parser.add_argument(
        "--train-path", type=Path, default=ROOT / "data" / "raw" / "train.csv"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fold", type=int, default=0)
    parser.add_argument("--dimensions", type=int, nargs="+", default=[128, 256, 512])
    parser.add_argument("--device", choices=["auto", "cpu", "mps", "cuda"], default="auto")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--steps", type=int, default=2)
    parser.add_argument("--token-dim", type=int, default=32)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--heads", type=int, default=4)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def resolve_device(torch, requested: str):
    if requested != "auto":
        return torch.device(requested)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def peak_memory_bytes(torch, device) -> int | None:
    if device.type == "cuda":
        return int(torch.cuda.max_memory_allocated(device))
    if device.type == "mps" and hasattr(torch.mps, "current_allocated_memory"):
        return int(torch.mps.current_allocated_memory())
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(usage if sys.platform == "darwin" else usage * 1024)


def main() -> None:
    args = parse_args()
    import torch

    cache_dir = args.cache_dir.resolve()
    feature_names = tuple(
        str(value)
        for value in json.loads(
            (cache_dir / "feature_names.json").read_text(encoding="utf-8")
        )
    )
    train_features = sparse.load_npz(cache_dir / "train_features.npz").tocsr()
    test_features = sparse.load_npz(cache_dir / "test_features.npz").tocsr()
    splits = pd.read_csv(args.split_path.resolve())
    train = pd.read_csv(args.train_path.resolve(), usecols=["ID", "SUBCLASS"])
    if len(train) != train_features.shape[0] or len(splits) != len(train):
        raise ValueError("train, feature cache, canonical split 행 수가 다릅니다.")
    if "ID" in splits and train["ID"].astype(str).tolist() != splits["ID"].astype(str).tolist():
        raise ValueError("train과 canonical split의 ID 순서가 다릅니다.")
    class_to_index = {label: index for index, label in enumerate(CLASS_LABELS)}
    labels = train["SUBCLASS"].map(class_to_index)
    if labels.isna().any():
        raise ValueError("고정 26-class order에 없는 SUBCLASS가 있습니다.")

    fold_values = splits["fold"].to_numpy(dtype=np.int64)
    train_rows = np.flatnonzero(fold_values != args.fold)
    valid_rows = np.flatnonzero(fold_values == args.fold)
    compressor = FoldSafeSemanticCompressor(
        target_dimensions=tuple(args.dimensions), seed=args.seed
    )
    fitted = compressor.fit(
        train_features[train_rows], feature_names, fold=args.fold
    )
    device = resolve_device(torch, args.device)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)

    results: dict[str, object] = {
        "analysis_only": True,
        "official_experiment": False,
        "history_update": False,
        "fold": int(args.fold),
        "device": str(device),
        "torch_version": torch.__version__,
        "seed": int(args.seed),
        "batch_size": int(args.batch_size),
        "steps": int(args.steps),
        "dimensions": {},
    }
    batch_size = min(args.batch_size, len(train_rows), len(valid_rows), test_features.shape[0])
    train_labels = labels.to_numpy(dtype=np.int64)[train_rows]
    for dimension in sorted(set(args.dimensions)):
        started = time.perf_counter()
        train_dataset = fitted.build_saint_dataset(
            train_features[train_rows], dimension=dimension
        )
        valid_dataset = fitted.build_saint_dataset(
            train_features[valid_rows], dimension=dimension
        )
        test_dataset = fitted.build_saint_dataset(test_features, dimension=dimension)
        config = SaintConfig(
            input_dim=dimension,
            binary_indices=train_dataset.binary_indices,
            continuous_indices=train_dataset.continuous_indices,
            n_classes=len(CLASS_LABELS),
            token_dim=args.token_dim,
            depth=args.depth,
            heads=args.heads,
            dropout=args.dropout,
            use_row_attention=True,
        )
        set_saint_determinism(args.seed + args.fold * 100 + dimension)
        model = build_saint_model(config).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
        rng = np.random.default_rng(args.seed + args.fold * 100 + dimension)
        losses: list[float] = []
        model.train()
        for _ in range(args.steps):
            indices = rng.choice(len(train_rows), size=batch_size, replace=False)
            values = torch.from_numpy(train_dataset.values[indices]).to(device)
            targets = torch.from_numpy(train_labels[indices]).to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(values)
            loss = torch.nn.functional.cross_entropy(logits, targets)
            if not torch.isfinite(loss):
                raise RuntimeError(f"dimension {dimension}: loss가 finite하지 않습니다.")
            loss.backward()
            if not all(
                parameter.grad is None or torch.isfinite(parameter.grad).all()
                for parameter in model.parameters()
            ):
                raise RuntimeError(f"dimension {dimension}: gradient가 finite하지 않습니다.")
            optimizer.step()
            losses.append(float(loss.detach().cpu()))

        model.eval()
        fixed_valid = torch.from_numpy(valid_dataset.values[:batch_size]).to(device)
        fixed_test = torch.from_numpy(test_dataset.values[:batch_size]).to(device)
        with torch.no_grad():
            first = model(fixed_valid)
            second = model(fixed_valid.clone())
            test_logits = model(fixed_test)
        exactly_deterministic = bool(torch.equal(first, second))
        if not exactly_deterministic:
            raise RuntimeError(
                f"dimension {dimension}: fixed-batch inference가 동일하지 않습니다."
            )
        if first.shape != (batch_size, len(CLASS_LABELS)):
            raise RuntimeError(f"dimension {dimension}: validation logit shape 오류")
        if test_logits.shape != (batch_size, len(CLASS_LABELS)):
            raise RuntimeError(f"dimension {dimension}: test logit shape 오류")
        results["dimensions"][str(dimension)] = {
            "selector_feature_names_sha256": fitted.manifest(
                dimension
            ).selected_feature_names_sha256,
            "train_shape": list(train_dataset.values.shape),
            "validation_shape": list(valid_dataset.values.shape),
            "test_shape": list(test_dataset.values.shape),
            "binary_columns": len(train_dataset.binary_indices),
            "continuous_columns": len(train_dataset.continuous_indices),
            "parameter_count": saint_parameter_count(model),
            "losses": losses,
            "finite_logits": bool(
                torch.isfinite(first).all() and torch.isfinite(test_logits).all()
            ),
            "exact_fixed_batch_inference": exactly_deterministic,
            "runtime_seconds": float(time.perf_counter() - started),
            "peak_memory_bytes": peak_memory_bytes(torch, device),
        }
        del model, optimizer, train_dataset, valid_dataset, test_dataset
        if device.type == "cuda":
            torch.cuda.empty_cache()
        elif device.type == "mps":
            torch.mps.empty_cache()

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
