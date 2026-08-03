#!/usr/bin/env python
"""Run EXP-233: post-hoc class-wise logit offset for Macro F1 via inner cross-fitting.

Issue #233. Baseline is EXP-219's already-saved OOF probabilities (recovered
via the exp-219-repro-v1 Release bundle, SHA-256 double-checked against
artifact_manifest.json). No outer model is retrained; only inner-fold models
(fit strictly inside each outer fold's train partition) are trained here, to
produce honest probabilities for fitting a 26-value class-wise offset that is
then applied to EXP-219's existing outer-validation OOF by transform only.
Test-side application is out of scope for this round (see config notes).
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
    MAX_COORDINATE_PASSES,
    REGULARIZATION_LAMBDA,
    apply_class_offset,
    fit_inner_cross_fitted_probabilities,
    search_class_offsets,
)
from open_cancer.paths import relative_posix
from open_cancer.validation import validate_json_document

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "exp233_nested_decision_offset.yaml"
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
ISSUE = 233
EXP_ID = "EXP-233"
SLUG = "nested_decision_offset"
ARTIFACT_SLUG = f"exp233_{SLUG}"
PARENT_EXPERIMENT = "EXP-219"
RUNNER_COMMAND = "uv run python scripts/run_exp233_nested_decision_offset.py"


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
        raise RuntimeError(f"EXP-233은 clean issue-233 브랜치에서만 실행해야 합니다.\n{dirty}")

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
    split = pd.read_csv(
        ROOT / config["split"]["path"], dtype={"ID": str, "fold": int}
    )
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

    model_params = dict(config["model"])
    inner_cfg = config["inner_cross_fitting"]
    offset_cfg = config["offset_search"]
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

    adjusted_probabilities = baseline_probabilities.copy()
    fold_records: list[dict[str, Any]] = []
    n_splits = config["split"]["n_splits"]

    for outer_fold in range(n_splits):
        outer_valid_mask = folds == outer_fold
        outer_train_indices = np.flatnonzero(~outer_valid_mask)
        outer_valid_indices = np.flatnonzero(outer_valid_mask)

        x_outer_train = x_all[outer_train_indices]
        y_outer_train = y[outer_train_indices]

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
        inner_oof_macro_f1_before = float(
            f1_score(
                y_outer_train,
                inner_result.probabilities.argmax(axis=1),
                labels=np.arange(len(CLASS_LABELS)),
                average="macro",
                zero_division=0,
            )
        )

        search_result = search_class_offsets(
            inner_result.probabilities,
            y_outer_train,
            candidate_grid=candidate_grid,
            regularization_lambda=offset_cfg["regularization_lambda"],
            max_passes=offset_cfg["max_coordinate_passes"],
        )
        offset = search_result["offset"]

        inner_adjusted = apply_class_offset(inner_result.probabilities, offset)
        inner_oof_macro_f1_after = float(
            f1_score(
                y_outer_train,
                inner_adjusted.argmax(axis=1),
                labels=np.arange(len(CLASS_LABELS)),
                average="macro",
                zero_division=0,
            )
        )

        outer_before = baseline_probabilities[outer_valid_indices]
        outer_after = apply_class_offset(outer_before, offset)
        adjusted_probabilities[outer_valid_indices] = outer_after

        y_outer_valid = y[outer_valid_indices]
        outer_macro_f1_before = float(
            f1_score(
                y_outer_valid,
                outer_before.argmax(axis=1),
                labels=np.arange(len(CLASS_LABELS)),
                average="macro",
                zero_division=0,
            )
        )
        outer_macro_f1_after = float(
            f1_score(
                y_outer_valid,
                outer_after.argmax(axis=1),
                labels=np.arange(len(CLASS_LABELS)),
                average="macro",
                zero_division=0,
            )
        )

        fold_records.append(
            {
                "outer_fold": outer_fold,
                "inner_n_splits": inner_cfg["n_splits"],
                "inner_seed": inner_cfg["seed_base"] + outer_fold,
                "offset": offset.tolist(),
                "offset_l2_norm": float(np.linalg.norm(offset)),
                "offset_search_passes_run": search_result["passes_run"],
                "inner_oof_macro_f1_before_offset": inner_oof_macro_f1_before,
                "inner_oof_macro_f1_after_offset": inner_oof_macro_f1_after,
                "outer_validation_macro_f1_before_offset": outer_macro_f1_before,
                "outer_validation_macro_f1_after_offset": outer_macro_f1_after,
                "outer_validation_macro_f1_delta": outer_macro_f1_after - outer_macro_f1_before,
            }
        )
        print(json.dumps(fold_records[-1], ensure_ascii=False))

    adjusted_argmax = adjusted_probabilities.argmax(axis=1)
    adjusted_oof_macro_f1 = float(
        f1_score(y, adjusted_argmax, labels=np.arange(len(CLASS_LABELS)), average="macro", zero_division=0)
    )
    fold_macro_f1_after = np.array([r["outer_validation_macro_f1_after_offset"] for r in fold_records])
    fold_macro_f1_before = np.array([r["outer_validation_macro_f1_before_offset"] for r in fold_records])

    per_class_f1_before = {
        label: float(f1_score(y == index, baseline_argmax == index, zero_division=0))
        for index, label in enumerate(CLASS_LABELS)
    }
    per_class_f1_after = {
        label: float(f1_score(y == index, adjusted_argmax == index, zero_division=0))
        for index, label in enumerate(CLASS_LABELS)
    }
    log_loss_before = float(log_loss(y, baseline_probabilities, labels=np.arange(len(CLASS_LABELS))))
    log_loss_after = float(log_loss(y, adjusted_probabilities, labels=np.arange(len(CLASS_LABELS))))

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
        },
        "base_feature_spec": {
            "name": "v1",
            "base_feature_spec_sha256": feature_spec_manifest["base_feature_spec_sha256"],
            "feature_names_sha256": feature_spec_manifest["feature_names_sha256"],
            "train_shape": feature_spec_manifest["train_shape"],
        },
        "split": {
            **config["split"],
            "sha256": sha256_file(ROOT / config["split"]["path"]),
        },
        "inner_cross_fitting": inner_cfg,
        "offset_search": {**offset_cfg, "candidate_grid": list(candidate_grid)},
        "model": {"class": "xgboost.XGBClassifier", "parameters": {**model_params, "num_class": len(CLASS_LABELS)}},
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
            for r in fold_records
        ],
        "oof": {
            "macro_f1": adjusted_oof_macro_f1,
            "fold_mean": float(fold_macro_f1_after.mean()),
            "fold_std": float(fold_macro_f1_after.std()),
            "accuracy": float(accuracy_score(y, adjusted_argmax)),
            "log_loss": log_loss_after,
            "per_class_f1": per_class_f1_after,
            "confusion_matrix": confusion_matrix(
                y, adjusted_argmax, labels=np.arange(len(CLASS_LABELS))
            ).tolist(),
        },
        "artifacts": {
            "resolved_config": relative_posix(resolved_config_path, ROOT),
            "test_probability": None,
            "submission": None,
        },
        "runtime": {"seconds": time.perf_counter() - clock},
        "notes": (
            f"Baseline EXP-219 OOF macro_f1 {baseline_oof_macro_f1:.10f} (before offset), "
            f"delta {adjusted_oof_macro_f1 - baseline_oof_macro_f1:+.10f}. "
            "Test-side offset application out of scope this round (OOF only)."
        ),
    }
    metrics_path = out_report / "metrics.json"
    write_json(metrics_path, metrics)
    validate_json_document(metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json")

    comparison_to_baseline = {
        "baseline_experiment_id": PARENT_EXPERIMENT,
        "baseline_oof_macro_f1": baseline_oof_macro_f1,
        "adjusted_oof_macro_f1": adjusted_oof_macro_f1,
        "oof_macro_f1_delta": adjusted_oof_macro_f1 - baseline_oof_macro_f1,
        "baseline_log_loss": log_loss_before,
        "adjusted_log_loss": log_loss_after,
        "log_loss_delta": log_loss_after - log_loss_before,
        "baseline_fold_std": float(fold_macro_f1_before.std()),
        "adjusted_fold_std": float(fold_macro_f1_after.std()),
        "per_class_f1_before": per_class_f1_before,
        "per_class_f1_after": per_class_f1_after,
        "per_class_f1_delta": {
            label: per_class_f1_after[label] - per_class_f1_before[label] for label in CLASS_LABELS
        },
        "fold_records": fold_records,
    }
    write_json(out_report / "offset_search_detail.json", comparison_to_baseline)

    print(
        json.dumps(
            {
                "metrics": str(metrics_path),
                "baseline_oof_macro_f1": baseline_oof_macro_f1,
                "adjusted_oof_macro_f1": adjusted_oof_macro_f1,
                "delta": adjusted_oof_macro_f1 - baseline_oof_macro_f1,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
