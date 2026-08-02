#!/usr/bin/env python
"""Run EXP-151: EXP-094 frozen features plus one log burden feature."""
from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import sparse
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss

from open_cancer.constants import CLASS_LABELS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.frozen_feature_specs import materialize_frozen_feature_spec
from open_cancer.hashing import sha256_file
from open_cancer.model_runner import create_model_adapter, run_canonical_cv
from open_cancer.validation import validate_json_document, validate_submission
from run_eda_violin import build_summary

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "exp151_burden_incremental.yaml"
TRAIN = ROOT / "data/raw/train.csv"
TEST = ROOT / "data/raw/test.csv"
SAMPLE = ROOT / "data/raw/sample_submission.csv"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def main() -> None:
    started = datetime.now(timezone.utc)
    clock = time.perf_counter()
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    if context.experiment_id != "EXP-151" or git("status", "--porcelain"):
        raise RuntimeError("EXP-151은 clean issue-151 브랜치에서만 실행해야 합니다.")
    slug = "exp151_mutated_gene_burden"
    feature_dir = ROOT / "data/processed" / f"{slug}_features"
    model_dir = ROOT / "models" / slug
    out_dir = ROOT / "reports" / slug
    repro_dir = ROOT / "reproducibility" / slug
    for path in (model_dir, out_dir, repro_dir):
        path.mkdir(parents=True, exist_ok=True)
    manifest = materialize_frozen_feature_spec(
        root=ROOT, name="v1", output_dir=feature_dir, train_path=TRAIN, test_path=TEST
    )
    x_train = sparse.load_npz(feature_dir / "train_features.npz").tocsr()
    x_test = sparse.load_npz(feature_dir / "test_features.npz").tocsr()
    train_burden = np.log1p(build_summary(TRAIN)["mutated_gene_count"].to_numpy(dtype=np.float32))
    test_burden = np.log1p(build_summary(TEST, with_label=False)["mutated_gene_count"].to_numpy(dtype=np.float32))
    x_train = sparse.hstack([x_train, sparse.csr_matrix(train_burden[:, None])], format="csr")
    x_test = sparse.hstack([x_test, sparse.csr_matrix(test_burden[:, None])], format="csr")
    train = pd.read_csv(TRAIN, usecols=["ID", "SUBCLASS"], dtype=str)
    test = pd.read_csv(TEST, usecols=["ID"], dtype=str)
    split_path = ROOT / config["split"]["path"]
    split = train[["ID"]].merge(pd.read_csv(split_path, dtype={"ID": str, "fold": int}), on="ID", how="left", validate="one_to_one", sort=False)
    folds = split["fold"].to_numpy(dtype=np.int32)
    targets = train["SUBCLASS"].map({label: i for i, label in enumerate(CLASS_LABELS)}).to_numpy(dtype=np.int32)
    params = dict(config["model"])
    params.pop("early_stopping_rounds", None)
    result = run_canonical_cv(
        train_features=x_train, test_features=x_test, targets=targets, folds=folds,
        adapter_factory=lambda fold: create_model_adapter("xgboost", params, 42 + fold),
        model_dir=model_dir, balanced_sample_weight=True,
    )
    pred = result.oof_probabilities.argmax(axis=1)
    f1 = f1_score(targets, pred, average="macro")
    fold_scores = np.asarray([row["macro_f1"] for row in result.fold_metrics])
    metrics = {
        "experiment_id": "EXP-151", "record_role": "official", "status": "COMPLETED",
        "owner": git("config", "user.name") or "unknown", "issue_number": 151,
        "parent_experiment": "EXP-094", "git_commit": git("rev-parse", "HEAD"),
        "started_at": started.isoformat(), "finished_at": datetime.now(timezone.utc).isoformat(),
        "primary_metric": "macro_f1", "split_id": str(config["split"]["path"]),
        "folds": list(result.fold_metrics),
        "oof": {"macro_f1": float(f1), "fold_mean": float(fold_scores.mean()), "fold_std": float(fold_scores.std()),
                "accuracy": float(accuracy_score(targets, pred)),
                "log_loss": float(log_loss(targets, result.oof_probabilities, labels=np.arange(len(CLASS_LABELS)))),
                "per_class_f1": {label: float(value) for label, value in zip(CLASS_LABELS, f1_score(targets, pred, average=None, labels=np.arange(len(CLASS_LABELS)), zero_division=0), strict=True)},
                "confusion_matrix": confusion_matrix(targets, pred, labels=np.arange(len(CLASS_LABELS))).tolist()},
        "artifacts": {"feature_spec_manifest": str((feature_dir / "feature_spec_manifest.json").relative_to(ROOT)),
                      "models": str(model_dir.relative_to(ROOT))},
        "runtime": {"seconds": time.perf_counter() - clock},
        "notes": "EXP-094 frozen Feature Spec + log1p(mutated_gene_count); test labels unused.",
    }
    metrics_path = out_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validate_json_document(metrics_path, ROOT / "schemas/experiment_metrics.schema.json")
    submission = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
    submission["SUBCLASS"] = np.asarray(CLASS_LABELS)[result.test_probabilities.argmax(axis=1)]
    submission_path = ROOT / "submissions" / f"{slug}.csv"
    submission.to_csv(submission_path, index=False, lineterminator="\n")
    validate_submission(submission_path, TEST)
    pd.DataFrame(result.oof_probabilities, columns=CLASS_LABELS).assign(ID=train.ID).to_csv(ROOT / "oof" / f"{slug}.csv", index=False)
    pd.DataFrame(result.test_probabilities, columns=CLASS_LABELS).assign(ID=test.ID).to_csv(ROOT / "preds" / f"{slug}_test_proba.csv", index=False)
    print(json.dumps({"metrics": str(metrics_path), "oof_macro_f1": float(f1), "submission": str(submission_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
