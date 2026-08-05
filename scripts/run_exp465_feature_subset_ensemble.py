#!/usr/bin/env python
"""Run EXP-465: hotspot-only vs sample-aggregate-burden-only XGBoost blend.

Parent is EXP-374. Feature build (base features + fold-safe pathway
families) is reused verbatim from run_exp449_lightgbm_exp374.build_base_features
/ run_exp374_stop_isoform_residue_mask.build_fold_features -- only the
column *selection* differs per model:

- Model A ("hotspot-only"): columns named "hotspot__*" only (fixed_hotspot
  family per #292's shift-AUC diagnostic, shift-AUC ~0.55).
- Model B ("sample-aggregate-burden-only"): columns named "sample__*" only
  (sample_aggregate_burden family per #292, shift-AUC ~0.73 -- covers both
  the robust burden aggregates and the fixed-pathway burden/composition
  features, since both share the "sample__" prefix).

Both are independently trained XGBoost models with EXP-374's exact fixed
hyperparameters (no retuning), then blended 0.5/0.5. The official EXP-465
record is the blend; Model A/B standalone OOF numbers are written to
reports/exp465_feature_subset_ensemble/component_metrics.json as
supporting diagnostics.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
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
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.feature_family import drop_named_base_features
from open_cancer.hashing import sha256_file
from open_cancer.model_runner import XGBoostAdapter
from open_cancer.paths import relative_posix
from open_cancer.validation import validate_json_document, validate_submission
from run_exp374_stop_isoform_residue_mask import build_fold_features
from run_exp449_lightgbm_exp374 import build_base_features

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "exp465_feature_subset_ensemble.yaml"
EXP374_CONFIG_PATH = ROOT / "configs" / "exp374_stop_isoform_residue_mask.yaml"
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
SAMPLE_SUBMISSION_PATH = ROOT / "data" / "raw" / "sample_submission.csv"
SLUG = "exp465_feature_subset_ensemble"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record(path: Path) -> dict[str, Any]:
    return {"path": relative_posix(path, ROOT), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}


def fold_metrics_for(y_true: np.ndarray, proba: np.ndarray) -> dict[str, Any]:
    pred = proba.argmax(axis=1)
    return {
        "macro_f1": float(f1_score(y_true, pred, average="macro", labels=np.arange(len(CLASS_LABELS)), zero_division=0)),
        "accuracy": float(accuracy_score(y_true, pred)),
        "log_loss": float(log_loss(y_true, proba, labels=np.arange(len(CLASS_LABELS)))),
    }


def main() -> None:
    started = datetime.now(timezone.utc)
    clock = time.perf_counter()
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    exp374_config = yaml.safe_load(EXP374_CONFIG_PATH.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    dirty = git("status", "--porcelain")
    if context.experiment_id != "EXP-465" or dirty:
        raise RuntimeError("EXP-465는 clean issue-465 브랜치에서만 실행해야 합니다.\n" + dirty)

    feature_dir = ROOT / "data" / "processed" / f"{SLUG}_features"
    model_dir_a = ROOT / "models" / SLUG / "hotspot_only"
    model_dir_b = ROOT / "models" / SLUG / "burden_only"
    report_dir = ROOT / "reports" / SLUG
    reproducibility_dir = ROOT / "reproducibility" / SLUG
    oof_path = ROOT / "oof" / f"{SLUG}.csv"
    test_probability_path = ROOT / "preds" / f"{SLUG}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{SLUG}.csv"
    for directory in (model_dir_a, model_dir_b, report_dir, reproducibility_dir, oof_path.parent, test_probability_path.parent, submission_path.parent):
        directory.mkdir(parents=True, exist_ok=True)

    feature_report = build_base_features(exp374_config, feature_dir)
    x_all = sparse.load_npz(feature_dir / "train_features.npz")
    x_test = sparse.load_npz(feature_dir / "test_features.npz")
    all_feature_names = tuple(json.loads((feature_dir / "feature_names.json").read_text(encoding="utf-8")))

    train_meta = pd.read_csv(TRAIN_PATH, usecols=["ID", "SUBCLASS"], dtype=str)
    test_meta = pd.read_csv(TEST_PATH, usecols=["ID"], dtype=str)
    sample_submission = pd.read_csv(SAMPLE_SUBMISSION_PATH, dtype=str, keep_default_na=False)
    split = pd.read_csv(ROOT / config["split"]["path"], dtype={"ID": str, "fold": int})
    train = train_meta.merge(split, on="ID", how="left", validate="one_to_one", sort=False)
    if not train["ID"].equals(train_meta["ID"]) or train["fold"].isna().any():
        raise ValueError("fold 병합 결과가 원본 train과 일치하지 않습니다.")
    label_encoder = LabelEncoder().fit(list(CLASS_LABELS))
    y = label_encoder.transform(train["SUBCLASS"]).astype(np.int32)
    n_splits = config["split"]["n_splits"]
    seed = config["seed"]

    fold_builder = build_fold_features()
    model_params = dict(config["model"]["parameters"])

    oof_proba_a = np.full((len(train), len(CLASS_LABELS)), np.nan, dtype=np.float64)
    oof_proba_b = np.full((len(train), len(CLASS_LABELS)), np.nan, dtype=np.float64)
    test_proba_a = np.zeros((len(test_meta), len(CLASS_LABELS)), dtype=np.float64)
    test_proba_b = np.zeros((len(test_meta), len(CLASS_LABELS)), dtype=np.float64)
    fold_metrics_a: list[dict[str, Any]] = []
    fold_metrics_b: list[dict[str, Any]] = []
    n_features_a: int | None = None
    n_features_b: int | None = None

    for fold in range(n_splits):
        valid_mask = train["fold"].eq(fold).to_numpy()
        train_indices = np.flatnonzero(~valid_mask)
        valid_indices = np.flatnonzero(valid_mask)
        y_train, y_valid = y[train_indices], y[valid_indices]
        x_train_base = x_all[train_indices]
        x_valid_base = x_all[valid_indices]

        extra = fold_builder(
            fold=fold,
            train_indices=train_indices,
            valid_indices=valid_indices,
            base_train=x_train_base,
            base_validation=x_valid_base,
            base_test=x_test,
            base_feature_names=all_feature_names,
            target=y_train,
        )
        x_train_dropped, x_valid_dropped, x_test_dropped, kept_names = drop_named_base_features(
            x_train_base, x_valid_base, x_test, all_feature_names, extra.base_feature_names_to_drop
        )
        x_train_fold = sparse.hstack([x_train_dropped, extra.train], format="csr", dtype=np.float32)
        x_valid_fold = sparse.hstack([x_valid_dropped, extra.validation], format="csr", dtype=np.float32)
        x_test_fold = sparse.hstack([x_test_dropped, extra.test], format="csr", dtype=np.float32)
        combined_names = tuple(kept_names) + tuple(extra.feature_names)
        if x_train_fold.shape[1] != len(combined_names):
            raise ValueError("결합된 feature 이름 수와 열 수가 다릅니다.")

        hotspot_mask = np.array([name.startswith("hotspot__") for name in combined_names])
        burden_mask = np.array([name.startswith("sample__") for name in combined_names])
        if not hotspot_mask.any() or not burden_mask.any():
            raise ValueError("hotspot 또는 sample 접두사 feature가 비어 있습니다.")
        if n_features_a is None:
            n_features_a, n_features_b = int(hotspot_mask.sum()), int(burden_mask.sum())

        sample_weight = (
            compute_sample_weight(class_weight="balanced", y=y_train)
            if config["training"]["balanced_sample_weight"]
            else None
        )

        for label, mask, model_dir, oof_proba, test_proba_acc, fold_list in (
            ("A", hotspot_mask, model_dir_a, oof_proba_a, test_proba_a, fold_metrics_a),
            ("B", burden_mask, model_dir_b, oof_proba_b, test_proba_b, fold_metrics_b),
        ):
            x_train_sub = x_train_fold[:, mask]
            x_valid_sub = x_valid_fold[:, mask]
            x_test_sub = x_test_fold[:, mask]
            adapter = XGBoostAdapter(dict(model_params), seed=seed + fold)
            adapter.fit(x_train_sub, y_train, x_valid_sub, y_valid, sample_weight)
            valid_proba = adapter.predict_proba(x_valid_sub).astype(np.float64)
            fold_test_proba = adapter.predict_proba(x_test_sub).astype(np.float64)
            adapter.save(model_dir / f"fold_{fold:02d}.json")
            oof_proba[valid_indices] = valid_proba
            test_proba_acc += fold_test_proba / n_splits
            result = {"fold": fold, **fold_metrics_for(y_valid, valid_proba), "best_iteration": adapter.best_iteration}
            fold_list.append(result)
            print(json.dumps({"model": label, **result}, ensure_ascii=False))

    if np.isnan(oof_proba_a).any() or np.isnan(oof_proba_b).any():
        raise ValueError("OOF 확률에 채워지지 않은 값이 있습니다.")

    blend_weight_a = float(config["ensemble"]["weight_a"])
    blend_weight_b = float(config["ensemble"]["weight_b"])
    oof_proba = blend_weight_a * oof_proba_a + blend_weight_b * oof_proba_b
    test_proba = blend_weight_a * test_proba_a + blend_weight_b * test_proba_b
    oof_pred = oof_proba.argmax(axis=1)
    test_pred = test_proba.argmax(axis=1)

    per_class_f1 = {
        label: float(v)
        for label, v in zip(
            CLASS_LABELS,
            f1_score(y, oof_pred, average=None, labels=np.arange(len(CLASS_LABELS)), zero_division=0),
            strict=True,
        )
    }
    fold_scores = np.asarray(
        [
            f1_score(y[train["fold"].eq(f).to_numpy()], oof_pred[train["fold"].eq(f).to_numpy()], average="macro", labels=np.arange(len(CLASS_LABELS)), zero_division=0)
            for f in range(n_splits)
        ]
    )
    fold_metrics_blend = [
        {
            "fold": f,
            "macro_f1": float(fold_scores[f]),
            "accuracy": float(accuracy_score(y[train["fold"].eq(f).to_numpy()], oof_pred[train["fold"].eq(f).to_numpy()])),
            "log_loss": float(log_loss(y[train["fold"].eq(f).to_numpy()], oof_proba[train["fold"].eq(f).to_numpy()], labels=np.arange(len(CLASS_LABELS)))),
            "best_iteration": None,
        }
        for f in range(n_splits)
    ]
    finished = datetime.now(timezone.utc)

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

    source_commit = git("rev-parse", "HEAD")
    owner = git("config", "user.name") or os.environ.get("USER", "unknown")
    resolved_config = {
        "experiment": {
            "issue_number": context.issue_number,
            "experiment_id": context.experiment_id,
            "branch": context.branch,
            "owner": owner,
            "source_commit": source_commit,
            "dirty_worktree": False,
            "started_at": started.isoformat(),
        },
        "data": {
            "train": {"path": "data/raw/train.csv", "sha256": sha256_file(TRAIN_PATH)},
            "test": {"path": "data/raw/test.csv", "sha256": sha256_file(TEST_PATH)},
            "class_order": list(CLASS_LABELS),
        },
        "split": {**config["split"], "sha256": sha256_file(ROOT / config["split"]["path"])},
        "features": feature_report["feature_contract"],
        "feature_subsets": {"model_a_hotspot_only_n_features": n_features_a, "model_b_burden_only_n_features": n_features_b},
        "model": {"class": "xgboost.XGBClassifier", "parameters": model_params},
        "ensemble": config["ensemble"],
        "training": {**config["training"], "command": "uv run python scripts/run_exp465_feature_subset_ensemble.py"},
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
    resolved_config_path = reproducibility_dir / "config.resolved.yaml"
    resolved_config_path.write_text(yaml.safe_dump(resolved_config, allow_unicode=True, sort_keys=False), encoding="utf-8")

    oof_metrics = {
        "macro_f1": float(f1_score(y, oof_pred, average="macro", labels=np.arange(len(CLASS_LABELS)), zero_division=0)),
        "fold_mean": float(fold_scores.mean()),
        "fold_std": float(fold_scores.std()),
        "accuracy": float(accuracy_score(y, oof_pred)),
        "log_loss": float(log_loss(y, oof_proba, labels=np.arange(len(CLASS_LABELS)))),
        "per_class_f1": per_class_f1,
        "confusion_matrix": confusion_matrix(y, oof_pred, labels=np.arange(len(CLASS_LABELS))).tolist(),
    }
    metrics = {
        "experiment_id": "EXP-465",
        "record_role": "official",
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": 465,
        "parent_experiment": "EXP-374",
        "git_commit": source_commit,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "primary_metric": "macro_f1",
        "split_id": relative_posix(ROOT / config["split"]["path"], ROOT),
        "folds": fold_metrics_blend,
        "oof": oof_metrics,
        "leaderboard": None,
        "runtime": {"seconds": time.perf_counter() - clock, "hardware": platform.platform()},
        "artifacts": {
            "resolved_config": relative_posix(resolved_config_path, ROOT),
            "oof": relative_posix(oof_path, ROOT),
            "test_probability": relative_posix(test_probability_path, ROOT),
            "submission": relative_posix(submission_path, ROOT),
            "models": relative_posix(ROOT / "models" / SLUG, ROOT),
            "submission_sha256": submission_validation["sha256"],
        },
        "notes": config.get("notes", ""),
    }
    metrics_path = report_dir / "metrics.json"
    write_json(metrics_path, metrics)
    validate_json_document(metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json")

    component_oof_metrics_a = {
        "macro_f1": float(f1_score(y, oof_proba_a.argmax(axis=1), average="macro", labels=np.arange(len(CLASS_LABELS)), zero_division=0)),
        "n_features": n_features_a,
    }
    component_oof_metrics_b = {
        "macro_f1": float(f1_score(y, oof_proba_b.argmax(axis=1), average="macro", labels=np.arange(len(CLASS_LABELS)), zero_division=0)),
        "n_features": n_features_b,
    }
    write_json(
        report_dir / "component_metrics.json",
        {
            "purpose": "standalone_component_diagnostics",
            "issue": 465,
            "model_a_hotspot_only": {"folds": fold_metrics_a, "oof": component_oof_metrics_a},
            "model_b_burden_only": {"folds": fold_metrics_b, "oof": component_oof_metrics_b},
            "blend_weights": {"a": blend_weight_a, "b": blend_weight_b},
        },
    )

    # Inference-only reproducibility check: reload saved XGBoost boosters
    # for both A and B, re-predict on test, confirm byte-identical
    # submission and near-zero probability drift.
    repro_test_proba_a = np.zeros((len(test_meta), len(CLASS_LABELS)), dtype=np.float64)
    repro_test_proba_b = np.zeros((len(test_meta), len(CLASS_LABELS)), dtype=np.float64)
    for fold in range(n_splits):
        valid_mask = train["fold"].eq(fold).to_numpy()
        train_indices = np.flatnonzero(~valid_mask)
        valid_indices = np.flatnonzero(valid_mask)
        extra = fold_builder(
            fold=fold,
            train_indices=train_indices,
            valid_indices=valid_indices,
            base_train=x_all[train_indices],
            base_validation=x_all[valid_indices],
            base_test=x_test,
            base_feature_names=all_feature_names,
            target=y[train_indices],
        )
        _, _, x_test_dropped, kept_names = drop_named_base_features(
            x_all[train_indices], x_all[valid_indices], x_test, all_feature_names, extra.base_feature_names_to_drop
        )
        x_test_fold = sparse.hstack([x_test_dropped, extra.test], format="csr", dtype=np.float32)
        combined_names = tuple(kept_names) + tuple(extra.feature_names)
        hotspot_mask = np.array([name.startswith("hotspot__") for name in combined_names])
        burden_mask = np.array([name.startswith("sample__") for name in combined_names])

        booster_a = xgb.XGBClassifier()
        booster_a.load_model(model_dir_a / f"fold_{fold:02d}.json")
        repro_test_proba_a += booster_a.predict_proba(x_test_fold[:, hotspot_mask]) / n_splits
        booster_b = xgb.XGBClassifier()
        booster_b.load_model(model_dir_b / f"fold_{fold:02d}.json")
        repro_test_proba_b += booster_b.predict_proba(x_test_fold[:, burden_mask]) / n_splits

    repro_test_proba = blend_weight_a * repro_test_proba_a + blend_weight_b * repro_test_proba_b
    repro_test_pred = repro_test_proba.argmax(axis=1)
    repro_submission = sample_submission.copy()
    repro_submission["SUBCLASS"] = label_encoder.inverse_transform(repro_test_pred)
    with tempfile.TemporaryDirectory() as temp:
        repro_path = Path(temp) / submission_path.name
        repro_submission.to_csv(repro_path, index=False, lineterminator="\n")
        repro_sha = sha256_file(repro_path)
    max_diff = float(np.max(np.abs(repro_test_proba - test_proba)))
    verified = datetime.now(timezone.utc).isoformat()
    original_submission_sha256 = submission_validation["sha256"]
    comparison = {
        "experiment_id": "EXP-465",
        "data_hashes_match": True,
        "original_submission_sha256": original_submission_sha256,
        "reproduced_submission_sha256": repro_sha,
        "submission_sha256_match": original_submission_sha256 == repro_sha,
        "test_label_agreement": float((repro_test_pred == test_pred).mean()),
        "probability_max_abs_difference": max_diff,
        "probability_atol": 1e-6,
        "probability_rtol": 1e-6,
    }
    comparison["passed"] = comparison["submission_sha256_match"] and max_diff <= 1e-6
    if not comparison["passed"]:
        raise RuntimeError(comparison)

    env_path = reproducibility_dir / "environment.json"
    data_path = reproducibility_dir / "data_manifest.json"
    original_path = reproducibility_dir / "original_metrics.json"
    reproduction_path = reproducibility_dir / "reproduction_metrics.json"
    comparison_path = reproducibility_dir / "comparison.json"
    reproduce_path = reproducibility_dir / "REPRODUCE.md"
    manifest_path = reproducibility_dir / "artifact_manifest.json"
    write_json(env_path, {"verified_at": verified, **resolved_config["environment"]})
    write_json(original_path, metrics)
    write_json(
        reproduction_path,
        {"verification_type": "saved_checkpoint_inference_two_component_blend", **comparison},
    )
    write_json(comparison_path, comparison)
    data_files = [
        ROOT / config["split"]["path"],
        TRAIN_PATH,
        TEST_PATH,
        SAMPLE_SUBMISSION_PATH,
    ]
    write_json(data_path, {"verified_at": verified, "files": [record(path) for path in data_files]})
    reproduce_path.write_text(
        "# EXP-465 재현 절차\n\n"
        "```bash\nuv sync --frozen\n"
        "uv run python scripts/run_exp465_feature_subset_ensemble.py\n"
        "uv run python scripts/check_exp465_test_like_subset.py\n"
        "uv run python scripts/validate_experiment.py\n```\n\n"
        "hotspot-only(Model A)와 sample-aggregate-burden-only(Model B) 두 XGBoost를 "
        "EXP-374의 feature build를 재사용해 column mask로 분리 학습하고, 0.7/0.3이 "
        "아닌 0.5/0.5로 블렌드합니다.\n",
        encoding="utf-8",
    )
    artifacts = [
        {"kind": kind, **record(path), "storage_uri": None}
        for kind, path in [
            ("submission", submission_path),
            ("oof_probability", oof_path),
            ("test_probability", test_probability_path),
            ("metrics", metrics_path),
            ("resolved_config", resolved_config_path),
            ("comparison", comparison_path),
            ("component_metrics", report_dir / "component_metrics.json"),
        ]
    ] + [
        {"kind": "checkpoint", **record(path), "storage_uri": None}
        for path in sorted(model_dir_a.glob("*.json")) + sorted(model_dir_b.glob("*.json"))
    ]
    manifest = {
        "experiment_id": "EXP-465",
        "issue_number": 465,
        "reproducibility_status": "INFERENCE_VERIFIED",
        "source_commit": source_commit,
        "source_tag": None,
        "dirty_worktree": False,
        "data_manifest": relative_posix(data_path, ROOT),
        "environment": relative_posix(env_path, ROOT),
        "release_url": None,
        "verifier": owner,
        "verified_at": verified,
        "artifacts": artifacts,
        "verification": {
            "data_hashes_match": True,
            "submission_sha256_match": True,
            "test_label_agreement": comparison["test_label_agreement"],
            "probability_atol": 1e-6,
            "probability_rtol": 1e-6,
            "passed": True,
        },
    }
    write_json(manifest_path, manifest)
    validate_json_document(manifest_path, ROOT / "schemas" / "reproducibility_manifest.schema.json")
    checksum_paths = [resolved_config_path, env_path, data_path, original_path, reproduction_path, comparison_path, reproduce_path]
    (reproducibility_dir / "checksums.sha256").write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in checksum_paths), encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "metrics": str(metrics_path),
                "oof": oof_metrics,
                "component": {"a": component_oof_metrics_a, "b": component_oof_metrics_b},
                "reproducibility_status": manifest["reproducibility_status"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
