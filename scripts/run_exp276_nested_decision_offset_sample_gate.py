#!/usr/bin/env python
"""Run EXP-276: EXP-233's nested decision offset, with a per-class sample gate.

Issue #276, follow-up to #233 (rejected: 26-class OOF Macro F1 improved but
DLBC F1 collapsed -0.1235; excluding DLBC alone made all 5 outer folds
improve consistently, ~3.5x the 26-class delta). This experiment reuses the
exact same inner cross-fitting (trained once, no retraining per threshold)
and adds a per-class sample gate: classes whose minimum per-inner-fold count
falls below a threshold keep offset=0 (original EXP-219 probability,
untouched) instead of having their coordinate searched. Three threshold
candidates are evaluated from the same inner-cross-fit run; the official
result is chosen by the pre-fixed rule in the config.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
import xgboost as xgb
import yaml
from scipy import sparse
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.constants import CLASS_LABELS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.frozen_feature_specs import materialize_frozen_feature_spec
from open_cancer.hashing import sha256_file
from open_cancer.model_runner import create_model_adapter
from open_cancer.nested_decision_offset import (
    CANDIDATE_OFFSET_GRID,
    apply_class_offset,
    fit_inner_cross_fitted_probabilities,
    min_class_count_per_inner_fold,
    search_class_offsets,
)
from open_cancer.paths import relative_posix
from open_cancer.validation import validate_json_document

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "exp276_nested_decision_offset_sample_gate.yaml"
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
ISSUE = 276
EXP_ID = "EXP-276"
SLUG = "nested_decision_offset_sample_gate"
ARTIFACT_SLUG = f"exp276_{SLUG}"
PARENT_EXPERIMENT = "EXP-219"
RUNNER_COMMAND = "uv run python scripts/run_exp276_nested_decision_offset_sample_gate.py"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    started = datetime.now(timezone.utc)
    clock = time.perf_counter()
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    dirty = git("status", "--porcelain")
    if context.experiment_id != EXP_ID or dirty:
        raise RuntimeError(f"EXP-276은 clean issue-276 브랜치에서만 실행해야 합니다.\n{dirty}")

    out_report = ROOT / "reports" / ARTIFACT_SLUG
    out_repro = ROOT / "reproducibility" / ARTIFACT_SLUG
    feature_dir = ROOT / "data" / "processed" / f"{ARTIFACT_SLUG}_features"
    for path in (out_report, out_repro):
        path.mkdir(parents=True, exist_ok=True)

    baseline_oof_path = ROOT / config["baseline"]["oof_path"]
    if not baseline_oof_path.is_file():
        raise FileNotFoundError(
            f"EXP-219 baseline OOF가 없습니다: {baseline_oof_path}. "
            "scripts/fetch_experiment_artifacts.py --experiment EXP-219 로 먼저 복원하세요."
        )

    feature_spec_manifest = materialize_frozen_feature_spec(
        root=ROOT, name="v1", output_dir=feature_dir, train_path=TRAIN_PATH, test_path=TEST_PATH
    )
    x_all = sparse.load_npz(feature_dir / "train_features.npz").tocsr()

    train_raw = pd.read_csv(TRAIN_PATH, usecols=["ID", "SUBCLASS"], dtype=str)
    split = pd.read_csv(ROOT / config["split"]["path"], dtype={"ID": str, "fold": int})
    train = train_raw.merge(split, on="ID", how="left", validate="one_to_one", sort=False)
    if not train["ID"].equals(train_raw["ID"]) or train["fold"].isna().any():
        raise ValueError("split 병합 후 train 순서 또는 커버리지가 어긋났습니다.")
    label_index = {label: index for index, label in enumerate(CLASS_LABELS)}
    y = train["SUBCLASS"].map(label_index).to_numpy(dtype=np.int64)
    folds = train["fold"].to_numpy(dtype=np.int32)

    baseline_oof = pd.read_csv(baseline_oof_path, dtype={"ID": str})
    if not baseline_oof["ID"].equals(train["ID"]):
        raise ValueError("EXP-219 baseline OOF의 ID 순서가 v1 feature matrix와 다릅니다.")
    proba_columns = [f"PROBA_{label}" for label in CLASS_LABELS]
    baseline_probabilities = baseline_oof.loc[:, proba_columns].to_numpy(dtype=np.float64)
    baseline_argmax = baseline_probabilities.argmax(axis=1)
    baseline_oof_macro_f1 = float(
        f1_score(y, baseline_argmax, labels=np.arange(len(CLASS_LABELS)), average="macro", zero_division=0)
    )
    baseline_log_loss = float(log_loss(y, baseline_probabilities, labels=np.arange(len(CLASS_LABELS))))

    model_params = dict(config["model"])
    inner_cfg = config["inner_cross_fitting"]
    offset_cfg = config["offset_search"]
    gate_cfg = config["sample_gate"]
    thresholds = sorted(int(t) for t in gate_cfg["threshold_candidates"])
    candidate_grid = tuple(
        round(float(v), 1)
        for v in np.arange(
            offset_cfg["candidate_grid_min"],
            offset_cfg["candidate_grid_max"] + offset_cfg["candidate_grid_step"] / 2,
            offset_cfg["candidate_grid_step"],
        )
    )
    if candidate_grid != CANDIDATE_OFFSET_GRID:
        raise ValueError("config의 candidate grid가 nested_decision_offset.py 상수와 다릅니다.")

    n_splits = config["split"]["n_splits"]
    n_classes = len(CLASS_LABELS)

    # Train the 15 inner models exactly once; reuse the resulting honest
    # probabilities for all 3 sample-gate thresholds (cheap offset search only).
    per_fold_min_counts: list[np.ndarray] = []
    per_fold_inner_probabilities: list[np.ndarray] = []
    per_fold_outer_train_targets: list[np.ndarray] = []
    per_fold_outer_valid_indices: list[np.ndarray] = []

    for outer_fold in range(n_splits):
        outer_valid_mask = folds == outer_fold
        outer_train_indices = np.flatnonzero(~outer_valid_mask)
        outer_valid_indices = np.flatnonzero(outer_valid_mask)
        per_fold_outer_valid_indices.append(outer_valid_indices)

        x_outer_train = x_all[outer_train_indices]
        y_outer_train = y[outer_train_indices]
        per_fold_outer_train_targets.append(y_outer_train)

        def train_fn(inner_train_pos: np.ndarray, inner_holdout_pos: np.ndarray) -> np.ndarray:
            x_inner_train = x_outer_train[inner_train_pos]
            y_inner_train = y_outer_train[inner_train_pos]
            x_inner_holdout = x_outer_train[inner_holdout_pos]
            y_inner_holdout = y_outer_train[inner_holdout_pos]
            sample_weight = (
                compute_sample_weight(class_weight="balanced", y=y_inner_train)
                if config["training"]["balanced_sample_weight"]
                else None
            )
            adapter = create_model_adapter(
                "xgboost", model_params, inner_cfg["seed_base"] + outer_fold
            )
            adapter.fit(x_inner_train, y_inner_train, x_inner_holdout, y_inner_holdout, sample_weight)
            return adapter.predict_proba(x_inner_holdout)

        inner_result = fit_inner_cross_fitted_probabilities(
            features=x_outer_train,
            targets=y_outer_train,
            train_fn=train_fn,
            n_splits=inner_cfg["n_splits"],
            seed=inner_cfg["seed_base"] + outer_fold,
        )
        per_fold_inner_probabilities.append(inner_result.probabilities)
        min_counts = min_class_count_per_inner_fold(
            y_outer_train, inner_result.inner_fold_assignment, inner_cfg["n_splits"]
        )
        per_fold_min_counts.append(min_counts)
        print(
            json.dumps(
                {"outer_fold": outer_fold, "min_class_count_per_inner_fold": min_counts.tolist()},
                ensure_ascii=False,
            )
        )

    # For each threshold, run the (cheap) gated offset search per outer fold
    # using the already-trained inner probabilities, and assemble full OOF.
    threshold_results: dict[int, dict[str, Any]] = {}
    for threshold in thresholds:
        adjusted_probabilities = baseline_probabilities.copy()
        fold_records: list[dict[str, Any]] = []
        for outer_fold in range(n_splits):
            y_outer_train = per_fold_outer_train_targets[outer_fold]
            inner_probabilities = per_fold_inner_probabilities[outer_fold]
            min_counts = per_fold_min_counts[outer_fold]
            eligible = min_counts >= threshold

            search_result = search_class_offsets(
                inner_probabilities,
                y_outer_train,
                candidate_grid=candidate_grid,
                regularization_lambda=offset_cfg["regularization_lambda"],
                max_passes=offset_cfg["max_coordinate_passes"],
                eligible_classes=eligible,
            )
            offset = search_result["offset"]

            outer_valid_indices = per_fold_outer_valid_indices[outer_fold]
            outer_before = baseline_probabilities[outer_valid_indices]
            outer_after = apply_class_offset(outer_before, offset)
            adjusted_probabilities[outer_valid_indices] = outer_after

            y_outer_valid = y[outer_valid_indices]
            outer_macro_f1_before = float(
                f1_score(
                    y_outer_valid, outer_before.argmax(axis=1),
                    labels=np.arange(n_classes), average="macro", zero_division=0,
                )
            )
            outer_macro_f1_after = float(
                f1_score(
                    y_outer_valid, outer_after.argmax(axis=1),
                    labels=np.arange(n_classes), average="macro", zero_division=0,
                )
            )
            fold_records.append(
                {
                    "outer_fold": outer_fold,
                    "n_eligible_classes": int(eligible.sum()),
                    "ineligible_classes": [
                        CLASS_LABELS[i] for i in range(n_classes) if not eligible[i]
                    ],
                    "offset": offset.tolist(),
                    "outer_validation_macro_f1_before_offset": outer_macro_f1_before,
                    "outer_validation_macro_f1_after_offset": outer_macro_f1_after,
                    "outer_validation_macro_f1_delta": outer_macro_f1_after - outer_macro_f1_before,
                }
            )

        adjusted_argmax = adjusted_probabilities.argmax(axis=1)
        adjusted_oof_macro_f1 = float(
            f1_score(y, adjusted_argmax, labels=np.arange(n_classes), average="macro", zero_division=0)
        )
        fold_macro_f1_after = np.array(
            [r["outer_validation_macro_f1_after_offset"] for r in fold_records]
        )
        log_loss_after = float(log_loss(y, adjusted_probabilities, labels=np.arange(n_classes)))
        per_class_f1_after = {
            label: float(f1_score(y == index, adjusted_argmax == index, zero_division=0))
            for index, label in enumerate(CLASS_LABELS)
        }

        threshold_results[threshold] = {
            "threshold": threshold,
            "adjusted_probabilities": adjusted_probabilities,
            "adjusted_argmax": adjusted_argmax,
            "oof_macro_f1": adjusted_oof_macro_f1,
            "fold_mean": float(fold_macro_f1_after.mean()),
            "fold_std": float(fold_macro_f1_after.std()),
            "log_loss": log_loss_after,
            "per_class_f1": per_class_f1_after,
            "fold_records": fold_records,
        }
        print(
            json.dumps(
                {
                    "threshold": threshold,
                    "oof_macro_f1": adjusted_oof_macro_f1,
                    "delta_vs_baseline": adjusted_oof_macro_f1 - baseline_oof_macro_f1,
                    "log_loss": log_loss_after,
                    "log_loss_delta": log_loss_after - baseline_log_loss,
                    "fold_std": float(fold_macro_f1_after.std()),
                },
                ensure_ascii=False,
            )
        )

    baseline_fold_scores = []
    for outer_fold in range(n_splits):
        idx = per_fold_outer_valid_indices[outer_fold]
        baseline_fold_scores.append(
            float(
                f1_score(
                    y[idx], baseline_argmax[idx],
                    labels=np.arange(n_classes), average="macro", zero_division=0,
                )
            )
        )
    baseline_fold_std = float(np.std(baseline_fold_scores))

    # Pre-fixed selection rule (config.official_threshold_selection): smallest
    # threshold that beats baseline on Macro F1 without regressing Log Loss or
    # fold-std; else the candidate with the highest Macro F1 (still reported
    # as not clearing the bar).
    qualifying = [
        t
        for t in thresholds
        if threshold_results[t]["oof_macro_f1"] > baseline_oof_macro_f1
        and threshold_results[t]["log_loss"] <= baseline_log_loss
        and threshold_results[t]["fold_std"] <= baseline_fold_std
    ]
    if qualifying:
        official_threshold = qualifying[0]
        verdict = "ADOPT"
    else:
        official_threshold = max(thresholds, key=lambda t: threshold_results[t]["oof_macro_f1"])
        verdict = "ARCHIVE"

    official = threshold_results[official_threshold]

    source_commit = git("rev-parse", "HEAD")
    owner = git("config", "user.name") or os.environ.get("USER", "unknown")
    finished = datetime.now(timezone.utc)

    resolved_config = {
        "experiment": {
            "record_role": config["record_role"],
            "issue_number": context.issue_number,
            "experiment_id": context.experiment_id,
            "component_experiments": config.get("component_experiments", []),
            "branch": context.branch,
            "owner": owner,
            "source_commit": source_commit,
            "dirty_worktree": bool(dirty),
            "started_at": started.isoformat(),
        },
        "baseline": {
            **config["baseline"],
            "oof_sha256": sha256_file(baseline_oof_path),
            "oof_macro_f1": baseline_oof_macro_f1,
            "log_loss": baseline_log_loss,
            "fold_std": baseline_fold_std,
        },
        "base_feature_spec": {
            "name": "v1",
            "base_feature_spec_sha256": feature_spec_manifest["base_feature_spec_sha256"],
            "feature_names_sha256": feature_spec_manifest["feature_names_sha256"],
            "train_shape": feature_spec_manifest["train_shape"],
        },
        "split": {**config["split"], "sha256": sha256_file(ROOT / config["split"]["path"])},
        "inner_cross_fitting": inner_cfg,
        "sample_gate": gate_cfg,
        "offset_search": {**offset_cfg, "candidate_grid": list(candidate_grid)},
        "official_threshold_selection": config["official_threshold_selection"],
        "official_threshold_chosen": official_threshold,
        "qualifying_thresholds": qualifying,
        "verdict": verdict,
        "model": {"class": "xgboost.XGBClassifier", "parameters": {**model_params, "num_class": n_classes}},
        "training": config["training"],
        "optimism_bias_disclosure": config["optimism_bias_disclosure"],
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "xgboost": xgb.__version__,
            "uv_lock_sha256": sha256_file(ROOT / "uv.lock"),
        },
        "command": RUNNER_COMMAND,
    }
    resolved_config_path = out_repro / "config.resolved.yaml"
    resolved_config_path.write_text(
        yaml.safe_dump(resolved_config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    metrics = {
        "experiment_id": EXP_ID,
        "record_role": "official",
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": ISSUE,
        "parent_experiment": PARENT_EXPERIMENT,
        "git_commit": source_commit,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "primary_metric": "macro_f1",
        "split_id": config["split"]["path"],
        "folds": [
            {
                "fold": r["outer_fold"],
                "macro_f1": r["outer_validation_macro_f1_after_offset"],
                "accuracy": None,
                "log_loss": None,
                "best_iteration": None,
            }
            for r in official["fold_records"]
        ],
        "oof": {
            "macro_f1": official["oof_macro_f1"],
            "fold_mean": official["fold_mean"],
            "fold_std": official["fold_std"],
            "accuracy": float(accuracy_score(y, official["adjusted_argmax"])),
            "log_loss": official["log_loss"],
            "per_class_f1": official["per_class_f1"],
            "confusion_matrix": confusion_matrix(
                y, official["adjusted_argmax"], labels=np.arange(n_classes)
            ).tolist(),
        },
        "artifacts": {"resolved_config": relative_posix(resolved_config_path, ROOT)},
        "runtime": {"seconds": time.perf_counter() - clock},
        "notes": (
            f"Official threshold: {official_threshold} (verdict {verdict}). "
            f"Baseline EXP-219 OOF macro_f1 {baseline_oof_macro_f1:.10f}, "
            f"delta {official['oof_macro_f1'] - baseline_oof_macro_f1:+.10f}. "
            f"Qualifying thresholds (Macro F1 up, Log Loss/fold-std not worse): {qualifying or 'none'}."
        ),
    }
    metrics_path = out_report / "metrics.json"
    write_json(metrics_path, metrics)
    validate_json_document(metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json")

    threshold_comparison = {
        "baseline_oof_macro_f1": baseline_oof_macro_f1,
        "baseline_log_loss": baseline_log_loss,
        "baseline_fold_std": baseline_fold_std,
        "thresholds": {
            str(t): {
                "oof_macro_f1": threshold_results[t]["oof_macro_f1"],
                "oof_macro_f1_delta": threshold_results[t]["oof_macro_f1"] - baseline_oof_macro_f1,
                "fold_mean": threshold_results[t]["fold_mean"],
                "fold_std": threshold_results[t]["fold_std"],
                "fold_std_delta": threshold_results[t]["fold_std"] - baseline_fold_std,
                "log_loss": threshold_results[t]["log_loss"],
                "log_loss_delta": threshold_results[t]["log_loss"] - baseline_log_loss,
                "per_class_f1": threshold_results[t]["per_class_f1"],
                "fold_records": threshold_results[t]["fold_records"],
                "qualifies": t in qualifying,
            }
            for t in thresholds
        },
        "official_threshold": official_threshold,
        "verdict": verdict,
        "min_class_count_per_inner_fold_by_fold": [
            {
                "outer_fold": i,
                "min_counts": {
                    CLASS_LABELS[j]: int(per_fold_min_counts[i][j]) for j in range(n_classes)
                },
            }
            for i in range(n_splits)
        ],
    }
    write_json(out_report / "threshold_comparison.json", threshold_comparison)

    print(
        json.dumps(
            {
                "metrics": str(metrics_path),
                "baseline_oof_macro_f1": baseline_oof_macro_f1,
                "official_threshold": official_threshold,
                "official_oof_macro_f1": official["oof_macro_f1"],
                "verdict": verdict,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
