#!/usr/bin/env python
"""Audit accepted XGBoost models with validation-only TreeSHAP summaries."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
import yaml
from scipy import sparse
from sklearn.preprocessing import LabelEncoder

from open_cancer.constants import CLASS_LABELS
from open_cancer.hashing import sha256_file, sha256_lines
from open_cancer.hotspot_features import (
    build_hotspot_augmented_features,
    resolve_hotspot_config,
)
from open_cancer.mutation_features import (
    resolve_position_features_from_config,
    resolve_position_options_from_config,
)
from open_cancer.tree_shap_audit import (
    accumulate_contribution_chunk,
    feature_family,
    stratified_validation_sample,
)
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder


ROOT = Path(__file__).resolve().parents[1]
FEATURE_DIR = ROOT / "data" / "processed" / "exp219_macro_f1_checkpoint_selection_features"
OUTPUT_DIR = ROOT / "reports" / "analysis" / "adopted_model_tree_shap"
SPLIT_PATH = ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
BASE_CONFIG = ROOT / "configs" / "exp219_macro_f1_checkpoint_selection.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-per-class", type=int, default=3)
    parser.add_argument("--chunk-size", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_base_features() -> None:
    """Rebuild the stateless EXP-219 feature cache when it is absent."""

    required = (FEATURE_DIR / "train_features.npz", FEATURE_DIR / "feature_names.json")
    if all(path.exists() for path in required):
        return
    config = yaml.safe_load(BASE_CONFIG.read_text(encoding="utf-8"))
    hotspots, _, _ = resolve_hotspot_config(config.get("hotspots", {}))
    build_hotspot_augmented_features(
        TRAIN_PATH,
        ROOT / "data" / "raw" / "test.csv",
        FEATURE_DIR,
        hotspots=hotspots,
        base_feature_options={
            "selected_robust_aggregates": tuple(
                config.get("features", {}).get("robust_aggregates", [])
            ),
            "selected_position_features": resolve_position_features_from_config(config),
            **resolve_position_options_from_config(config),
        },
    )


def update_sum(target: dict[str, float], names: tuple[str, ...], values: np.ndarray) -> None:
    for name, value in zip(names, values, strict=True):
        target[name] += float(value)


def audit_model(
    *,
    slug: str,
    model_dir: Path,
    base_features: sparse.csr_matrix,
    base_names: tuple[str, ...],
    folds: np.ndarray,
    target: np.ndarray,
    max_per_class: int,
    chunk_size: int,
    seed: int,
    fold_builder: PathwayMutationTypeFoldBuilder | None = None,
) -> dict[str, Any]:
    global_sum: dict[str, float] = defaultdict(float)
    class_sum = [defaultdict(float) for _ in CLASS_LABELS]
    class_rows = np.zeros(len(CLASS_LABELS), dtype=np.int64)
    global_denominator = 0
    fold_records: list[dict[str, Any]] = []

    for fold in range(5):
        valid_indices = np.flatnonzero(folds == fold)
        train_indices = np.flatnonzero(folds != fold)
        sample_indices = stratified_validation_sample(
            valid_indices,
            target,
            fold=fold,
            class_count=len(CLASS_LABELS),
            max_per_class=max_per_class,
            seed=seed,
        )
        matrix = base_features[sample_indices]
        names = base_names
        extra_names: tuple[str, ...] = ()
        if fold_builder is not None:
            extra = fold_builder(
                fold=fold,
                train_indices=train_indices,
                valid_indices=sample_indices,
                base_train=base_features[train_indices],
                base_validation=matrix,
                base_test=base_features[:1],
                base_feature_names=base_names,
                target=target[train_indices],
            )
            matrix = sparse.hstack([matrix, extra.validation], format="csr", dtype=np.float32)
            extra_names = tuple(extra.feature_names)
            names = (*base_names, *extra_names)

        checkpoint = model_dir / f"fold_{fold:02d}.json"
        booster = xgb.Booster()
        booster.load_model(checkpoint)
        if booster.num_features() != matrix.shape[1] or matrix.shape[1] != len(names):
            raise ValueError(
                f"{slug} fold {fold} feature contract mismatch: "
                f"model={booster.num_features()}, matrix={matrix.shape[1]}, names={len(names)}"
            )

        fold_global = np.zeros(len(names), dtype=np.float64)
        fold_class = np.zeros((len(CLASS_LABELS), len(names)), dtype=np.float64)
        fold_class_rows = np.zeros(len(CLASS_LABELS), dtype=np.int64)
        for start in range(0, len(sample_indices), chunk_size):
            stop = min(start + chunk_size, len(sample_indices))
            chunk = matrix[start:stop]
            labels = target[sample_indices[start:stop]]
            contributions = booster.predict(
                xgb.DMatrix(chunk), pred_contribs=True, strict_shape=True
            )
            chunk_global, chunk_class, chunk_rows = accumulate_contribution_chunk(
                contributions, labels, class_count=len(CLASS_LABELS)
            )
            fold_global += chunk_global
            fold_class += chunk_class
            fold_class_rows += chunk_rows

        update_sum(global_sum, names, fold_global)
        for class_index in range(len(CLASS_LABELS)):
            update_sum(class_sum[class_index], names, fold_class[class_index])
        class_rows += fold_class_rows
        global_denominator += len(sample_indices) * len(CLASS_LABELS)
        class_counts = {
            CLASS_LABELS[index]: int(value)
            for index, value in enumerate(fold_class_rows)
            if value
        }
        fold_records.append(
            {
                "fold": fold,
                "validation_rows": int(len(valid_indices)),
                "sampled_rows": int(len(sample_indices)),
                "sampled_class_counts": class_counts,
                "sample_id_sha256": hashlib.sha256(
                    "\n".join(str(value) for value in sample_indices).encode("utf-8")
                ).hexdigest(),
                "feature_count": len(names),
                "feature_names_sha256": sha256_lines(names),
                "extra_feature_count": len(extra_names),
                "checkpoint": str(checkpoint.relative_to(ROOT)),
                "checkpoint_sha256": sha256_file(checkpoint),
            }
        )

    global_mean = {name: value / global_denominator for name, value in global_sum.items()}
    total_global = sum(global_mean.values())
    global_rows = sorted(
        (
            {
                "feature": name,
                "family": feature_family(name),
                "mean_abs_shap": value,
                "share": value / total_global if total_global else 0.0,
            }
            for name, value in global_mean.items()
        ),
        key=lambda row: (-row["mean_abs_shap"], row["feature"]),
    )
    for rank, row in enumerate(global_rows, 1):
        row["rank"] = rank

    class_rows_output: list[dict[str, Any]] = []
    for class_index, label in enumerate(CLASS_LABELS):
        denominator = int(class_rows[class_index])
        rows = sorted(
            (
                {
                    "class": label,
                    "feature": name,
                    "family": feature_family(name),
                    "mean_abs_true_class_shap": value / denominator,
                }
                for name, value in class_sum[class_index].items()
            ),
            key=lambda row: (-row["mean_abs_true_class_shap"], row["feature"]),
        )
        for rank, row in enumerate(rows[:20], 1):
            row["rank"] = rank
            class_rows_output.append(row)

    family_groups: dict[str, list[float]] = defaultdict(list)
    for row in global_rows:
        family_groups[row["family"]].append(row["mean_abs_shap"])
    family_rows = sorted(
        (
            {
                "family": family,
                "feature_count": len(values),
                "total_mean_abs_shap": float(sum(values)),
                "total_share": float(sum(values) / total_global if total_global else 0.0),
                "mean_per_feature": float(np.mean(values)),
            }
            for family, values in family_groups.items()
        ),
        key=lambda row: (-row["total_share"], row["family"]),
    )

    pd.DataFrame(global_rows[:500]).to_csv(
        OUTPUT_DIR / f"{slug}_global_top500.csv", index=False
    )
    pd.DataFrame(class_rows_output).to_csv(
        OUTPUT_DIR / f"{slug}_class_top20.csv", index=False
    )
    pd.DataFrame(family_rows).to_csv(
        OUTPUT_DIR / f"{slug}_family_importance.csv", index=False
    )
    return {
        "slug": slug,
        "sampled_rows": int(global_denominator // len(CLASS_LABELS)),
        "class_sample_counts": {
            label: int(class_rows[index]) for index, label in enumerate(CLASS_LABELS)
        },
        "folds": fold_records,
        "global_top20": global_rows[:20],
        "family_importance": family_rows,
    }


def main() -> None:
    args = parse_args()
    if args.chunk_size < 1:
        raise ValueError("chunk-size must be positive")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ensure_base_features()
    base_features = sparse.load_npz(FEATURE_DIR / "train_features.npz").tocsr()
    base_names = tuple(json.loads((FEATURE_DIR / "feature_names.json").read_text()))
    train = pd.read_csv(TRAIN_PATH, usecols=["ID", "SUBCLASS"], dtype=str)
    split = pd.read_csv(SPLIT_PATH, dtype={"ID": str, "fold": int})
    merged = train.merge(split, on="ID", how="left", validate="one_to_one", sort=False)
    if not merged["ID"].equals(train["ID"]) or merged["fold"].isna().any():
        raise ValueError("canonical fold ID contract mismatch")
    encoder = LabelEncoder().fit(list(CLASS_LABELS))
    target = encoder.transform(train["SUBCLASS"]).astype(np.int32)
    folds = merged["fold"].to_numpy(dtype=np.int32)

    models = [
        audit_model(
            slug="exp219_macro_f1_checkpoint_selection",
            model_dir=ROOT / "models" / "exp219_macro_f1_checkpoint_selection",
            base_features=base_features,
            base_names=base_names,
            folds=folds,
            target=target,
            max_per_class=args.max_per_class,
            chunk_size=args.chunk_size,
            seed=args.seed,
        ),
        audit_model(
            slug="exp229_pathway_mutation_types",
            model_dir=ROOT / "models" / "exp229_pathway_mutation_types",
            base_features=base_features,
            base_names=base_names,
            folds=folds,
            target=target,
            max_per_class=args.max_per_class,
            chunk_size=args.chunk_size,
            seed=args.seed,
            fold_builder=PathwayMutationTypeFoldBuilder(),
        ),
    ]
    write_json(
        OUTPUT_DIR / "summary.json",
        {
            "analysis_role": "validation_only_explanation",
            "selection_or_training_use": False,
            "test_or_public_lb_use": False,
            "method": "XGBoost exact TreeSHAP via pred_contribs",
            "sampling": {
                "seed": args.seed,
                "max_per_class_per_fold": args.max_per_class,
                "chunk_size": args.chunk_size,
            },
            "data": {
                "train_sha256": sha256_file(TRAIN_PATH),
                "split_sha256": sha256_file(SPLIT_PATH),
                "base_feature_names_sha256": sha256_lines(base_names),
            },
            "models": models,
        },
    )


if __name__ == "__main__":
    main()
