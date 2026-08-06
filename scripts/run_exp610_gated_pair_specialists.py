#!/usr/bin/env python
"""Run EXP-610: gated pair specialists on the fixed EXP-527 26-class base."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
import yaml
from scipy import sparse
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, log_loss
from sklearn.preprocessing import LabelEncoder

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.feature_family import drop_named_base_features
from open_cancer.hashing import sha256_file
from open_cancer.validation import validate_submission
from run_exp527_parser_v4_class_cosine_loo import LeaveOneOutClassCosineFoldBuilder
from run_exp592_hierarchical_pair_specialists import fit_specialist


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "exp610_gated_pair_specialists.yaml"
TRAIN = ROOT / "data" / "raw" / "train.csv"
TEST = ROOT / "data" / "raw" / "test.csv"
SAMPLE = ROOT / "data" / "raw" / "sample_submission.csv"
PARENT_SLUG = "exp527_parser_v4_class_cosine_loo"
FEATURE_DIR = ROOT / "data" / "processed" / f"{PARENT_SLUG}_features"
MODEL_DIR = ROOT / "models" / PARENT_SLUG
PAIRS = (("KIPAN", "KIRC"), ("GBMLGG", "LGG"))


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def gated_swap(
    base_probability: np.ndarray,
    features: sparse.csr_matrix,
    specialists: dict[tuple[str, str], xgb.XGBClassifier],
) -> tuple[np.ndarray, dict[str, int]]:
    adjusted = np.asarray(base_probability, dtype=np.float32).copy()
    base_top1 = adjusted.argmax(axis=1)
    counts: dict[str, int] = {}
    for pair in PAIRS:
        left_idx, right_idx = (CLASS_LABELS.index(label) for label in pair)
        gate = np.isin(base_top1, (left_idx, right_idx))
        conditional = specialists[pair].predict_proba(features)[:, 1]
        specialist_top1 = np.where(conditional >= 0.5, right_idx, left_idx)
        disagree = gate & (specialist_top1 != base_top1)
        tmp = adjusted[disagree, left_idx].copy()
        adjusted[disagree, left_idx] = adjusted[disagree, right_idx]
        adjusted[disagree, right_idx] = tmp
        key = "/".join(pair)
        counts[f"{key}_gated_rows"] = int(gate.sum())
        counts[f"{key}_changed_rows"] = int(disagree.sum())
    return adjusted, counts


def main() -> None:
    started = datetime.now(timezone.utc)
    started_perf = time.perf_counter()
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    if git("status", "--porcelain"):
        raise RuntimeError("공식 실험은 source/config commit 후 clean worktree에서 실행해야 합니다.")

    slug = f"exp{context.issue_number:03d}_{config['slug']}"
    report_dir = ROOT / "reports" / slug
    repro_dir = ROOT / "reproducibility" / slug
    output_model_dir = ROOT / "models" / slug
    oof_path = ROOT / "oof" / f"{slug}.csv"
    pred_path = ROOT / "preds" / f"{slug}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{slug}.csv"
    resolved_path = repro_dir / "config.resolved.yaml"
    for path in (report_dir, repro_dir, output_model_dir, oof_path.parent, pred_path.parent, submission_path.parent):
        path.mkdir(parents=True, exist_ok=True)

    required = [
        FEATURE_DIR / "train_features.npz",
        FEATURE_DIR / "test_features.npz",
        FEATURE_DIR / "feature_names.json",
        *[MODEL_DIR / f"fold_{fold:02d}.json" for fold in range(5)],
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("EXP-527 artifacts missing: " + ", ".join(missing))

    train_meta = pd.read_csv(TRAIN, usecols=["ID", "SUBCLASS"], dtype=str)
    test_meta = pd.read_csv(TEST, usecols=["ID"], dtype=str)
    folds = pd.read_csv(ROOT / config["split"]["path"], dtype={"ID": str, "fold": int})
    train = train_meta.merge(folds, on="ID", how="left", validate="one_to_one", sort=False)
    if not train["ID"].equals(train_meta["ID"]) or train["fold"].isna().any():
        raise ValueError("canonical fold merge changed train order")

    x_all = sparse.load_npz(FEATURE_DIR / "train_features.npz").tocsr()
    x_test = sparse.load_npz(FEATURE_DIR / "test_features.npz").tocsr()
    feature_names = tuple(json.loads((FEATURE_DIR / "feature_names.json").read_text()))
    encoder = LabelEncoder().fit(CLASS_LABELS)
    target = encoder.transform(train["SUBCLASS"]).astype(np.int32)
    builder = LeaveOneOutClassCosineFoldBuilder()
    params = dict(config["specialists"]["model"])

    oof = np.full((len(train), len(CLASS_LABELS)), np.nan, dtype=np.float32)
    test_probability = np.zeros((len(test_meta), len(CLASS_LABELS)), dtype=np.float32)
    fold_records: list[dict[str, object]] = []

    for fold in range(config["split"]["n_splits"]):
        valid_mask = train["fold"].eq(fold).to_numpy()
        train_idx, valid_idx = np.flatnonzero(~valid_mask), np.flatnonzero(valid_mask)
        extra = builder(
            fold=fold,
            train_indices=train_idx,
            valid_indices=valid_idx,
            base_train=x_all[train_idx],
            base_validation=x_all[valid_idx],
            base_test=x_test,
            base_feature_names=feature_names,
            target=target[train_idx],
        )
        base_train, base_valid, base_test, _ = drop_named_base_features(
            x_all[train_idx], x_all[valid_idx], x_test, feature_names,
            extra.base_feature_names_to_drop, allow_empty=bool(extra.feature_names),
        )
        x_train = sparse.hstack([base_train, extra.train], format="csr", dtype=np.float32)
        x_valid = sparse.hstack([base_valid, extra.validation], format="csr", dtype=np.float32)
        x_test_fold = sparse.hstack([base_test, extra.test], format="csr", dtype=np.float32)

        base_model = xgb.XGBClassifier()
        base_model.load_model(MODEL_DIR / f"fold_{fold:02d}.json")
        labels = train["SUBCLASS"].to_numpy()[train_idx]
        specialists: dict[tuple[str, str], xgb.XGBClassifier] = {}
        specialist_records: list[dict[str, object]] = []
        for pair_index, pair in enumerate(PAIRS):
            model, record = fit_specialist(
                x_train, labels, positive_label=pair[1], pair=pair,
                parameters=params, seed=config["seed"] + fold + pair_index * 100,
            )
            model.save_model(output_model_dir / f"{'_'.join(pair).lower()}_fold_{fold:02d}.json")
            specialists[pair] = model
            specialist_records.append(record)

        valid_base = base_model.predict_proba(x_valid).astype(np.float32)
        valid_adjusted, valid_counts = gated_swap(valid_base, x_valid, specialists)
        fold_test_base = base_model.predict_proba(x_test_fold).astype(np.float32)
        fold_test_adjusted, test_counts = gated_swap(fold_test_base, x_test_fold, specialists)
        oof[valid_idx] = valid_adjusted
        test_probability += fold_test_adjusted / config["split"]["n_splits"]

        valid_target = target[valid_idx]
        base_pred = valid_base.argmax(axis=1)
        adjusted_pred = valid_adjusted.argmax(axis=1)
        fold_records.append({
            "fold": fold,
            "macro_f1": float(f1_score(valid_target, adjusted_pred, labels=np.arange(26), average="macro", zero_division=0)),
            "accuracy": float(accuracy_score(valid_target, adjusted_pred)),
            "log_loss": float(log_loss(valid_target, valid_adjusted, labels=np.arange(26))),
            "best_iteration": None,
            "model_parameters": params,
            "resampling": {
                "base_macro_f1": float(f1_score(valid_target, base_pred, labels=np.arange(26), average="macro", zero_division=0)),
                "valid_gate_counts": valid_counts,
                "test_gate_counts": test_counts,
                "specialists": specialist_records,
            },
        })

    if np.isnan(oof).any():
        raise RuntimeError("OOF contains NaN")
    oof_pred = oof.argmax(axis=1)
    test_probability /= test_probability.sum(axis=1, keepdims=True)
    test_pred = test_probability.argmax(axis=1)
    report = classification_report(target, oof_pred, labels=np.arange(26), target_names=CLASS_LABELS, output_dict=True, zero_division=0)
    macro = float(f1_score(target, oof_pred, labels=np.arange(26), average="macro", zero_division=0))
    metrics = {
        "experiment_id": config["experiment_id"],
        "issue_number": context.issue_number,
        "owner": "fabxoe",
        "record_role": config["record_role"],
        "parent_experiment": config["parent_experiment"],
        "status": "COMPLETED",
        "primary_metric": "macro_f1",
        "split_id": config["split"]["path"],
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git("rev-parse", "HEAD"),
        "oof": {
            "macro_f1": macro,
            "accuracy": float(accuracy_score(target, oof_pred)),
            "log_loss": float(log_loss(target, oof, labels=np.arange(26))),
            "fold_mean": float(np.mean([row["macro_f1"] for row in fold_records])),
            "fold_std": float(np.std([row["macro_f1"] for row in fold_records])),
            "per_class_f1": {label: float(report[label]["f1-score"]) for label in CLASS_LABELS},
            "confusion_matrix": confusion_matrix(target, oof_pred, labels=np.arange(26)).tolist(),
        },
        "folds": fold_records,
        "runtime": {"seconds": time.perf_counter() - started_perf, "hardware": "local-cpu"},
        "artifacts": {
            "resolved_config": str(resolved_path.relative_to(ROOT)),
            "oof": str(oof_path.relative_to(ROOT)),
            "test_probability": str(pred_path.relative_to(ROOT)),
            "submission": str(submission_path.relative_to(ROOT)),
            "models": str(output_model_dir.relative_to(ROOT)),
        },
        "notes": config["notes"],
    }

    pd.DataFrame({"ID": train["ID"], **{col: oof[:, idx] for idx, col in enumerate(PROBABILITY_COLUMNS)}}).to_csv(oof_path, index=False)
    pd.DataFrame({"ID": test_meta["ID"], **{col: test_probability[:, idx] for idx, col in enumerate(PROBABILITY_COLUMNS)}}).to_csv(pred_path, index=False)
    sample = pd.read_csv(SAMPLE, dtype=str)
    submission = pd.DataFrame({"ID": sample["ID"], "SUBCLASS": encoder.inverse_transform(test_pred)})
    submission.to_csv(submission_path, index=False)
    validate_submission(submission_path, TEST, expected_classes=CLASS_LABELS)
    metrics["artifacts"]["submission_sha256"] = sha256_file(submission_path)
    write_json(report_dir / "metrics.json", metrics)
    (repro_dir / "config.resolved.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    write_json(repro_dir / "original_metrics.json", metrics)
    write_json(repro_dir / "comparison.json", {
        "submission_sha256": sha256_file(submission_path),
        "probability_row_sum_max_abs_error": float(np.max(np.abs(test_probability.sum(axis=1) - 1.0))),
    })
    print(json.dumps({"macro_f1": macro, "runtime_seconds": metrics["runtime"]["seconds"], "submission": str(submission_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
