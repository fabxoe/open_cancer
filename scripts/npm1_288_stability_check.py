#!/usr/bin/env python
"""NPM1 288 precheck Step 5: 4-seed model stability check (Issue #329).

RUN_MODE=explore, no EXP-ID (pre-Issue target-informed screening, Gate C
exception -- see npm1_288_precheck.py for steps 1-4). This script uses
SUBCLASS, canonical folds, Macro F1, and per-class F1; it is not
target-independent. Trains EXP-094 Feature Spec v1 +
hotspot__NPM1_288 (position 288 frameshift, ref-agnostic, 22 positive rows)
with the official seed 42 plus 3 stability seeds (1001/1002/1003), matching
the POLE/CTNNB1 pilot pattern.

Usage: uv run python scripts/npm1_288_stability_check.py
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics import f1_score, log_loss

from open_cancer.constants import CLASS_LABELS
from open_cancer.model_runner import create_model_adapter, run_canonical_cv
from open_cancer.mutation_features import parse_mutation_token

ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
SPLIT_PATH = ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"
FEATURE_DIR = ROOT / "reports" / "analysis" / "npm1_288_precheck_data" / "_v1_features"
OUT_PATH = ROOT / "reports" / "analysis" / "npm1_288_precheck_data" / "npm1_288_stability_results.json"

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

STABILITY_SEEDS = [1001, 1002, 1003]


def compute_npm1_288_flag(frame: pd.DataFrame) -> np.ndarray:
    flags = np.zeros(len(frame), dtype=np.float32)
    for row_index, cell in enumerate(frame["NPM1"]):
        if not cell or cell == "WT":
            continue
        for token_str in cell.split():
            if token_str == "WT":
                continue
            token = parse_mutation_token(token_str)
            if (
                token.mutation_type == "frameshift"
                and token.residue_positions
                and token.residue_positions[0] == 288
            ):
                flags[row_index] = 1.0
                break
    return flags


def run_cv_with_seed(*, x_train, x_test, targets, folds, model_dir, seed_base):
    return run_canonical_cv(
        train_features=x_train,
        test_features=x_test,
        targets=targets,
        folds=folds,
        adapter_factory=lambda fold: create_model_adapter("xgboost", MODEL_PARAMS, seed_base + fold),
        model_dir=model_dir,
        balanced_sample_weight=True,
    )


def main() -> None:
    started = time.perf_counter()
    x_train_base = sparse.load_npz(FEATURE_DIR / "train_features.npz").tocsr()
    x_test_base = sparse.load_npz(FEATURE_DIR / "test_features.npz").tocsr()

    train_raw = pd.read_csv(TRAIN_PATH, dtype=str, keep_default_na=False)
    test_raw = pd.read_csv(TEST_PATH, dtype=str, keep_default_na=False)
    train_flag = compute_npm1_288_flag(train_raw)
    test_flag = compute_npm1_288_flag(test_raw)
    print(f"train positive: {int(train_flag.sum())}, test positive: {int(test_flag.sum())}")

    x_train = sparse.hstack([x_train_base, sparse.csr_matrix(train_flag[:, None])], format="csr")
    x_test = sparse.hstack([x_test_base, sparse.csr_matrix(test_flag[:, None])], format="csr")

    split = pd.read_csv(SPLIT_PATH, dtype={"ID": str, "fold": int})
    merged = train_raw[["ID"]].merge(split, on="ID", how="left", validate="one_to_one")
    folds = merged["fold"].to_numpy(dtype=np.int32)
    targets = (
        train_raw["SUBCLASS"]
        .map({label: i for i, label in enumerate(CLASS_LABELS)})
        .to_numpy(dtype=np.int32)
    )

    baseline = json.loads(
        (ROOT / "reports" / "exp094_feature_spec_v1" / "metrics.json").read_text(encoding="utf-8")
    )
    baseline_oof = baseline["oof"]

    model_dir_base = ROOT / "reports" / "analysis" / "npm1_288_precheck_data" / "_models"
    all_seed_results = []
    for label, seed_base in (("official_42", 42), *((f"stability_{s}", s) for s in STABILITY_SEEDS)):
        model_dir = model_dir_base / label
        result = run_cv_with_seed(
            x_train=x_train, x_test=x_test, targets=targets, folds=folds,
            model_dir=model_dir, seed_base=seed_base,
        )
        pred = result.oof_probabilities.argmax(axis=1)
        fold_scores = np.asarray([row["macro_f1"] for row in result.fold_metrics])
        f1 = float(f1_score(targets, pred, average="macro"))
        per_class_f1 = {
            lbl: float(v)
            for lbl, v in zip(
                CLASS_LABELS,
                f1_score(targets, pred, average=None, labels=np.arange(len(CLASS_LABELS)), zero_division=0),
                strict=True,
            )
        }
        per_class_delta = {lbl: per_class_f1[lbl] - baseline_oof["per_class_f1"][lbl] for lbl in CLASS_LABELS}
        worst_class = min(per_class_delta, key=per_class_delta.get)
        log_loss_value = float(log_loss(targets, result.oof_probabilities, labels=np.arange(len(CLASS_LABELS))))
        seed_result = {
            "label": label,
            "seed_base": seed_base,
            "oof_macro_f1": f1,
            "macro_f1_delta_vs_exp094": f1 - baseline_oof["macro_f1"],
            "fold_macro_f1": fold_scores.tolist(),
            "fold_std": float(fold_scores.std()),
            "fold_std_delta_vs_exp094": float(fold_scores.std()) - baseline_oof["fold_std"],
            "log_loss": log_loss_value,
            "log_loss_delta_vs_exp094": log_loss_value - baseline_oof["log_loss"],
            "LAML_f1": per_class_f1["LAML"],
            "LAML_f1_delta": per_class_delta["LAML"],
            "worst_class": worst_class,
            "worst_class_delta": per_class_delta[worst_class],
            "per_class_delta": per_class_delta,
        }
        all_seed_results.append(seed_result)
        print(
            f"[{label}] OOF={f1:.10f} delta={seed_result['macro_f1_delta_vs_exp094']:+.10f} "
            f"LAML_delta={per_class_delta['LAML']:+.6f} worst={worst_class}({per_class_delta[worst_class]:+.6f})"
        )
        if label != "official_42":
            shutil.rmtree(model_dir, ignore_errors=True)

    stability_oof = np.array([r["oof_macro_f1"] for r in all_seed_results])
    summary = {
        "analysis_only": True,
        "run_mode": "explore",
        "target_used": True,
        "test_features_used_for_selection": False,
        "public_score_used": False,
        "baseline_experiment_id": baseline["experiment_id"],
        "baseline_oof_macro_f1": baseline_oof["macro_f1"],
        "train_positive": int(train_flag.sum()),
        "test_positive": int(test_flag.sum()),
        "seeds": all_seed_results,
        "stability_oof_mean": float(stability_oof.mean()),
        "stability_oof_std": float(stability_oof.std()),
        "runtime_seconds": time.perf_counter() - started,
    }
    OUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved: {OUT_PATH}")
    print(f"runtime: {summary['runtime_seconds']:.1f}s")


if __name__ == "__main__":
    main()
