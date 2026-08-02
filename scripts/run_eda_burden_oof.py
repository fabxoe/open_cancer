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
    ]
    transforms = {"raw": lambda x: x}
    if args.with_outlier_transforms:
        transforms.update(
            {
                "log1p": lambda x: np.log1p(x),
                "clip99": lambda x: np.minimum(x, np.quantile(x, 0.99)),
                "clip995": lambda x: np.minimum(x, np.quantile(x, 0.995)),
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
        for transform_name, transform in transforms.items():
            x = transform(data[feature].to_numpy(dtype=np.float32))
            oof = np.zeros((len(data), len(CLASS_LABELS)), dtype=np.float64)
            fold_scores: list[float] = []
            for fold in range(5):
                train_idx = np.flatnonzero(folds != fold)
                valid_idx = np.flatnonzero(folds == fold)
                model = xgb.XGBClassifier(**base_params)
                weights = compute_sample_weight("balanced", y[train_idx])
                model.fit(x[train_idx, None], y[train_idx], sample_weight=weights)
                proba = model.predict_proba(x[valid_idx, None])
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
