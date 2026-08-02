#!/usr/bin/env python
"""Exploratory single-burden-feature OOF ablations.

This script is deliberately separate from official experiment runners. It writes
only analysis artifacts and never updates EXPERIMENT_HISTORY.md.
"""

from __future__ import annotations

import json
import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import f1_score, log_loss
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.constants import CLASS_LABELS


ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "data" / "raw" / "train.csv"
SPLIT = ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"
OUT = ROOT / "reports" / "analysis" / "eda_violin"


def apply_transform(
    train_values: np.ndarray, valid_values: np.ndarray, transform: str
) -> tuple[np.ndarray, np.ndarray]:
    """Fit transform parameters on the fold-train portion only.

    In particular, clipping, robust scaling and percentile ranks must not inspect
    the validation fold. This keeps the exploratory OOF screen leakage-safe.
    """
    train_values = train_values.astype(np.float64, copy=False)
    valid_values = valid_values.astype(np.float64, copy=False)
    if transform == "raw":
        return train_values, valid_values
    if transform == "log1p":
        return np.log1p(train_values), np.log1p(valid_values)
    if transform in {"clip99", "clip995"}:
        quantile = 0.99 if transform == "clip99" else 0.995
        cap = float(np.quantile(train_values, quantile))
        return np.minimum(train_values, cap), np.minimum(valid_values, cap)
    if transform == "log1p_robust":
        train_log = np.log1p(train_values)
        valid_log = np.log1p(valid_values)
        center = float(np.median(train_log))
        scale = float(np.percentile(train_log, 75) - np.percentile(train_log, 25))
        if scale <= 0:
            scale = 1.0
        return (train_log - center) / scale, (valid_log - center) / scale
    if transform == "percentile_rank":
        sorted_train = np.sort(train_values)
        denominator = max(len(sorted_train) - 1, 1)
        train_rank = np.searchsorted(sorted_train, train_values, side="right") / denominator
        valid_rank = np.searchsorted(sorted_train, valid_values, side="right") / denominator
        return train_rank, valid_rank
    raise ValueError(f"unknown transform: {transform}")


def load_burden(path: Path, with_label: bool) -> pd.DataFrame:
    if with_label:
        from run_eda_violin import build_summary

        return build_summary()[
            [
                "mutated_gene_count",
                "total_variant_count",
                "missense_count",
                "truncating_count",
                "complex_count",
                "has_complex_any",
                "SUBCLASS",
            ]
        ]
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    frame.pop("ID")
    values = frame.to_numpy(dtype=object)
    mutated = (values != "") & (values != "WT")
    # Each cell is one gene; token-level effects are not needed for presence count.
    result = pd.DataFrame({"mutated_gene_count": mutated.sum(axis=1).astype(float)})
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--with-outlier-transforms",
        action="store_true",
        help="Run log1p and clipping only after raw-feature screening.",
    )
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    data = load_burden(TRAIN, with_label=True)
    split = pd.read_csv(SPLIT).set_index("ID")
    ids = pd.read_csv(TRAIN, usecols=["ID"], dtype=str)["ID"]
    folds = split.loc[ids, "fold"].to_numpy()
    encoder = LabelEncoder().fit(list(CLASS_LABELS))
    y = encoder.transform(data["SUBCLASS"])
    feature_names = [
        "mutated_gene_count",
        "total_variant_count",
        "missense_count",
        "truncating_count",
        "complex_count",
        "has_complex_any",
    ]
    transforms = {"raw": "raw"}
    if args.with_outlier_transforms:
        transforms.update(
            {
                "log1p": "log1p",
                "clip99": "clip99",
                "clip995": "clip995",
                "log1p_robust": "log1p_robust",
                "percentile_rank": "percentile_rank",
            }
        )
    rows: list[dict[str, float | int | str]] = []
    base_params = {
        "objective": "multi:softprob",
        "num_class": len(CLASS_LABELS),
        "n_estimators": 100,
        "learning_rate": 0.05,
        "max_depth": 6,
        "min_child_weight": 2.0,
        "subsample": 0.8,
        "colsample_bytree": 1.0,
        "reg_lambda": 1.0,
        "eval_metric": "mlogloss",
        "tree_method": "hist",
        "device": "cpu",
        "n_jobs": 2,
        "random_state": 42,
    }
    for feature in feature_names:
        for transform_name in transforms:
            oof = np.zeros((len(data), len(CLASS_LABELS)), dtype=np.float64)
            fold_scores: list[float] = []
            for fold in range(5):
                train_idx = np.flatnonzero(folds != fold)
                valid_idx = np.flatnonzero(folds == fold)
                train_x, valid_x = apply_transform(
                    data[feature].to_numpy(dtype=np.float64)[train_idx],
                    data[feature].to_numpy(dtype=np.float64)[valid_idx],
                    transform_name,
                )
                model = xgb.XGBClassifier(**base_params)
                weights = compute_sample_weight("balanced", y[train_idx])
                model.fit(train_x[:, None], y[train_idx], sample_weight=weights)
                proba = np.asarray(model.predict_proba(valid_x[:, None]), dtype=np.float64)
                proba = np.maximum(proba, 0.0)
                proba = proba / proba.sum(axis=1, keepdims=True)
                oof[valid_idx] = proba
                fold_scores.append(
                    f1_score(y[valid_idx], proba.argmax(axis=1), average="macro")
                )
            predictions = oof.argmax(axis=1)
            class_scores = f1_score(y, predictions, average=None, labels=np.arange(len(CLASS_LABELS)))
            rows.append(
                {
                    "feature": feature,
                    "transform": transform_name,
                    "oof_macro_f1": f1_score(y, predictions, average="macro"),
                    "fold_std": np.std(fold_scores, ddof=0),
                    "log_loss": log_loss(y, oof, labels=np.arange(len(CLASS_LABELS))),
                    "lower_quartile_class_f1": float(np.mean(np.sort(class_scores)[:7])),
                    "fold_scores": json.dumps([round(v, 8) for v in fold_scores]),
                }
            )
    result = pd.DataFrame(rows).sort_values("oof_macro_f1", ascending=False)
    result.to_csv(OUT / "single_feature_oof.csv", index=False)
    print(result.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
