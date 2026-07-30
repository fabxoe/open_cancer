#!/usr/bin/env python
"""Run EXP-005: XGBoost with sparse gene-by-mutation-type features."""

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
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
)
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.hashing import sha256_file
from open_cancer.mutation_features import build_mutation_features
from open_cancer.validation import validate_json_document, validate_submission


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "exp005_xgb_mutation_features.yaml"
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
SAMPLE_SUBMISSION_PATH = ROOT / "data" / "raw" / "sample_submission.csv"
FEATURE_DIR = ROOT / "data" / "processed" / "mutation_type_features"


def run_git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    started_at = datetime.now(timezone.utc)
    start_time = time.perf_counter()
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    if context.experiment_id != "EXP-005" or context.issue_number != 5:
        raise ValueError("이 script는 Issue #5 브랜치의 EXP-005 전용입니다.")

    artifact_slug = "exp005_xgb_mutation_features"
    split_path = ROOT / config["split"]["path"]
    report_dir = ROOT / "reports" / artifact_slug
    model_dir = ROOT / "models" / artifact_slug
    oof_path = ROOT / "oof" / f"{artifact_slug}.csv"
    test_probability_path = ROOT / "preds" / f"{artifact_slug}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{artifact_slug}.csv"
    reproducibility_dir = ROOT / "reproducibility" / artifact_slug
    resolved_config_path = reproducibility_dir / "config.resolved.yaml"
    metrics_path = report_dir / "metrics.json"
    for directory in (
        report_dir,
        model_dir,
        oof_path.parent,
        test_probability_path.parent,
        submission_path.parent,
        reproducibility_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    source_commit = run_git("rev-parse", "HEAD")
    dirty_worktree = bool(run_git("status", "--porcelain"))
    owner = run_git("config", "user.name") or os.environ.get("USER", "unknown")
    feature_report = build_mutation_features(TRAIN_PATH, TEST_PATH, FEATURE_DIR)

    train_meta = pd.read_csv(TRAIN_PATH, usecols=["ID", "SUBCLASS"], dtype=str)
    test_meta = pd.read_csv(TEST_PATH, usecols=["ID"], dtype=str)
    sample_submission = pd.read_csv(SAMPLE_SUBMISSION_PATH, dtype=str, keep_default_na=False)
    folds = pd.read_csv(split_path, dtype={"ID": str, "fold": int})
    train = train_meta.merge(folds, on="ID", how="left", validate="one_to_one", sort=False)
    if not train["ID"].equals(train_meta["ID"]):
        raise ValueError("fold 병합 과정에서 train 순서가 변경됐습니다.")

    x_all = sparse.load_npz(FEATURE_DIR / "train_features.npz")
    x_test = sparse.load_npz(FEATURE_DIR / "test_features.npz")
    feature_train_ids = pd.read_csv(FEATURE_DIR / "train_ids.csv", dtype=str)["ID"]
    feature_test_ids = pd.read_csv(FEATURE_DIR / "test_ids.csv", dtype=str)["ID"]
    if not feature_train_ids.equals(train["ID"]) or not feature_test_ids.equals(test_meta["ID"]):
        raise ValueError("피처 행렬 ID 순서가 원본과 다릅니다.")

    label_encoder = LabelEncoder().fit(list(CLASS_LABELS))
    if list(label_encoder.classes_) != list(CLASS_LABELS):
        raise ValueError("고정 클래스 순서와 LabelEncoder 순서가 다릅니다.")
    y = label_encoder.transform(train["SUBCLASS"]).astype(np.int32)

    model_params = {
        **config["model"],
        "num_class": len(CLASS_LABELS),
    }
    resolved_config = {
        "experiment": {
            "issue_number": context.issue_number,
            "experiment_id": context.experiment_id,
            "branch": context.branch,
            "owner": owner,
            "source_commit": source_commit,
            "dirty_worktree": dirty_worktree,
            "started_at": started_at.isoformat(),
        },
        "data": {
            "train": {"path": str(TRAIN_PATH.relative_to(ROOT)), "sha256": sha256_file(TRAIN_PATH)},
            "test": {"path": str(TEST_PATH.relative_to(ROOT)), "sha256": sha256_file(TEST_PATH)},
            "sample_submission": {
                "path": str(SAMPLE_SUBMISSION_PATH.relative_to(ROOT)),
                "sha256": sha256_file(SAMPLE_SUBMISSION_PATH),
            },
            "class_order": list(CLASS_LABELS),
        },
        "split": {
            **config["split"],
            "sha256": sha256_file(split_path),
            "method": "StratifiedKFold",
            "shuffle": True,
            "seed": config["seed"],
        },
        "features": feature_report["feature_contract"],
        "feature_outputs": {
            name: {
                **metadata,
                "path": str(Path(metadata["path"]).relative_to(ROOT)),
            }
            for name, metadata in feature_report["outputs"].items()
        },
        "model": {
            "class": "xgboost.XGBClassifier",
            "parameters": model_params,
        },
        "training": {
            **config["training"],
            "fold_seeds": [config["seed"] + fold for fold in range(config["split"]["n_splits"])],
            "command": "uv run python scripts/run_exp005_xgb_mutation_features.py",
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "xgboost": xgb.__version__,
            "uv_lock_sha256": sha256_file(ROOT / "uv.lock"),
        },
    }
    reproducibility_dir.mkdir(parents=True, exist_ok=True)
    resolved_config_path.write_text(
        yaml.safe_dump(resolved_config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    n_splits = config["split"]["n_splits"]
    oof_proba = np.full((len(train), len(CLASS_LABELS)), np.nan, dtype=np.float32)
    test_proba = np.zeros((len(test_meta), len(CLASS_LABELS)), dtype=np.float32)
    fold_metrics: list[dict[str, Any]] = []

    for fold in range(n_splits):
        valid_mask = train["fold"].eq(fold).to_numpy()
        train_indices = np.flatnonzero(~valid_mask)
        valid_indices = np.flatnonzero(valid_mask)
        y_train = y[train_indices]
        y_valid = y[valid_indices]
        sample_weight = (
            compute_sample_weight(class_weight="balanced", y=y_train)
            if config["training"]["balanced_sample_weight"]
            else None
        )
        model = xgb.XGBClassifier(
            **model_params,
            random_state=config["seed"] + fold,
        )
        model.fit(
            x_all[train_indices],
            y_train,
            sample_weight=sample_weight,
            eval_set=[(x_all[valid_indices], y_valid)],
            verbose=False,
        )
        valid_proba = model.predict_proba(x_all[valid_indices]).astype(np.float32)
        fold_test_proba = model.predict_proba(x_test).astype(np.float32)
        oof_proba[valid_indices] = valid_proba
        test_proba += fold_test_proba / n_splits
        valid_pred = valid_proba.argmax(axis=1)
        best_iteration = getattr(model, "best_iteration", None)
        result = {
            "fold": fold,
            "macro_f1": float(f1_score(y_valid, valid_pred, average="macro")),
            "accuracy": float(accuracy_score(y_valid, valid_pred)),
            "log_loss": float(log_loss(y_valid, valid_proba, labels=np.arange(len(CLASS_LABELS)))),
            "best_iteration": None if best_iteration is None else int(best_iteration),
        }
        fold_metrics.append(result)
        model.save_model(model_dir / f"fold_{fold:02d}.json")
        print(json.dumps(result, ensure_ascii=False))

    if np.isnan(oof_proba).any():
        raise ValueError("OOF 확률에 채워지지 않은 값이 있습니다.")

    oof_pred = oof_proba.argmax(axis=1)
    test_pred = test_proba.argmax(axis=1)
    report = classification_report(
        y,
        oof_pred,
        labels=np.arange(len(CLASS_LABELS)),
        target_names=CLASS_LABELS,
        output_dict=True,
        zero_division=0,
    )
    fold_scores = np.asarray([item["macro_f1"] for item in fold_metrics])
    finished_at = datetime.now(timezone.utc)

    oof_frame = pd.DataFrame(
        {
            "ID": train["ID"],
            "SUBCLASS_TRUE": train["SUBCLASS"],
            "SUBCLASS_PRED": label_encoder.inverse_transform(oof_pred),
            "FOLD": train["fold"].astype(int),
        }
    )
    oof_frame.loc[:, list(PROBABILITY_COLUMNS)] = oof_proba
    oof_frame.to_csv(oof_path, index=False, lineterminator="\n")

    test_probability_frame = pd.DataFrame({"ID": test_meta["ID"]})
    test_probability_frame.loc[:, list(PROBABILITY_COLUMNS)] = test_proba
    test_probability_frame.to_csv(test_probability_path, index=False, lineterminator="\n")

    submission = sample_submission.copy()
    submission["SUBCLASS"] = label_encoder.inverse_transform(test_pred)
    submission.to_csv(submission_path, index=False, lineterminator="\n")
    submission_validation = validate_submission(submission_path, TEST_PATH)

    metrics = {
        "experiment_id": context.experiment_id,
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": context.issue_number,
        "parent_experiment": None,
        "git_commit": source_commit,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "primary_metric": "macro_f1",
        "split_id": str(split_path.relative_to(ROOT)),
        "folds": fold_metrics,
        "oof": {
            "macro_f1": float(f1_score(y, oof_pred, average="macro")),
            "fold_mean": float(fold_scores.mean()),
            "fold_std": float(fold_scores.std()),
            "accuracy": float(accuracy_score(y, oof_pred)),
            "log_loss": float(log_loss(y, oof_proba, labels=np.arange(len(CLASS_LABELS)))),
            "per_class_f1": {
                label: float(report[label]["f1-score"]) for label in CLASS_LABELS
            },
            "confusion_matrix": confusion_matrix(
                y,
                oof_pred,
                labels=np.arange(len(CLASS_LABELS)),
            ).tolist(),
        },
        "leaderboard": None,
        "runtime": {
            "seconds": float(time.perf_counter() - start_time),
            "hardware": platform.platform(),
        },
        "artifacts": {
            "resolved_config": str(resolved_config_path.relative_to(ROOT)),
            "oof": str(oof_path.relative_to(ROOT)),
            "test_probability": str(test_probability_path.relative_to(ROOT)),
            "submission": str(submission_path.relative_to(ROOT)),
            "models": str(model_dir.relative_to(ROOT)),
            "submission_sha256": submission_validation["sha256"],
        },
        "notes": "Sparse gene-by-mutation-type features; no HGVS/MANE or target-derived features.",
    }
    write_json(metrics_path, metrics)
    validate_json_document(metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json")
    print(json.dumps({"metrics": str(metrics_path), "oof": metrics["oof"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
