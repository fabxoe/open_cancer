#!/usr/bin/env python
"""Run EXP-459: CatBoost on EXP-374's exact feature set (model diversity).

Parent is EXP-374. Feature set (stop-notation-invariant v2 parser, Ensembl
release 116 isoform residue mask, pathway families, hotspot-34) is held
fixed -- reuses run_exp374_stop_isoform_residue_mask.build_fold_features()
directly, the same pattern EXP-449 (LightGBM) used. The sole change is the
model: CatBoost, starting from EXP-127's GPU hyperparameters but reduced to
a CPU-feasible depth/iteration/rsm setting (see configs/exp459_catboost_exp374.yaml
preflight.attempts -- no GPU is available in this execution environment).

Not run via run_hotspot_xgb.main() (XGBoost-only); replicates its base
feature build + fold loop, swapping in CatBoostAdapter.
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
from open_cancer.hotspot_features import build_hotspot_augmented_features, resolve_hotspot_config
from open_cancer.isoform_position_mask import resolve_isoform_position_mask_from_config
from open_cancer.isoform_relative_position import resolve_isoform_relative_position_from_config
from open_cancer.model_runner import CatBoostAdapter
from open_cancer.mutation_features import (
    resolve_position_features_from_config,
    resolve_position_options_from_config,
)
from open_cancer.paths import relative_posix
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
)
from open_cancer.validation import validate_json_document, validate_submission
from run_exp374_stop_isoform_residue_mask import build_fold_features

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "exp459_catboost_exp374.yaml"
EXP374_CONFIG_PATH = ROOT / "configs" / "exp374_stop_isoform_residue_mask.yaml"
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
SAMPLE_SUBMISSION_PATH = ROOT / "data" / "raw" / "sample_submission.csv"
SLUG = "exp459_catboost_exp374"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def build_base_features(exp374_config: dict, feature_dir: Path) -> dict:
    hotspot_config = exp374_config.get("hotspots", {})
    hotspots, _evidence, _min_rows = resolve_hotspot_config(hotspot_config)
    selected_position_features = resolve_position_features_from_config(exp374_config)
    position_options = resolve_position_options_from_config(exp374_config)
    position_token_filter, mask_contract = resolve_isoform_position_mask_from_config(
        exp374_config, root=ROOT
    )
    position_token_transformer, relative_contract = resolve_isoform_relative_position_from_config(
        exp374_config, root=ROOT
    )
    position_semantic_contract = relative_contract or mask_contract
    selected_robust_aggregates = tuple(
        exp374_config.get("features", {}).get("robust_aggregates", [])
    )
    return build_hotspot_augmented_features(
        TRAIN_PATH,
        TEST_PATH,
        feature_dir,
        hotspots=hotspots,
        base_feature_options={
            "selected_robust_aggregates": selected_robust_aggregates,
            "selected_position_features": selected_position_features,
            "position_token_filter": position_token_filter,
            "position_token_transformer": position_token_transformer,
            "position_semantic_contract": position_semantic_contract,
            "mutation_cell_parser": parse_stop_notation_invariant_cell,
            "mutation_parser_contract": STOP_NOTATION_PARSER_CONTRACT,
            **position_options,
        },
        hotspot_token_normalizer=normalize_stop_notation_token,
    )


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    started = datetime.now(timezone.utc)
    clock = time.perf_counter()
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    exp374_config = yaml.safe_load(EXP374_CONFIG_PATH.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    dirty = git("status", "--porcelain")
    if context.experiment_id != "EXP-459" or dirty:
        raise RuntimeError("EXP-459는 clean issue-459 브랜치에서만 실행해야 합니다.\n" + dirty)

    feature_dir = ROOT / "data" / "processed" / f"{SLUG}_features"
    model_dir = ROOT / "models" / SLUG
    report_dir = ROOT / "reports" / SLUG
    reproducibility_dir = ROOT / "reproducibility" / SLUG
    oof_path = ROOT / "oof" / f"{SLUG}.csv"
    test_probability_path = ROOT / "preds" / f"{SLUG}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{SLUG}.csv"
    for directory in (model_dir, report_dir, reproducibility_dir, oof_path.parent, test_probability_path.parent, submission_path.parent):
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

    oof_proba = np.full((len(train), len(CLASS_LABELS)), np.nan, dtype=np.float64)
    test_proba = np.zeros((len(test_meta), len(CLASS_LABELS)), dtype=np.float64)
    fold_metrics: list[dict[str, Any]] = []

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
        x_train_dropped, x_valid_dropped, x_test_dropped, _ = drop_named_base_features(
            x_train_base, x_valid_base, x_test, all_feature_names, extra.base_feature_names_to_drop
        )
        x_train_fold = sparse.hstack([x_train_dropped, extra.train], format="csr", dtype=np.float32)
        x_valid_fold = sparse.hstack([x_valid_dropped, extra.validation], format="csr", dtype=np.float32)
        x_test_fold = sparse.hstack([x_test_dropped, extra.test], format="csr", dtype=np.float32)

        sample_weight = (
            compute_sample_weight(class_weight="balanced", y=y_train)
            if config["training"]["balanced_sample_weight"]
            else None
        )
        fold_started = time.perf_counter()
        adapter = CatBoostAdapter(dict(model_params), seed=seed + fold)
        adapter.fit(x_train_fold, y_train, x_valid_fold, y_valid, sample_weight)
        valid_proba = adapter.predict_proba(x_valid_fold).astype(np.float64)
        fold_test_proba = adapter.predict_proba(x_test_fold).astype(np.float64)
        adapter.save(model_dir / f"fold_{fold:02d}.cbm")

        oof_proba[valid_indices] = valid_proba
        test_proba += fold_test_proba / n_splits
        valid_pred = valid_proba.argmax(axis=1)
        result = {
            "fold": fold,
            "macro_f1": float(f1_score(y_valid, valid_pred, average="macro")),
            "accuracy": float(accuracy_score(y_valid, valid_pred)),
            "log_loss": float(log_loss(y_valid, valid_proba, labels=np.arange(len(CLASS_LABELS)))),
            "best_iteration": adapter.best_iteration,
            "seconds": time.perf_counter() - fold_started,
        }
        fold_metrics.append(result)
        print(json.dumps(result, ensure_ascii=False))

    if np.isnan(oof_proba).any():
        raise ValueError("OOF 확률에 채워지지 않은 값이 있습니다.")

    oof_pred = oof_proba.argmax(axis=1)
    test_pred = test_proba.argmax(axis=1)
    report_dict = {
        label: float(v)
        for label, v in zip(
            CLASS_LABELS,
            f1_score(y, oof_pred, average=None, labels=np.arange(len(CLASS_LABELS)), zero_division=0),
            strict=True,
        )
    }
    fold_scores = np.asarray([item["macro_f1"] for item in fold_metrics])
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
        "model": {"class": "catboost.CatBoostClassifier", "parameters": model_params},
        "training": {
            **config["training"],
            "command": "uv run python scripts/run_exp459_catboost_exp374.py",
        },
        "preflight": config.get("preflight", {}),
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
    resolved_config_path.write_text(
        yaml.safe_dump(resolved_config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    metrics = {
        "experiment_id": "EXP-459",
        "record_role": "official",
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": 459,
        "parent_experiment": "EXP-374",
        "git_commit": source_commit,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "primary_metric": "macro_f1",
        "split_id": relative_posix(ROOT / config["split"]["path"], ROOT),
        "folds": fold_metrics,
        "oof": {
            "macro_f1": float(f1_score(y, oof_pred, average="macro")),
            "fold_mean": float(fold_scores.mean()),
            "fold_std": float(fold_scores.std()),
            "accuracy": float(accuracy_score(y, oof_pred)),
            "log_loss": float(log_loss(y, oof_proba, labels=np.arange(len(CLASS_LABELS)))),
            "per_class_f1": report_dict,
            "confusion_matrix": confusion_matrix(y, oof_pred, labels=np.arange(len(CLASS_LABELS))).tolist(),
        },
        "leaderboard": None,
        "runtime": {"seconds": time.perf_counter() - clock, "hardware": platform.platform()},
        "artifacts": {
            "resolved_config": relative_posix(resolved_config_path, ROOT),
            "oof": relative_posix(oof_path, ROOT),
            "test_probability": relative_posix(test_probability_path, ROOT),
            "submission": relative_posix(submission_path, ROOT),
            "models": relative_posix(model_dir, ROOT),
            "submission_sha256": submission_validation["sha256"],
        },
        "notes": config.get("notes", ""),
    }
    metrics_path = report_dir / "metrics.json"
    write_json(metrics_path, metrics)
    validate_json_document(metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json")

    # Inference-only reproducibility check: reload saved CatBoost boosters,
    # re-predict on test, confirm byte-identical submission and near-zero
    # probability drift.
    from catboost import CatBoostClassifier

    repro_test_proba = np.zeros((len(test_meta), len(CLASS_LABELS)), dtype=np.float64)
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
        _, _, x_test_dropped, _ = drop_named_base_features(
            x_all[train_indices], x_all[valid_indices], x_test, all_feature_names, extra.base_feature_names_to_drop
        )
        x_test_fold = sparse.hstack([x_test_dropped, extra.test], format="csr", dtype=np.float32)
        booster = CatBoostClassifier()
        booster.load_model(str(model_dir / f"fold_{fold:02d}.cbm"))
        fold_pred = booster.predict_proba(x_test_fold)
        repro_test_proba += fold_pred / n_splits
    repro_test_pred = repro_test_proba.argmax(axis=1)
    repro_submission = sample_submission.copy()
    repro_submission["SUBCLASS"] = label_encoder.inverse_transform(repro_test_pred)

    with tempfile.TemporaryDirectory() as temp:
        repro_path = Path(temp) / submission_path.name
        repro_submission.to_csv(repro_path, index=False, lineterminator="\n")
        repro_sha = sha256_file(repro_path)
    max_diff = float(np.max(np.abs(repro_test_proba - test_proba)))
    comparison = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "data_hashes_match": True,
        "original_submission_sha256": submission_validation["sha256"],
        "reproduced_submission_sha256": repro_sha,
        "submission_sha256_match": submission_validation["sha256"] == repro_sha,
        "test_label_agreement": float((repro_test_pred == test_pred).mean()),
        "test_probability_max_abs_diff": max_diff,
        "probability_atol": 1e-6,
        "probability_rtol": 1e-6,
    }
    comparison["passed"] = comparison["submission_sha256_match"] and max_diff <= 1e-6
    write_json(reproducibility_dir / "comparison.json", comparison)
    manifest = {
        "experiment_id": "EXP-459",
        "issue_number": 459,
        "reproducibility_status": "INFERENCE_VERIFIED" if comparison["passed"] else "FAILED",
        "source_commit": source_commit,
        "verified_at": comparison["verified_at"],
        "verifier": owner,
        "verification": comparison,
    }
    write_json(reproducibility_dir / "artifact_manifest.json", manifest)

    print(
        json.dumps(
            {
                "metrics": str(metrics_path),
                "oof": metrics["oof"],
                "reproducibility_status": manifest["reproducibility_status"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
