#!/usr/bin/env python
"""Raw-first train/test audit for Issue #658.

This diagnostic intentionally avoids SUBCLASS, existing feature matrices, model
predictions, and Public LB results.  It asks how much dataset identity is visible
from a handful of parser-agnostic summaries that could have been computed before
the first modelling experiment.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from open_cancer.hashing import sha256_file


FEATURES = (
    "non_wt_gene_count",
    "blank_gene_count",
    "token_count",
    "multi_token_gene_count",
    "star_stop_token_count",
    "x_stop_token_count",
    "ter_stop_token_count",
    "frameshift_token_count",
    "range_token_count",
    "long_token_count",
)
SPACE_RE = re.compile(r"\s+")


def _summarize(path: Path, genes: list[str], chunksize: int) -> np.ndarray:
    rows: list[np.ndarray] = []
    for chunk in pd.read_csv(
        path,
        usecols=["ID", *genes],
        dtype=str,
        keep_default_na=False,
        chunksize=chunksize,
    ):
        values = chunk[genes].to_numpy(dtype=object)
        stripped = np.frompyfunc(lambda value: str(value).strip(), 1, 1)(values)
        blank = stripped == ""
        mutated = (~blank) & (stripped != "WT")
        result = np.zeros((len(chunk), len(FEATURES)), dtype=np.float64)
        result[:, 0] = mutated.sum(axis=1)
        result[:, 1] = blank.sum(axis=1)

        row_index, col_index = np.nonzero(mutated)
        for row, col in zip(row_index.tolist(), col_index.tolist()):
            tokens = [token for token in SPACE_RE.split(stripped[row, col]) if token]
            result[row, 2] += len(tokens)
            result[row, 3] += len(tokens) > 1
            for token in tokens:
                lowered = token.lower()
                result[row, 4] += token.endswith("*")
                result[row, 5] += token.endswith("X") or token.endswith("x")
                result[row, 6] += lowered.endswith("ter")
                result[row, 7] += "fs" in lowered
                result[row, 8] += "_" in token
                result[row, 9] += len(token) >= 20
        rows.append(result)
    return np.vstack(rows)


def _quantiles(values: np.ndarray) -> dict[str, float]:
    labels = ("min", "p25", "median", "p75", "p90", "p95", "p99", "max")
    points = (0, 25, 50, 75, 90, 95, 99, 100)
    return {label: float(value) for label, value in zip(labels, np.percentile(values, points))}


def _domain_auc(x: np.ndarray, y: np.ndarray, seed: int) -> tuple[float, list[float]]:
    splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    oof = np.zeros(len(y), dtype=np.float64)
    folds: list[float] = []
    for train_index, valid_index in splitter.split(x, y):
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(
                C=1.0,
                class_weight="balanced",
                max_iter=2000,
                random_state=seed,
            ),
        )
        model.fit(x[train_index], y[train_index])
        prediction = model.predict_proba(x[valid_index])[:, 1]
        oof[valid_index] = prediction
        folds.append(float(roc_auc_score(y[valid_index], prediction)))
    return float(roc_auc_score(y, oof)), folds


def run(train_path: Path, test_path: Path, output_path: Path, chunksize: int, seed: int) -> dict:
    train_header = pd.read_csv(train_path, nrows=0).columns.tolist()
    test_header = pd.read_csv(test_path, nrows=0).columns.tolist()
    genes = [column for column in train_header if column not in {"ID", "SUBCLASS"}]
    if train_header != ["ID", "SUBCLASS", *genes]:
        raise ValueError("unexpected train schema")
    if test_header != ["ID", *genes]:
        raise ValueError("train/test gene names or order differ")

    train = _summarize(train_path, genes, chunksize)
    test = _summarize(test_path, genes, chunksize)
    x = np.vstack([train, test])
    y = np.concatenate([np.zeros(len(train)), np.ones(len(test))]).astype(np.int8)
    overall_auc, fold_auc = _domain_auc(x, y, seed)

    summaries: dict[str, dict] = {}
    for index, name in enumerate(FEATURES):
        train_values = train[:, index]
        test_values = test[:, index]
        raw_auc = float(roc_auc_score(y, x[:, index]))
        pooled_sd = float(np.sqrt((train_values.var() + test_values.var()) / 2.0))
        summaries[name] = {
            "train_mean": float(train_values.mean()),
            "test_mean": float(test_values.mean()),
            "train_nonzero_rate": float(np.mean(train_values > 0)),
            "test_nonzero_rate": float(np.mean(test_values > 0)),
            "standardized_mean_difference": (
                float((test_values.mean() - train_values.mean()) / pooled_sd)
                if pooled_sd > 0
                else 0.0
            ),
            "standalone_auc_direction_free": max(raw_auc, 1.0 - raw_auc),
            "higher_in_test": bool(test_values.mean() >= train_values.mean()),
            "train_quantiles": _quantiles(train_values),
            "test_quantiles": _quantiles(test_values),
        }

    result = {
        "schema_version": "1.0.0",
        "issue": 658,
        "analysis_only": True,
        "target_used": False,
        "public_lb_used": False,
        "existing_feature_matrix_used": False,
        "inputs": {
            "train": {"path": "data/raw/train.csv", "sha256": sha256_file(train_path)},
            "test": {"path": "data/raw/test.csv", "sha256": sha256_file(test_path)},
            "train_rows": len(train),
            "test_rows": len(test),
            "gene_columns": len(genes),
        },
        "domain_classifier": {
            "features": list(FEATURES),
            "model": "StandardScaler + class-balanced LogisticRegression(C=1.0)",
            "split": f"StratifiedKFold(n_splits=5, shuffle=True, random_state={seed})",
            "oof_auc": overall_auc,
            "fold_auc": fold_auc,
        },
        "feature_summaries": summaries,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, default=Path("data/raw/train.csv"))
    parser.add_argument("--test", type=Path, default=Path("data/raw/test.csv"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/analysis/fresh_start_raw_audit/summary.json"),
    )
    parser.add_argument("--chunksize", type=int, default=128)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run(args.train, args.test, args.output, args.chunksize, args.seed)
    print(json.dumps(result["domain_classifier"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
