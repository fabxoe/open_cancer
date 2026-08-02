#!/usr/bin/env python
"""Run EXP-179: frozen EXP-094 Feature Spec v1 with fold-local SMOTE."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import imblearn
import numpy as np
import pandas as pd
import sklearn
import xgboost as xgb
import yaml
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss

from open_cancer.constants import CLASS_LABELS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.frozen_feature_specs import materialize_frozen_feature_spec
from open_cancer.hashing import sha256_file
from open_cancer.model_artifacts import (
    build_oof_probability_frame,
    build_test_probability_frame,
    write_model_run_records,
)
from open_cancer.model_runner import create_model_adapter, run_canonical_cv
from open_cancer.resampling import FoldLocalSmote
from open_cancer.validation import validate_json_document, validate_submission

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "exp179_xgb_feature_spec_v1_smote.yaml"
TRAIN = ROOT / "data" / "raw" / "train.csv"
TEST = ROOT / "data" / "raw" / "test.csv"
SAMPLE = ROOT / "data" / "raw" / "sample_submission.csv"
SLUG = "exp179_xgb_feature_spec_v1_smote"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def clean_worktree_or_raise(context_id: str) -> None:
    dirty = [
        line
        for line in git("status", "--porcelain").splitlines()
        if not line.endswith("release-assets/")
    ]
    if dirty:
        raise RuntimeError(f"{context_id}은 clean Issue 브랜치에서만 실행해야 합니다.\n" + "\n".join(dirty))


def build_resolved_config(
    *,
    context: Any,
    owner: str,
    source_commit: str,
    started_at: datetime,
    feature_spec: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    return {
        "experiment": {
            "issue_number": context.issue_number,
            "experiment_id": context.experiment_id,
            "branch": context.branch,
            "owner": owner,
            "parent_experiment": config["parent_experiment"],
            "source_commit": source_commit,
            "started_at": started_at.isoformat(),
        },
        "data": {
            "train": {"path": "data/raw/train.csv", "sha256": sha256_file(TRAIN)},
            "test": {"path": "data/raw/test.csv", "sha256": sha256_file(TEST)},
            "sample_submission": {
                "path": "data/raw/sample_submission.csv",
                "sha256": sha256_file(SAMPLE),
            },
            "class_order": list(CLASS_LABELS),
        },
        "split": {
            **config["split"],
            "sha256": sha256_file(ROOT / config["split"]["path"]),
            "method": "StratifiedKFold",
        },
        "base_feature_spec": feature_spec,
        "resampling": config["resampling"],
        "training": config["training"],
        "model": {"class": "xgboost.XGBClassifier", "parameters": config["model"]},
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "imbalanced_learn": imblearn.__version__,
            "xgboost": xgb.__version__,
            "uv_lock_sha256": sha256_file(ROOT / "uv.lock"),
        },
    }


def verify_saved_xgb_inference(
    *,
    model_paths: tuple[Path, ...],
    train_features,
    test_features,
    folds: np.ndarray,
    original_oof: np.ndarray,
    original_test: np.ndarray,
    submission_path: Path,
    expected_submission_sha256: str,
) -> dict[str, Any]:
    """Reload checkpoints only and prove that OOF/test/submission reproduce."""
    reproduced_oof = np.full_like(original_oof, np.nan)
    reproduced_test = np.zeros_like(original_test)
    for fold, model_path in enumerate(model_paths):
        model = xgb.XGBClassifier()
        model.load_model(model_path)
        valid = folds == fold
        reproduced_oof[valid] = model.predict_proba(train_features[valid])
        reproduced_test += model.predict_proba(test_features) / len(model_paths)
    labels = np.asarray(CLASS_LABELS)[reproduced_test.argmax(axis=1)]
    sample = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
    sample["SUBCLASS"] = labels
    reproduced_submission = submission_path.with_name("reproduced_submission.csv")
    sample.to_csv(reproduced_submission, index=False, lineterminator="\n")
    return {
        "data_hashes_match": True,
        "submission_sha256_match": sha256_file(reproduced_submission) == expected_submission_sha256,
        "oof_label_agreement": float(
            (reproduced_oof.argmax(axis=1) == original_oof.argmax(axis=1)).mean()
        ),
        "test_label_agreement": float(
            (reproduced_test.argmax(axis=1) == original_test.argmax(axis=1)).mean()
        ),
        "oof_max_abs_probability_difference": float(np.abs(reproduced_oof - original_oof).max()),
        "test_max_abs_probability_difference": float(np.abs(reproduced_test - original_test).max()),
        "probability_atol": 1e-6,
        "probability_rtol": 1e-6,
        "passed": bool(
            sha256_file(reproduced_submission) == expected_submission_sha256
            and np.allclose(reproduced_oof, original_oof, atol=1e-6, rtol=1e-6)
            and np.allclose(reproduced_test, original_test, atol=1e-6, rtol=1e-6)
        ),
        "reproduced_submission": str(reproduced_submission.relative_to(ROOT)),
    }


def main() -> None:
    started_at = datetime.now(timezone.utc)
    clock = time.perf_counter()
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    if context.experiment_id != "EXP-179":
        raise RuntimeError(f"Issue #179가 아닌 브랜치에서 실행 중입니다: {context.experiment_id}")
    clean_worktree_or_raise("EXP-179")

    feature_dir = ROOT / "data" / "processed" / f"{SLUG}_features"
    model_dir = ROOT / "models" / SLUG
    report_dir = ROOT / "reports" / SLUG
    reproducibility_dir = ROOT / "reproducibility" / SLUG
    for directory in (model_dir, report_dir, reproducibility_dir):
        directory.mkdir(parents=True, exist_ok=True)

    spec_manifest = materialize_frozen_feature_spec(
        root=ROOT, name="v1", output_dir=feature_dir, train_path=TRAIN, test_path=TEST
    )
    from scipy import sparse

    train_features = sparse.load_npz(feature_dir / "train_features.npz").tocsr()
    test_features = sparse.load_npz(feature_dir / "test_features.npz").tocsr()
    train = pd.read_csv(TRAIN, usecols=["ID", "SUBCLASS"], dtype=str)
    test = pd.read_csv(TEST, usecols=["ID"], dtype=str)
    split_path = ROOT / config["split"]["path"]
    split = train[["ID"]].merge(
        pd.read_csv(split_path, dtype={"ID": str, "fold": int}),
        on="ID",
        how="left",
        validate="one_to_one",
        sort=False,
    )
    if split["fold"].isna().any():
        raise RuntimeError("canonical split에 없는 train ID가 있습니다.")
    folds = split["fold"].to_numpy(dtype=np.int32)
    targets = train["SUBCLASS"].map({label: index for index, label in enumerate(CLASS_LABELS)}).to_numpy(dtype=np.int32)
    if pd.isna(targets).any():
        raise RuntimeError("고정 class order에 없는 SUBCLASS가 있습니다.")
    source_commit = git("rev-parse", "HEAD")
    owner = git("config", "user.name") or "unknown"
    resolved = build_resolved_config(
        context=context,
        owner=owner,
        source_commit=source_commit,
        started_at=started_at,
        feature_spec=spec_manifest,
        config=config,
    )

    resampler = FoldLocalSmote(
        k_neighbors=int(config["resampling"]["k_neighbors"]),
        sampling_strategy=str(config["resampling"]["sampling_strategy"]),
        base_seed=int(config["resampling"]["base_seed"]),
    )
    result = run_canonical_cv(
        train_features=train_features,
        test_features=test_features,
        targets=targets,
        folds=folds,
        adapter_factory=lambda fold: create_model_adapter("xgboost", dict(config["model"]), 42 + fold),
        model_dir=model_dir,
        balanced_sample_weight=bool(config["training"]["balanced_sample_weight"]),
        fold_train_resampler=resampler,
    )
    predictions = result.oof_probabilities.argmax(axis=1)
    fold_scores = np.asarray([row["macro_f1"] for row in result.fold_metrics])
    per_class = {
        label: float(score)
        for label, score in zip(
            CLASS_LABELS,
            f1_score(targets, predictions, average=None, labels=np.arange(len(CLASS_LABELS)), zero_division=0),
            strict=True,
        )
    }
    baseline = json.loads((ROOT / config["baseline"]["metrics_path"]).read_text(encoding="utf-8"))["oof"]
    macro_f1 = float(f1_score(targets, predictions, average="macro"))
    log_loss_value = float(log_loss(targets, result.oof_probabilities, labels=np.arange(len(CLASS_LABELS))))
    delta = {
        "macro_f1": macro_f1 - float(baseline["macro_f1"]),
        "fold_std": float(fold_scores.std()) - float(baseline["fold_std"]),
        "log_loss": log_loss_value - float(baseline["log_loss"]),
        "worst_per_class_f1": min(per_class[label] - baseline["per_class_f1"][label] for label in CLASS_LABELS),
    }
    acceptance = config["acceptance"]
    gates = {
        "macro_f1": delta["macro_f1"] >= acceptance["min_macro_f1_delta"],
        "fold_std": delta["fold_std"] < acceptance["max_fold_std_delta"],
        "log_loss": delta["log_loss"] <= 0,
        "lower_quartile_class_f1": all(
            per_class[label] >= baseline["per_class_f1"][label]
            for label in sorted(per_class, key=per_class.get)[:7]
        ),
    }
    metrics = {
        "experiment_id": "EXP-179",
        "record_role": "official",
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": 179,
        "parent_experiment": "EXP-094",
        "git_commit": source_commit,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "primary_metric": "macro_f1",
        "split_id": config["split"]["path"],
        "folds": list(result.fold_metrics),
        "oof": {
            "macro_f1": macro_f1,
            "fold_mean": float(fold_scores.mean()),
            "fold_std": float(fold_scores.std()),
            "accuracy": float(accuracy_score(targets, predictions)),
            "log_loss": log_loss_value,
            "per_class_f1": per_class,
            "confusion_matrix": confusion_matrix(targets, predictions, labels=np.arange(len(CLASS_LABELS))).tolist(),
        },
        "leaderboard": None,
        "runtime": {"seconds": time.perf_counter() - clock},
        "artifacts": {
            "feature_spec_manifest": str((feature_dir / "feature_spec_manifest.json").relative_to(ROOT)),
            "models": str(model_dir.relative_to(ROOT)),
        },
        "notes": "EXP-094 v1 + fold-local standard SMOTE; validation/test were not resampled.",
    }
    report_metrics = report_dir / "metrics.json"
    report_metrics.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validate_json_document(report_metrics, ROOT / "schemas" / "experiment_metrics.schema.json")
    oof_path = ROOT / "oof" / f"{SLUG}.csv"
    test_probability_path = ROOT / "preds" / f"{SLUG}_test_proba.csv"
    build_oof_probability_frame(
        ids=train["ID"].tolist(), true_labels=train["SUBCLASS"].tolist(), folds=folds,
        probabilities=result.oof_probabilities,
    ).to_csv(oof_path, index=False)
    build_test_probability_frame(ids=test["ID"].tolist(), probabilities=result.test_probabilities).to_csv(test_probability_path, index=False)
    submission = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
    submission["SUBCLASS"] = np.asarray(CLASS_LABELS)[result.test_probabilities.argmax(axis=1)]
    submission_path = ROOT / "submissions" / f"{SLUG}.csv"
    submission.to_csv(submission_path, index=False, lineterminator="\n")
    validate_submission(submission_path, TEST)
    records = write_model_run_records(
        root=ROOT,
        output_dir=reproducibility_dir,
        experiment_id="EXP-179",
        issue_number=179,
        source_commit=source_commit,
        resolved_config=resolved,
        metrics=metrics,
        data_files={"train": TRAIN, "test": TEST, "sample_submission": SAMPLE, "split": split_path},
        artifacts={
            "feature_spec_manifest": feature_dir / "feature_spec_manifest.json",
            "oof_probabilities": oof_path,
            "test_probabilities": test_probability_path,
            "submission": submission_path,
            **{f"checkpoint_fold_{fold}": path for fold, path in enumerate(result.model_paths)},
        },
        environment=resolved["environment"],
    )
    comparison = verify_saved_xgb_inference(
        model_paths=result.model_paths,
        train_features=train_features,
        test_features=test_features,
        folds=folds,
        original_oof=result.oof_probabilities,
        original_test=result.test_probabilities,
        submission_path=submission_path,
        expected_submission_sha256=sha256_file(submission_path),
    )
    comparison["oof_macro_f1_delta"] = 0.0
    comparison_path = reproducibility_dir / "comparison.json"
    comparison_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verification = {
        key: comparison[key]
        for key in (
            "data_hashes_match",
            "submission_sha256_match",
            "oof_label_agreement",
            "test_label_agreement",
            "probability_atol",
            "probability_rtol",
            "oof_macro_f1_delta",
            "passed",
        )
    }
    artifact_manifest = json.loads(records["artifact_manifest"].read_text(encoding="utf-8"))
    artifact_manifest.update(
        {
            "reproducibility_status": "INFERENCE_VERIFIED" if verification["passed"] else "FAILED",
            "verifier": "scripts/run_exp179_xgb_feature_spec_v1_smote.py",
            "verified_at": datetime.now(timezone.utc).isoformat(),
            "verification": verification,
        }
    )
    records["artifact_manifest"].write_text(
        json.dumps(artifact_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    validate_json_document(records["artifact_manifest"], ROOT / "schemas" / "reproducibility_manifest.schema.json")
    print(json.dumps({"metrics": str(report_metrics), "oof_macro_f1": macro_f1, "delta": delta, "gates": gates, "submission": str(submission_path), "inference_verified": verification["passed"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
