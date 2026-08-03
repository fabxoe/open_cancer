#!/usr/bin/env python
"""EXP-181 follow-up: per-class UCEC/COAD/DLBC F1 across all 4 seeds.

The original run only persisted overall OOF macro F1 per stability seed
(1001/1002/1003), not per-class F1 or the OOF probabilities themselves
(model checkpoints were deleted after each stability seed to save disk).
This script re-runs those 3 seeds (deterministic given fixed XGBoost
random_state, same feature matrix and folds) to recover per-class F1, and
cross-checks the reproduced fold_macro_f1 against what verdict.json already
recorded as a determinism sanity check. Seed 42 reuses the already-saved
official OOF CSV -- no retraining needed for that one.

RUN_MODE=explore: does not create a new EXP-ID or History entry; the result
is folded into the existing EXP-181 report as supplementary detail.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics import f1_score

from open_cancer.constants import CLASS_LABELS
from open_cancer.feature_family import transform_checked
from open_cancer.frozen_feature_specs import materialize_frozen_feature_spec
from open_cancer.model_runner import create_model_adapter, run_canonical_cv
from open_cancer.pole_ed_features import pole_hotspot5_family

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "data" / "raw" / "train.csv"
TEST = ROOT / "data" / "raw" / "test.csv"
SLUG = "exp181_pole_hotspot5"
WATCH_CLASSES = ["UCEC", "COAD", "DLBC"]
STABILITY_SEEDS = [1001, 1002, 1003]

MODEL_PARAMS = {
    "objective": "multi:softprob",
    "n_estimators": 500,
    "learning_rate": 0.05,
    "max_depth": 6,
    "min_child_weight": 1.0,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.0,
    "reg_lambda": 1.0,
    "eval_metric": "mlogloss",
    "early_stopping_rounds": 30,
    "tree_method": "hist",
    "device": "cpu",
    "n_jobs": 8,
    "verbosity": 0,
    "num_class": len(CLASS_LABELS),
}


def per_class_f1(true_labels: np.ndarray, pred_labels: np.ndarray) -> dict[str, float]:
    values = f1_score(
        true_labels, pred_labels, average=None, labels=np.arange(len(CLASS_LABELS)), zero_division=0
    )
    return {label: float(value) for label, value in zip(CLASS_LABELS, values, strict=True)}


def main() -> None:
    baseline = json.loads(
        (ROOT / "reports" / "exp094_feature_spec_v1" / "metrics.json").read_text(encoding="utf-8")
    )
    baseline_per_class = baseline["oof"]["per_class_f1"]

    feature_dir = ROOT / "data" / "processed" / f"{SLUG}_features"
    feature_spec_manifest = materialize_frozen_feature_spec(
        root=ROOT, name="v1", output_dir=feature_dir, train_path=TRAIN, test_path=TEST
    )
    x_train_base = sparse.load_npz(feature_dir / "train_features.npz").tocsr()
    x_test_base = sparse.load_npz(feature_dir / "test_features.npz").tocsr()

    train_raw = pd.read_csv(TRAIN, dtype=str, keep_default_na=False)
    test_raw = pd.read_csv(TEST, dtype=str, keep_default_na=False)
    fitted_family = pole_hotspot5_family().fit(train_raw)
    train_flag_matrix = transform_checked(fitted_family, train_raw)
    test_flag_matrix = transform_checked(fitted_family, test_raw)
    x_train = sparse.hstack([x_train_base, train_flag_matrix], format="csr")
    x_test = sparse.hstack([x_test_base, test_flag_matrix], format="csr")

    split = train_raw[["ID"]].merge(
        pd.read_csv(
            ROOT / "data" / "splits" / "stratified_5fold_seed42.csv",
            dtype={"ID": str, "fold": int},
        ),
        on="ID",
        how="left",
        validate="one_to_one",
        sort=False,
    )
    folds = split["fold"].to_numpy(dtype=np.int32)
    label_index = {label: index for index, label in enumerate(CLASS_LABELS)}
    targets = train_raw["SUBCLASS"].map(label_index).to_numpy(dtype=np.int32)

    results: dict[str, dict] = {}

    # Seed 42: reuse the already-saved official OOF, no retraining.
    official_oof = pd.read_csv(ROOT / "oof" / f"{SLUG}.csv", dtype={"ID": str})
    official_oof = official_oof.merge(train_raw[["ID", "SUBCLASS"]], on="ID", how="left")
    official_pred = official_oof[list(CLASS_LABELS)].to_numpy().argmax(axis=1)
    official_true = official_oof["SUBCLASS"].map(label_index).to_numpy()
    official_per_class = per_class_f1(official_true, official_pred)
    official_macro_f1 = float(f1_score(official_true, official_pred, average="macro"))
    results["42"] = {
        "oof_macro_f1": official_macro_f1,
        "source": "reused_saved_oof_no_retrain",
        "per_class_f1": {cls: official_per_class[cls] for cls in WATCH_CLASSES},
        "per_class_delta": {
            cls: official_per_class[cls] - baseline_per_class[cls] for cls in WATCH_CLASSES
        },
    }

    # Recorded stability check fold_macro_f1 (from the original run) for the
    # determinism cross-check below.
    verdict = json.loads((ROOT / "reports" / SLUG / "verdict.json").read_text(encoding="utf-8"))
    recorded_stability = {
        str(item["model_seed_base"]): item["fold_macro_f1"]
        for item in verdict["stability_check"]["stability_seeds"]
    }

    for seed_base in STABILITY_SEEDS:
        model_dir = ROOT / "models" / f"{SLUG}_stability_verify_{seed_base}"
        result = run_canonical_cv(
            train_features=x_train,
            test_features=x_test,
            targets=targets,
            folds=folds,
            adapter_factory=lambda fold, seed_base=seed_base: create_model_adapter(
                "xgboost", dict(MODEL_PARAMS), seed_base + fold
            ),
            model_dir=model_dir,
            balanced_sample_weight=True,
        )
        pred = result.oof_probabilities.argmax(axis=1)
        macro_f1 = float(f1_score(targets, pred, average="macro"))
        fold_scores = [row["macro_f1"] for row in result.fold_metrics]
        recorded = recorded_stability[str(seed_base)]
        matches_recorded = all(
            abs(a - b) < 1e-9 for a, b in zip(fold_scores, recorded, strict=True)
        )
        seed_per_class = per_class_f1(targets, pred)
        results[str(seed_base)] = {
            "oof_macro_f1": macro_f1,
            "fold_macro_f1": fold_scores,
            "matches_originally_recorded_fold_scores": matches_recorded,
            "per_class_f1": {cls: seed_per_class[cls] for cls in WATCH_CLASSES},
            "per_class_delta": {
                cls: seed_per_class[cls] - baseline_per_class[cls] for cls in WATCH_CLASSES
            },
        }
        import shutil

        shutil.rmtree(model_dir, ignore_errors=True)

    # Consistency summary: does the sign of the delta agree across all 4 seeds?
    consistency = {}
    for cls in WATCH_CLASSES:
        deltas = [results[seed]["per_class_delta"][cls] for seed in ("42", "1001", "1002", "1003")]
        signs = {1 if d > 0 else (-1 if d < 0 else 0) for d in deltas}
        consistency[cls] = {
            "deltas_by_seed": {
                seed: results[seed]["per_class_delta"][cls] for seed in ("42", "1001", "1002", "1003")
            },
            "consistent_direction": len(signs - {0}) <= 1,
            "mean_delta": float(np.mean(deltas)),
            "std_delta": float(np.std(deltas)),
        }

    output = {
        "watch_classes": WATCH_CLASSES,
        "per_seed": results,
        "consistency": consistency,
    }
    output_path = ROOT / "reports" / SLUG / "watch_class_stability.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
