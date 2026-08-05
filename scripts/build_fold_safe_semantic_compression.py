#!/usr/bin/env python
"""Materialize fold-safe parser-v4 semantic feature selections.

This is an implementation utility, not an experiment runner.  It never reads
targets and does not train a model.  Selection is fit independently on each
outer-training fold and replayed on validation and test matrices.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.hashing import sha256_file
from open_cancer.semantic_compression import FoldSafeSemanticCompressor


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=ROOT / "data" / "processed" / "issue475_native_v3_analysis",
        help="feature_names.json, train_features.npz, test_features.npz directory",
    )
    parser.add_argument(
        "--split-path",
        type=Path,
        default=ROOT / "data" / "splits" / "stratified_5fold_seed42.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Local generated artifact directory; normally data/processed/...",
    )
    parser.add_argument("--folds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    parser.add_argument(
        "--dimensions", type=int, nargs="+", default=[128, 256, 512]
    )
    parser.add_argument("--min-support", type=int, default=5)
    parser.add_argument("--inner-splits", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--write-matrices",
        action="store_true",
        help="Also write selected train/validation/test sparse matrices",
    )
    return parser.parse_args()


def matrix_summary(matrix: sparse.spmatrix) -> dict[str, Any]:
    rows, columns = matrix.shape
    cells = rows * columns
    return {
        "shape": [int(rows), int(columns)],
        "nnz": int(matrix.nnz),
        "density": float(matrix.nnz / cells) if cells else 0.0,
        "dtype": str(matrix.dtype),
    }


def main() -> None:
    args = parse_args()
    cache_dir = args.cache_dir.resolve()
    split_path = args.split_path.resolve()
    output_dir = args.output_dir.resolve()

    names_path = cache_dir / "feature_names.json"
    train_path = cache_dir / "train_features.npz"
    test_path = cache_dir / "test_features.npz"
    names_document = json.loads(names_path.read_text(encoding="utf-8"))
    if not isinstance(names_document, list):
        raise ValueError("feature_names.json은 문자열 배열이어야 합니다.")
    feature_names = tuple(str(value) for value in names_document)
    train_features = sparse.load_npz(train_path).tocsr().astype(np.float32)
    test_features = sparse.load_npz(test_path).tocsr().astype(np.float32)
    splits = pd.read_csv(split_path)

    if "fold" not in splits.columns:
        raise ValueError("canonical split에 fold 컬럼이 없습니다.")
    if len(splits) != train_features.shape[0]:
        raise ValueError("canonical split과 train feature 행 수가 다릅니다.")
    if train_features.shape[1] != len(feature_names):
        raise ValueError("train feature와 feature name 수가 다릅니다.")
    if test_features.shape[1] != len(feature_names):
        raise ValueError("test feature와 feature name 수가 다릅니다.")

    dimensions = tuple(sorted(set(int(value) for value in args.dimensions)))
    compressor = FoldSafeSemanticCompressor(
        target_dimensions=dimensions,
        min_support=int(args.min_support),
        inner_splits=int(args.inner_splits),
        seed=int(args.seed),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    run_summary: dict[str, Any] = {
        "artifact_type": "fold_safe_parser_v4_semantic_compression",
        "model_trained": False,
        "target_used": False,
        "cache_dir": str(cache_dir),
        "split_path": str(split_path),
        "input_sha256": {
            "feature_names": sha256_file(names_path),
            "train_features": sha256_file(train_path),
            "test_features": sha256_file(test_path),
            "split": sha256_file(split_path),
        },
        "dimensions": list(dimensions),
        "folds": {},
    }

    fold_values = splits["fold"].to_numpy(dtype=np.int64)
    for fold in args.folds:
        outer_train_rows = np.flatnonzero(fold_values != fold)
        validation_rows = np.flatnonzero(fold_values == fold)
        if len(validation_rows) == 0:
            raise ValueError(f"split에 fold {fold} 행이 없습니다.")
        fitted = compressor.fit(
            train_features[outer_train_rows], feature_names, fold=int(fold)
        )
        fold_dir = output_dir / f"fold_{fold}"
        fold_dir.mkdir(parents=True, exist_ok=True)
        fold_summary: dict[str, Any] = {
            "outer_train_rows": int(len(outer_train_rows)),
            "validation_rows": int(len(validation_rows)),
            "dimensions": {},
        }
        for dimension in dimensions:
            selected_train = fitted.transform(
                train_features[outer_train_rows], dimension=dimension
            )
            selected_validation = fitted.transform(
                train_features[validation_rows], dimension=dimension
            )
            selected_test = fitted.transform(test_features, dimension=dimension)
            manifest = fitted.manifest(dimension).to_dict()
            manifest["matrices"] = {
                "outer_train": matrix_summary(selected_train),
                "validation": matrix_summary(selected_validation),
                "test": matrix_summary(selected_test),
            }
            manifest_path = fold_dir / f"selector_{dimension}.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            paths: dict[str, str] = {"selector": str(manifest_path)}
            if args.write_matrices:
                matrix_dir = fold_dir / f"dimension_{dimension}"
                matrix_dir.mkdir(parents=True, exist_ok=True)
                for name, matrix in (
                    ("outer_train", selected_train),
                    ("validation", selected_validation),
                    ("test", selected_test),
                ):
                    path = matrix_dir / f"{name}.npz"
                    sparse.save_npz(path, matrix, compressed=True)
                    paths[name] = str(path)
            fold_summary["dimensions"][str(dimension)] = {
                "selected_feature_names_sha256": manifest[
                    "selected_feature_names_sha256"
                ],
                "paths": paths,
                "matrices": manifest["matrices"],
            }
        run_summary["folds"][str(fold)] = fold_summary

    summary_path = output_dir / "run_summary.json"
    summary_path.write_text(
        json.dumps(run_summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(summary_path)


if __name__ == "__main__":
    main()
