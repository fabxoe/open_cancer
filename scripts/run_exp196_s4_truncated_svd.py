#!/usr/bin/env python
"""Run EXP-196: fold-local TruncatedSVD low-dimensional comparator."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
import xgboost as xgb
import yaml
from scipy import sparse
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.checkpoint_selection import (
    audit_xgboost_validation_iterations,
    predict_xgboost_at_iteration,
    save_xgboost_iteration_checkpoint,
)
from open_cancer.constants import CLASS_LABELS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.frozen_feature_specs import materialize_frozen_feature_spec
from open_cancer.hashing import sha256_file, sha256_lines
from open_cancer.model_artifacts import (
    build_oof_probability_frame,
    build_test_probability_frame,
    write_model_run_records,
)
from open_cancer.validation import validate_json_document, validate_submission


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "exp196_s4_truncated_svd.yaml"
TRAIN = ROOT / "data" / "raw" / "train.csv"
TEST = ROOT / "data" / "raw" / "test.csv"
SAMPLE = ROOT / "data" / "raw" / "sample_submission.csv"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _joined_features(
    projected: np.ndarray,
    source: sparse.csr_matrix,
    passthrough_indices: np.ndarray,
) -> sparse.csr_matrix:
    return sparse.hstack(
        [sparse.csr_matrix(projected.astype(np.float32)), source[:, passthrough_indices]],
        format="csr",
        dtype=np.float32,
    )


def main() -> None:
    started_at = datetime.now(timezone.utc)
    timer = time.perf_counter()
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    if context.experiment_id != config["experiment_id"] or context.issue_number != config["issue_number"]:
        raise RuntimeError("config와 현재 Issue 브랜치의 EXP-ID가 일치하지 않습니다.")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("공식 실험은 tracked worktree가 clean한 상태에서만 실행합니다.")

    slug = str(config["slug"])
    feature_dir = ROOT / "data" / "processed" / f"{slug}_features"
    model_dir = ROOT / "models" / slug
    report_dir = ROOT / "reports" / slug
    repro_dir = ROOT / "reproducibility" / slug
    for directory in (model_dir, report_dir, repro_dir, ROOT / "oof", ROOT / "preds", ROOT / "submissions"):
        directory.mkdir(parents=True, exist_ok=True)

    spec_manifest = materialize_frozen_feature_spec(
        root=ROOT, name="v1", output_dir=feature_dir, train_path=TRAIN, test_path=TEST
    )
    train_features = sparse.load_npz(feature_dir / "train_features.npz").tocsr()
    test_features = sparse.load_npz(feature_dir / "test_features.npz").tocsr()
    feature_names = tuple(json.loads((feature_dir / "feature_names.json").read_text(encoding="utf-8")))
    gene_indices = np.asarray(
        [index for index, name in enumerate(feature_names) if name.endswith("__mutated")],
        dtype=np.int64,
    )
    prefixes = tuple(config["projection"]["passthrough_prefixes"])
    passthrough_indices = np.asarray(
        [index for index, name in enumerate(feature_names) if name.startswith(prefixes)],
        dtype=np.int64,
    )
    if len(gene_indices) != 4384:
        raise RuntimeError(f"raw mutation-presence 열이 4,384개가 아닙니다: {len(gene_indices)}")
    if len(passthrough_indices) == 0 or np.intersect1d(gene_indices, passthrough_indices).size:
        raise RuntimeError("SVD input과 passthrough feature 계약이 잘못됐습니다.")

    train = pd.read_csv(TRAIN, usecols=["ID", "SUBCLASS"], dtype=str)
    test = pd.read_csv(TEST, usecols=["ID"], dtype=str)
    split_path = ROOT / config["split"]["path"]
    folds = train[["ID"]].merge(
        pd.read_csv(split_path, dtype={"ID": str, "fold": int}),
        on="ID", how="left", validate="one_to_one", sort=False,
    )["fold"].to_numpy(dtype=np.int32)
    targets = train["SUBCLASS"].map(
        {label: index for index, label in enumerate(CLASS_LABELS)}
    ).to_numpy(dtype=np.int32)
    if pd.isna(targets).any() or set(np.unique(folds)) != set(range(5)):
        raise RuntimeError("고정 class order 또는 canonical split 계약이 깨졌습니다.")

    oof = np.full((len(train), len(CLASS_LABELS)), np.nan, dtype=np.float64)
    test_probabilities = np.zeros((len(test), len(CLASS_LABELS)), dtype=np.float64)
    fold_metrics: list[dict[str, object]] = []
    artifact_paths: dict[str, Path] = {}
    fold_scores: list[float] = []
    components = int(config["projection"]["n_components"])

    for fold in range(5):
        train_mask = folds != fold
        valid_mask = folds == fold
        projector = TruncatedSVD(
            n_components=components,
            algorithm=str(config["projection"]["algorithm"]),
            n_iter=int(config["projection"]["n_iter"]),
            random_state=int(config["seed"]) + fold,
        )
        gene_train = train_features[train_mask][:, gene_indices]
        gene_valid = train_features[valid_mask][:, gene_indices]
        gene_test = test_features[:, gene_indices]
        projected_train = projector.fit_transform(gene_train)
        x_train = _joined_features(projected_train, train_features[train_mask], passthrough_indices)
        x_valid = _joined_features(projector.transform(gene_valid), train_features[valid_mask], passthrough_indices)
        x_test = _joined_features(projector.transform(gene_test), test_features, passthrough_indices)
        y_train = targets[train_mask]
        y_valid = targets[valid_mask]

        model = xgb.XGBClassifier(**dict(config["model"]), random_state=int(config["seed"]) + fold)
        sample_weight = compute_sample_weight("balanced", y_train)
        model.fit(x_train, y_train, sample_weight=sample_weight, eval_set=[(x_valid, y_valid)], verbose=False)
        audit = audit_xgboost_validation_iterations(model, x_valid, y_valid)
        selected_iteration = int(audit["macro_f1_best"]["iteration"])
        valid_probability = predict_xgboost_at_iteration(model, x_valid, selected_iteration)
        test_probability = predict_xgboost_at_iteration(model, x_test, selected_iteration)
        oof[valid_mask] = valid_probability
        test_probabilities += test_probability / 5

        model_path = model_dir / f"fold_{fold:02d}.json"
        projector_path = model_dir / f"fold_{fold:02d}_truncated_svd.joblib"
        audit_path = model_dir / f"fold_{fold:02d}_checkpoint_audit.json"
        projection_path = model_dir / f"fold_{fold:02d}_projection.json"
        save_xgboost_iteration_checkpoint(model, model_path, selected_iteration)
        joblib.dump(projector, projector_path)
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        projection_record = {
            "fold": fold,
            "fit_scope": "outer_fold_train_only",
            "input_feature_count": int(len(gene_indices)),
            "component_count": components,
            "passthrough_feature_count": int(len(passthrough_indices)),
            "output_feature_count": int(x_train.shape[1]),
            "gene_feature_order_sha256": sha256_lines(feature_names[index] for index in gene_indices),
            "passthrough_feature_order_sha256": sha256_lines(feature_names[index] for index in passthrough_indices),
            "explained_variance_ratio_sum": float(projector.explained_variance_ratio_.sum()),
        }
        projection_path.write_text(json.dumps(projection_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        fold_macro = float(f1_score(y_valid, valid_probability.argmax(axis=1), average="macro", zero_division=0))
        fold_scores.append(fold_macro)
        fold_metrics.append({
            "fold": fold,
            "macro_f1": fold_macro,
            "accuracy": float(accuracy_score(y_valid, valid_probability.argmax(axis=1))),
            "log_loss": float(log_loss(y_valid, valid_probability, labels=np.arange(len(CLASS_LABELS)))),
            "best_iteration": selected_iteration,
            "feature_selection": {
                "method": "truncated_svd_projection",
                **projection_record,
                "projection_artifact": str(projection_path.relative_to(ROOT)),
                "checkpoint_audit_artifact": str(audit_path.relative_to(ROOT)),
            },
        })
        artifact_paths.update({
            f"checkpoint_fold_{fold}": model_path,
            f"projector_fold_{fold}": projector_path,
            f"projection_fold_{fold}": projection_path,
            f"checkpoint_audit_fold_{fold}": audit_path,
        })
        print(f"fold {fold}: Macro F1={fold_macro:.6f}, iteration={selected_iteration}, variance={projection_record['explained_variance_ratio_sum']:.4f}", flush=True)

    if np.isnan(oof).any():
        raise RuntimeError("OOF 확률이 완성되지 않았습니다.")
    prediction = oof.argmax(axis=1)
    per_class = {
        label: float(value) for label, value in zip(
            CLASS_LABELS,
            f1_score(targets, prediction, average=None, labels=np.arange(len(CLASS_LABELS)), zero_division=0),
            strict=True,
        )
    }
    baseline = json.loads((ROOT / config["baseline"]["metrics_path"]).read_text(encoding="utf-8"))["oof"]
    macro_f1 = float(f1_score(targets, prediction, average="macro", zero_division=0))
    fold_std = float(np.std(fold_scores))
    logloss = float(log_loss(targets, oof, labels=np.arange(len(CLASS_LABELS))))
    delta = {
        "macro_f1": macro_f1 - float(baseline["macro_f1"]),
        "fold_std": fold_std - float(baseline["fold_std"]),
        "log_loss": logloss - float(baseline["log_loss"]),
        "worst_per_class_f1": min(per_class[label] - float(baseline["per_class_f1"][label]) for label in CLASS_LABELS),
    }
    accepted = (
        delta["macro_f1"] >= float(config["acceptance"]["min_macro_f1_delta"])
        and delta["fold_std"] < float(config["acceptance"]["max_fold_std_delta"])
        and delta["worst_per_class_f1"] >= -float(config["acceptance"]["max_per_class_f1_drop"])
    )
    decision = "COMPARATOR_CANDIDATE" if accepted else "ARCHIVE"
    owner = git("config", "user.name") or "unknown"
    source_commit = git("rev-parse", "HEAD")
    finished_at = datetime.now(timezone.utc)
    metrics = {
        "experiment_id": context.experiment_id,
        "record_role": "official",
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": context.issue_number,
        "parent_experiment": config["parent_experiment"],
        "git_commit": source_commit,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "primary_metric": "macro_f1",
        "split_id": config["split"]["path"],
        "folds": fold_metrics,
        "oof": {
            "macro_f1": macro_f1,
            "fold_mean": float(np.mean(fold_scores)),
            "fold_std": fold_std,
            "accuracy": float(accuracy_score(targets, prediction)),
            "log_loss": logloss,
            "per_class_f1": per_class,
            "confusion_matrix": confusion_matrix(targets, prediction, labels=np.arange(len(CLASS_LABELS))).tolist(),
        },
        "baseline_delta": delta,
        "decision": decision,
        "leaderboard": None,
        "runtime": {"seconds": time.perf_counter() - timer},
        "artifacts": {"feature_spec_manifest": str((feature_dir / "feature_spec_manifest.json").relative_to(ROOT)), "models": str(model_dir.relative_to(ROOT))},
        "notes": "TruncatedSVD fit uses outer-train mutation-presence only; validation/test reuse the fold projector. Macro F1 checkpoint selection uses validation only.",
    }
    metrics_path = report_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validate_json_document(metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json")
    oof_path = ROOT / "oof" / f"{slug}.csv"
    test_probability_path = ROOT / "preds" / f"{slug}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{slug}.csv"
    build_oof_probability_frame(ids=train["ID"].tolist(), true_labels=train["SUBCLASS"].tolist(), folds=folds, probabilities=oof).to_csv(oof_path, index=False)
    build_test_probability_frame(ids=test["ID"].tolist(), probabilities=test_probabilities).to_csv(test_probability_path, index=False)
    submission = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
    submission["SUBCLASS"] = np.asarray(CLASS_LABELS)[test_probabilities.argmax(axis=1)]
    submission.to_csv(submission_path, index=False, lineterminator="\n")
    validate_submission(submission_path, TEST)
    resolved = {
        "experiment": {"experiment_id": context.experiment_id, "issue_number": context.issue_number, "branch": context.branch, "owner": owner, "parent_experiment": config["parent_experiment"], "source_commit": source_commit, "started_at": started_at.isoformat()},
        "data": {"train": {"path": "data/raw/train.csv", "sha256": sha256_file(TRAIN)}, "test": {"path": "data/raw/test.csv", "sha256": sha256_file(TEST)}, "sample_submission": {"path": "data/raw/sample_submission.csv", "sha256": sha256_file(SAMPLE)}, "class_order": list(CLASS_LABELS)},
        "split": {**config["split"], "sha256": sha256_file(split_path), "method": "StratifiedKFold"},
        "base_feature_spec": spec_manifest,
        "projection": config["projection"],
        "training": config["training"],
        "model": {"class": "xgboost.XGBClassifier", "parameters": config["model"]},
        "environment": {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__, "pandas": pd.__version__, "scikit_learn": sklearn.__version__, "xgboost": xgb.__version__, "uv_lock_sha256": sha256_file(ROOT / "uv.lock")},
    }
    write_model_run_records(
        root=ROOT, output_dir=repro_dir, experiment_id=context.experiment_id or "", issue_number=context.issue_number or 0,
        source_commit=source_commit, resolved_config=resolved, metrics=metrics,
        data_files={"train": TRAIN, "test": TEST, "sample_submission": SAMPLE, "split": split_path},
        artifacts={"feature_spec_manifest": feature_dir / "feature_spec_manifest.json", "oof_probabilities": oof_path, "test_probabilities": test_probability_path, "submission": submission_path, **artifact_paths},
        environment=resolved["environment"],
    )
    print(json.dumps({"experiment_id": context.experiment_id, "oof_macro_f1": macro_f1, "delta": delta, "decision": decision, "metrics": str(metrics_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
