#!/usr/bin/env python
"""Run EXP-191: fold-local categorical summaries for correlated gene pairs."""

from __future__ import annotations

import json
import platform
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
from open_cancer.correlation_pair_features import (
    append_pair_categorical_features,
    pair_feature_names,
)
from open_cancer.experiment import resolve_experiment_context
from open_cancer.fold_feature_selection import (
    FoldFeatureSelection,
    PhiJaccardGreedyPruner,
    write_fold_feature_selection,
)
from open_cancer.frozen_feature_specs import materialize_frozen_feature_spec
from open_cancer.hashing import sha256_file
from open_cancer.model_artifacts import (
    build_oof_probability_frame,
    build_test_probability_frame,
    write_model_run_records,
)
from open_cancer.model_runner import create_model_adapter
from open_cancer.validation import validate_json_document, validate_submission
from run_exp188_c1_phi_jaccard_pruning import compact_fold_metrics, git, verdict


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "exp191_r1_correlation_pair_summary.yaml"
TRAIN = ROOT / "data" / "raw" / "train.csv"
TEST = ROOT / "data" / "raw" / "test.csv"
SAMPLE = ROOT / "data" / "raw" / "sample_submission.csv"


def build_resolved_config(
    *,
    config: dict[str, Any],
    context: Any,
    owner: str,
    source_commit: str,
    started_at: datetime,
    feature_spec: dict[str, Any],
) -> dict[str, Any]:
    return {
        "experiment": {
            "experiment_id": context.experiment_id,
            "issue_number": context.issue_number,
            "branch": context.branch,
            "owner": owner,
            "parent_experiment": config["parent_experiment"],
            "source_commit": source_commit,
            "started_at": started_at.isoformat(),
        },
        "data": {
            "train": {"path": "data/raw/train.csv", "sha256": sha256_file(TRAIN)},
            "test": {"path": "data/raw/test.csv", "sha256": sha256_file(TEST)},
            "sample_submission": {"path": "data/raw/sample_submission.csv", "sha256": sha256_file(SAMPLE)},
            "class_order": list(CLASS_LABELS),
        },
        "split": {
            **config["split"],
            "sha256": sha256_file(ROOT / config["split"]["path"]),
            "method": "StratifiedKFold",
        },
        "base_feature_spec": feature_spec,
        "pair_selection": config["pair_selection"],
        "training": config["training"],
        "model": {"class": "xgboost.XGBClassifier", "parameters": config["model"]},
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


def main() -> None:
    started_at = datetime.now(timezone.utc)
    timer = time.perf_counter()
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    if context.experiment_id != config["experiment_id"] or context.issue_number != config["issue_number"]:
        raise RuntimeError("EXP-191 config와 현재 Issue 브랜치가 일치하지 않습니다.")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("공식 실험은 tracked worktree가 clean한 상태에서만 실행합니다.")

    slug = str(config["slug"])
    feature_dir = ROOT / "data" / "processed" / f"{slug}_features"
    model_dir = ROOT / "models" / slug
    report_dir = ROOT / "reports" / slug
    repro_dir = ROOT / "reproducibility" / slug
    for directory in (model_dir, report_dir, repro_dir):
        directory.mkdir(parents=True, exist_ok=True)

    spec_manifest = materialize_frozen_feature_spec(
        root=ROOT, name="v1", output_dir=feature_dir, train_path=TRAIN, test_path=TEST
    )
    train_features = sparse.load_npz(feature_dir / "train_features.npz").tocsr()
    test_features = sparse.load_npz(feature_dir / "test_features.npz").tocsr()
    feature_names = tuple(json.loads((feature_dir / "feature_names.json").read_text(encoding="utf-8")))
    train = pd.read_csv(TRAIN, usecols=["ID", "SUBCLASS"], dtype=str)
    test = pd.read_csv(TEST, usecols=["ID"], dtype=str)
    split_path = ROOT / config["split"]["path"]
    folds = train[["ID"]].merge(
        pd.read_csv(split_path, dtype={"ID": str, "fold": int}),
        on="ID", how="left", validate="one_to_one", sort=False,
    )["fold"].to_numpy(dtype=np.int32)
    targets = train["SUBCLASS"].map({label: index for index, label in enumerate(CLASS_LABELS)}).to_numpy(dtype=np.int32)
    if pd.isna(targets).any() or set(np.unique(folds)) != set(range(5)):
        raise RuntimeError("고정 class order 또는 canonical split 계약이 깨졌습니다.")

    selection_config = config["pair_selection"]
    selector = PhiJaccardGreedyPruner(
        phi_min=float(selection_config["phi_min"]),
        jaccard_min=float(selection_config["jaccard_min"]),
        min_joint_count=int(selection_config["min_joint_count"]),
    )
    oof = np.full((len(train), len(CLASS_LABELS)), np.nan, dtype=np.float64)
    test_probabilities = np.zeros((len(test), len(CLASS_LABELS)), dtype=np.float64)
    fold_metrics: list[dict[str, Any]] = []
    model_paths: list[Path] = []
    pair_spec_paths: list[Path] = []

    for fold in range(5):
        valid = folds == fold
        fit = ~valid
        selection = selector.select(train_features[fit], targets[fit], feature_names, fold)
        pairs = list(selection.metadata["matched_pairs"])
        added_names = pair_feature_names(pairs)
        expanded_names = (*feature_names, *added_names)
        train_matrix = append_pair_categorical_features(train_features[fit], feature_names, pairs)
        valid_matrix = append_pair_categorical_features(train_features[valid], feature_names, pairs)
        test_matrix = append_pair_categorical_features(test_features, feature_names, pairs)
        if train_matrix.shape[1] != len(expanded_names):
            raise RuntimeError("R1 확장 feature 이름과 matrix 차원이 다릅니다.")

        metadata = dict(selection.metadata)
        metadata.update({
            "selector": "phi_jaccard_pair_categorical_summary",
            "original_feature_count": len(feature_names),
            "pair_feature_count": len(added_names),
            "expanded_feature_count": len(expanded_names),
            "pair_feature_names": list(added_names),
        })
        pair_spec_path = write_fold_feature_selection(
            selection=FoldFeatureSelection(tuple(range(len(expanded_names))), metadata),
            feature_names=expanded_names,
            path=model_dir / f"fold_{fold:02d}_pair_features.json",
        )
        pair_spec_relative = str(pair_spec_path.relative_to(ROOT))
        metadata["candidate_pairs_artifact"] = pair_spec_relative
        metadata["matched_pairs_artifact"] = pair_spec_relative
        adapter = create_model_adapter("xgboost", dict(config["model"]), int(config["seed"]) + fold)
        sample_weight = compute_sample_weight(class_weight="balanced", y=targets[fit])
        adapter.fit(train_matrix, targets[fit], valid_matrix, targets[valid], sample_weight)
        valid_probabilities = adapter.predict_proba(valid_matrix)
        oof[valid] = valid_probabilities
        test_probabilities += adapter.predict_proba(test_matrix) / 5
        model_path = model_dir / f"fold_{fold:02d}{adapter.file_suffix}"
        adapter.save(model_path)
        pair_spec_paths.append(pair_spec_path)
        model_paths.append(model_path)
        fold_metrics.append({
            "fold": fold,
            "macro_f1": float(f1_score(targets[valid], valid_probabilities.argmax(axis=1), average="macro")),
            "accuracy": float(accuracy_score(targets[valid], valid_probabilities.argmax(axis=1))),
            "log_loss": float(log_loss(targets[valid], valid_probabilities, labels=np.arange(len(CLASS_LABELS)))),
            "best_iteration": adapter.best_iteration,
            "feature_selection": metadata,
        })

    if np.isnan(oof).any():
        raise RuntimeError("OOF 확률이 모두 채워지지 않았습니다.")
    predictions = oof.argmax(axis=1)
    fold_scores = np.asarray([record["macro_f1"] for record in fold_metrics])
    per_class = {
        label: float(value)
        for label, value in zip(
            CLASS_LABELS,
            f1_score(targets, predictions, average=None, labels=np.arange(len(CLASS_LABELS)), zero_division=0),
            strict=True,
        )
    }
    baseline = json.loads((ROOT / config["baseline"]["metrics_path"]).read_text(encoding="utf-8"))["oof"]
    macro_f1 = float(f1_score(targets, predictions, average="macro"))
    log_loss_value = float(log_loss(targets, oof, labels=np.arange(len(CLASS_LABELS))))
    delta = {
        "macro_f1": macro_f1 - float(baseline["macro_f1"]),
        "fold_std": float(fold_scores.std()) - float(baseline["fold_std"]),
        "log_loss": log_loss_value - float(baseline["log_loss"]),
        "worst_per_class_f1": min(per_class[label] - float(baseline["per_class_f1"][label]) for label in CLASS_LABELS),
    }
    owner = git("config", "user.name") or "unknown"
    source_commit = git("rev-parse", "HEAD")
    resolved = build_resolved_config(
        config=config, context=context, owner=owner, source_commit=source_commit,
        started_at=started_at, feature_spec=spec_manifest,
    )
    metrics = {
        "experiment_id": context.experiment_id,
        "record_role": "official",
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": context.issue_number,
        "parent_experiment": config["parent_experiment"],
        "git_commit": source_commit,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "primary_metric": "macro_f1",
        "split_id": config["split"]["path"],
        "folds": compact_fold_metrics(fold_metrics, model_dir=model_dir),
        "oof": {
            "macro_f1": macro_f1,
            "fold_mean": float(fold_scores.mean()),
            "fold_std": float(fold_scores.std()),
            "accuracy": float(accuracy_score(targets, predictions)),
            "log_loss": log_loss_value,
            "per_class_f1": per_class,
            "confusion_matrix": confusion_matrix(targets, predictions, labels=np.arange(len(CLASS_LABELS))).tolist(),
        },
        "baseline_delta": delta,
        "decision": verdict(delta=delta, acceptance=config["acceptance"]),
        "leaderboard": None,
        "runtime": {"seconds": time.perf_counter() - timer},
        "artifacts": {
            "feature_spec_manifest": str((feature_dir / "feature_spec_manifest.json").relative_to(ROOT)),
            "models": str(model_dir.relative_to(ROOT)),
        },
        "notes": "R1 pairs are fit only on outer-train; original v1 features are retained and three categorical pair states are appended.",
    }
    metrics_path = report_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validate_json_document(metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json")
    oof_path = ROOT / "oof" / f"{slug}.csv"
    test_path = ROOT / "preds" / f"{slug}_test_proba.csv"
    build_oof_probability_frame(ids=train["ID"].tolist(), true_labels=train["SUBCLASS"].tolist(), folds=folds, probabilities=oof).to_csv(oof_path, index=False)
    build_test_probability_frame(ids=test["ID"].tolist(), probabilities=test_probabilities).to_csv(test_path, index=False)
    submission = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
    submission["SUBCLASS"] = np.asarray(CLASS_LABELS)[test_probabilities.argmax(axis=1)]
    submission_path = ROOT / "submissions" / f"{slug}.csv"
    submission.to_csv(submission_path, index=False, lineterminator="\n")
    validate_submission(submission_path, TEST)
    metrics["artifacts"].update({
        "oof_probabilities": str(oof_path.relative_to(ROOT)),
        "test_probabilities": str(test_path.relative_to(ROOT)),
        "submission": str(submission_path.relative_to(ROOT)),
    })
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_model_run_records(
        root=ROOT, output_dir=repro_dir, experiment_id=context.experiment_id or "", issue_number=context.issue_number or 0,
        source_commit=source_commit, resolved_config=resolved, metrics=metrics,
        data_files={"train": TRAIN, "test": TEST, "sample_submission": SAMPLE, "split": split_path},
        artifacts={
            "feature_spec_manifest": feature_dir / "feature_spec_manifest.json",
            "oof_probabilities": oof_path,
            "test_probabilities": test_path,
            "submission": submission_path,
            **{f"checkpoint_fold_{fold}": path for fold, path in enumerate(model_paths)},
            **{f"pair_features_fold_{fold}": path for fold, path in enumerate(pair_spec_paths)},
        },
        environment=resolved["environment"],
    )
    print(json.dumps({"experiment_id": context.experiment_id, "oof_macro_f1": macro_f1, "delta": delta, "decision": metrics["decision"], "metrics": str(metrics_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
