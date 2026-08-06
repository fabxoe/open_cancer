#!/usr/bin/env python
"""Run EXP-592: expand EXP-589 with two fold-safe binary specialists."""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
import xgboost as xgb
import yaml
from scipy import sparse
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, log_loss
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.feature_family import drop_named_base_features
from open_cancer.hashing import sha256_file, sha256_lines
from open_cancer.hierarchical_specialist import split_merged_probabilities
from open_cancer.paths import relative_posix
from open_cancer.validation import validate_json_document, validate_submission
from run_exp589_merged_24class import (
    MERGED_CLASS_LABELS,
    TARGET_ALIASES,
    Merged24ClassCosineFoldBuilder,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "exp592_hierarchical_pair_specialists.yaml"
TRAIN = ROOT / "data" / "raw" / "train.csv"
TEST = ROOT / "data" / "raw" / "test.csv"
SAMPLE_SUBMISSION = ROOT / "data" / "raw" / "sample_submission.csv"
PARENT_SLUG = "exp589_merged_24class"
PARENT_FEATURE_DIR = ROOT / "data" / "processed" / f"{PARENT_SLUG}_features"
PARENT_MODEL_DIR = ROOT / "models" / PARENT_SLUG


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_record(path: Path) -> dict[str, object]:
    return {
        "path": relative_posix(path, ROOT),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def fit_specialist(
    features: sparse.csr_matrix,
    labels: np.ndarray,
    *,
    positive_label: str,
    pair: tuple[str, str],
    parameters: dict[str, object],
    seed: int,
) -> tuple[xgb.XGBClassifier, dict[str, object]]:
    mask = np.isin(labels, pair)
    pair_labels = labels[mask]
    target = (pair_labels == positive_label).astype(np.int32)
    if set(np.unique(target)) != {0, 1}:
        raise ValueError(f"outer-train specialist {pair}에 두 클래스가 모두 없습니다.")
    weights = compute_sample_weight(class_weight="balanced", y=target)
    model = xgb.XGBClassifier(**parameters, random_state=seed)
    model.fit(features[mask], target, sample_weight=weights, verbose=False)
    return model, {
        "pair": list(pair),
        "positive_label": positive_label,
        "train_rows": int(mask.sum()),
        "negative_rows": int((target == 0).sum()),
        "positive_rows": int((target == 1).sum()),
        "fit_scope": "outer_train_pair_rows_only",
        "outer_validation_used_for_fit_or_selection": False,
    }


def main() -> None:
    started = datetime.now(timezone.utc)
    started_perf = time.perf_counter()
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    source_commit = git("rev-parse", "HEAD")
    if git("status", "--porcelain"):
        raise RuntimeError("공식 실험은 source/config commit 후 clean worktree에서 실행해야 합니다.")

    slug = f"exp{context.issue_number:03d}_{config['slug']}"
    report_dir = ROOT / "reports" / slug
    reproducibility_dir = ROOT / "reproducibility" / slug
    model_dir = ROOT / "models" / slug
    oof_path = ROOT / "oof" / f"{slug}.csv"
    test_probability_path = ROOT / "preds" / f"{slug}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{slug}.csv"
    metrics_path = report_dir / "metrics.json"
    resolved_path = reproducibility_dir / "config.resolved.yaml"
    for directory in (
        report_dir,
        reproducibility_dir,
        model_dir,
        oof_path.parent,
        test_probability_path.parent,
        submission_path.parent,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    required_parent = [
        PARENT_FEATURE_DIR / "train_features.npz",
        PARENT_FEATURE_DIR / "test_features.npz",
        PARENT_FEATURE_DIR / "feature_names.json",
        *[PARENT_MODEL_DIR / f"fold_{fold:02d}.json" for fold in range(5)],
    ]
    missing = [str(path) for path in required_parent if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "EXP-589 parent artifact가 없습니다. fetch_experiment_artifacts로 복구하세요: "
            + ", ".join(missing)
        )

    train_meta = pd.read_csv(TRAIN, usecols=["ID", "SUBCLASS"], dtype=str)
    test_meta = pd.read_csv(TEST, usecols=["ID"], dtype=str)
    split_path = ROOT / config["split"]["path"]
    folds = pd.read_csv(split_path, dtype={"ID": str, "fold": int})
    train = train_meta.merge(folds, on="ID", how="left", validate="one_to_one", sort=False)
    if not train["ID"].equals(train_meta["ID"]) or train["fold"].isna().any():
        raise ValueError("canonical fold 병합 결과가 원본 train과 다릅니다.")

    x_all = sparse.load_npz(PARENT_FEATURE_DIR / "train_features.npz").tocsr()
    x_test = sparse.load_npz(PARENT_FEATURE_DIR / "test_features.npz").tocsr()
    feature_names = tuple(
        json.loads((PARENT_FEATURE_DIR / "feature_names.json").read_text(encoding="utf-8"))
    )
    merged_encoder = LabelEncoder().fit(MERGED_CLASS_LABELS)
    merged_target = merged_encoder.transform(
        train["SUBCLASS"].replace(TARGET_ALIASES)
    ).astype(np.int32)
    original_encoder = LabelEncoder().fit(CLASS_LABELS)
    original_target = original_encoder.transform(train["SUBCLASS"]).astype(np.int32)
    builder = Merged24ClassCosineFoldBuilder()
    parameters = dict(config["specialists"]["model"])

    oof_probability = np.full((len(train), len(CLASS_LABELS)), np.nan, dtype=np.float32)
    test_probability = np.zeros((len(test_meta), len(CLASS_LABELS)), dtype=np.float32)
    reproduced_test_probability = np.zeros_like(test_probability)
    fold_metrics: list[dict[str, object]] = []
    fold_feature_records: list[dict[str, object]] = []
    model_artifacts: list[Path] = []

    for fold in range(config["split"]["n_splits"]):
        valid_mask = train["fold"].eq(fold).to_numpy()
        train_indices = np.flatnonzero(~valid_mask)
        valid_indices = np.flatnonzero(valid_mask)
        extra = builder(
            fold=fold,
            train_indices=train_indices,
            valid_indices=valid_indices,
            base_train=x_all[train_indices],
            base_validation=x_all[valid_indices],
            base_test=x_test,
            base_feature_names=feature_names,
            target=merged_target[train_indices],
        )
        base_train, base_valid, base_test, kept_names = drop_named_base_features(
            x_all[train_indices],
            x_all[valid_indices],
            x_test,
            feature_names,
            extra.base_feature_names_to_drop,
            allow_empty=bool(extra.feature_names),
        )
        x_train_fold = sparse.hstack([base_train, extra.train], format="csr", dtype=np.float32)
        x_valid_fold = sparse.hstack([base_valid, extra.validation], format="csr", dtype=np.float32)
        x_test_fold = sparse.hstack([base_test, extra.test], format="csr", dtype=np.float32)
        fold_feature_records.append(
            {
                "fold": fold,
                "feature_count": int(x_train_fold.shape[1]),
                "base_feature_names_after_drop_sha256": sha256_lines(kept_names),
                "extra_feature_names_sha256": sha256_lines(extra.feature_names),
            }
        )

        parent_source = PARENT_MODEL_DIR / f"fold_{fold:02d}.json"
        parent_copy = model_dir / f"base_fold_{fold:02d}.json"
        shutil.copy2(parent_source, parent_copy)
        base_model = xgb.XGBClassifier()
        base_model.load_model(parent_copy)
        base_valid_probability = base_model.predict_proba(x_valid_fold).astype(np.float32)
        base_test_probability = base_model.predict_proba(x_test_fold).astype(np.float32)

        labels_train = train["SUBCLASS"].to_numpy()[train_indices]
        kipan_model, kipan_record = fit_specialist(
            x_train_fold,
            labels_train,
            positive_label="KIRC",
            pair=("KIPAN", "KIRC"),
            parameters=parameters,
            seed=config["seed"] + fold,
        )
        gbmlgg_model, gbmlgg_record = fit_specialist(
            x_train_fold,
            labels_train,
            positive_label="LGG",
            pair=("GBMLGG", "LGG"),
            parameters=parameters,
            seed=config["seed"] + 100 + fold,
        )
        kipan_path = model_dir / f"kipan_kirc_fold_{fold:02d}.json"
        gbmlgg_path = model_dir / f"gbmlgg_lgg_fold_{fold:02d}.json"
        kipan_model.save_model(kipan_path)
        gbmlgg_model.save_model(gbmlgg_path)
        model_artifacts.extend([parent_copy, kipan_path, gbmlgg_path])

        valid_probability = split_merged_probabilities(
            base_valid_probability,
            merged_class_labels=MERGED_CLASS_LABELS,
            output_class_labels=CLASS_LABELS,
            kipan_conditional=kipan_model.predict_proba(x_valid_fold),
            gbmlgg_conditional=gbmlgg_model.predict_proba(x_valid_fold),
        )
        fold_test_probability = split_merged_probabilities(
            base_test_probability,
            merged_class_labels=MERGED_CLASS_LABELS,
            output_class_labels=CLASS_LABELS,
            kipan_conditional=kipan_model.predict_proba(x_test_fold),
            gbmlgg_conditional=gbmlgg_model.predict_proba(x_test_fold),
        )
        oof_probability[valid_indices] = valid_probability
        test_probability += fold_test_probability / config["split"]["n_splits"]

        # Reload all three checkpoints and reproduce this fold's test probability.
        replay_base = xgb.XGBClassifier()
        replay_kipan = xgb.XGBClassifier()
        replay_gbmlgg = xgb.XGBClassifier()
        replay_base.load_model(parent_copy)
        replay_kipan.load_model(kipan_path)
        replay_gbmlgg.load_model(gbmlgg_path)
        replay = split_merged_probabilities(
            replay_base.predict_proba(x_test_fold),
            merged_class_labels=MERGED_CLASS_LABELS,
            output_class_labels=CLASS_LABELS,
            kipan_conditional=replay_kipan.predict_proba(x_test_fold),
            gbmlgg_conditional=replay_gbmlgg.predict_proba(x_test_fold),
        )
        reproduced_test_probability += replay / config["split"]["n_splits"]

        valid_target = original_target[valid_indices]
        valid_prediction = valid_probability.argmax(axis=1)
        fold_metrics.append(
            {
                "fold": fold,
                "macro_f1": float(
                    f1_score(
                        valid_target,
                        valid_prediction,
                        labels=np.arange(len(CLASS_LABELS)),
                        average="macro",
                        zero_division=0,
                    )
                ),
                "accuracy": float(accuracy_score(valid_target, valid_prediction)),
                "log_loss": float(
                    log_loss(
                        valid_target,
                        valid_probability,
                        labels=np.arange(len(CLASS_LABELS)),
                    )
                ),
                "best_iteration": None,
                "model_parameters": parameters,
                "resampling": {
                    "kipan_kirc": kipan_record,
                    "gbmlgg_lgg": gbmlgg_record,
                },
            }
        )
        print(json.dumps(fold_metrics[-1], ensure_ascii=False))

    if np.isnan(oof_probability).any():
        raise ValueError("OOF probability에 채워지지 않은 행이 있습니다.")
    if not np.allclose(test_probability, reproduced_test_probability, atol=1e-6, rtol=1e-6):
        raise ValueError("저장 checkpoint 재추론 확률이 원 실행과 다릅니다.")

    oof_prediction = oof_probability.argmax(axis=1)
    test_prediction = test_probability.argmax(axis=1)
    report = classification_report(
        original_target,
        oof_prediction,
        labels=np.arange(len(CLASS_LABELS)),
        target_names=CLASS_LABELS,
        output_dict=True,
        zero_division=0,
    )
    fold_scores = np.array([float(row["macro_f1"]) for row in fold_metrics])
    finished = datetime.now(timezone.utc)

    oof_frame = pd.DataFrame(
        {
            "ID": train["ID"],
            "SUBCLASS_TRUE": train["SUBCLASS"],
            "SUBCLASS_PRED": np.asarray(CLASS_LABELS)[oof_prediction],
            "FOLD": train["fold"].astype(int),
        }
    )
    oof_frame.loc[:, list(PROBABILITY_COLUMNS)] = oof_probability
    oof_frame.to_csv(oof_path, index=False, lineterminator="\n")
    test_frame = pd.DataFrame({"ID": test_meta["ID"]})
    test_frame.loc[:, list(PROBABILITY_COLUMNS)] = test_probability
    test_frame.to_csv(test_probability_path, index=False, lineterminator="\n")
    submission = pd.read_csv(SAMPLE_SUBMISSION, dtype=str, keep_default_na=False)
    submission["SUBCLASS"] = np.asarray(CLASS_LABELS)[test_prediction]
    submission.to_csv(submission_path, index=False, lineterminator="\n")
    submission_validation = validate_submission(submission_path, TEST)

    resolved = {
        "experiment": {
            "record_role": config["record_role"],
            "issue_number": context.issue_number,
            "experiment_id": context.experiment_id,
            "branch": context.branch,
            "owner": git("config", "user.name") or os.environ.get("USER", "unknown"),
            "source_commit": source_commit,
            "dirty_worktree": False,
            "started_at": started.isoformat(),
        },
        "data": {
            "train": {"path": relative_posix(TRAIN, ROOT), "sha256": sha256_file(TRAIN)},
            "test": {"path": relative_posix(TEST, ROOT), "sha256": sha256_file(TEST)},
            "sample_submission": {
                "path": relative_posix(SAMPLE_SUBMISSION, ROOT),
                "sha256": sha256_file(SAMPLE_SUBMISSION),
            },
            "class_order": list(CLASS_LABELS),
        },
        "split": {**config["split"], "sha256": sha256_file(split_path)},
        "parent": {
            "experiment_id": "EXP-589",
            "model_paths": [relative_posix(PARENT_MODEL_DIR / f"fold_{fold:02d}.json", ROOT) for fold in range(5)],
            "feature_dir": relative_posix(PARENT_FEATURE_DIR, ROOT),
        },
        "fold_features": fold_feature_records,
        "specialists": config["specialists"],
        "training": {
            "command": "uv run python scripts/run_exp592_hierarchical_pair_specialists.py",
            "fold_seeds": [config["seed"] + fold for fold in range(5)],
            "test_or_public_used_for_selection": False,
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
    resolved_path.write_text(yaml.safe_dump(resolved, allow_unicode=True, sort_keys=False), encoding="utf-8")
    metrics = {
        "experiment_id": context.experiment_id,
        "record_role": config["record_role"],
        "status": "COMPLETED",
        "owner": resolved["experiment"]["owner"],
        "issue_number": context.issue_number,
        "parent_experiment": "EXP-589",
        "git_commit": source_commit,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "primary_metric": "macro_f1",
        "split_id": relative_posix(split_path, ROOT),
        "folds": fold_metrics,
        "oof": {
            "macro_f1": float(
                f1_score(
                    original_target,
                    oof_prediction,
                    labels=np.arange(len(CLASS_LABELS)),
                    average="macro",
                    zero_division=0,
                )
            ),
            "fold_mean": float(fold_scores.mean()),
            "fold_std": float(fold_scores.std()),
            "accuracy": float(accuracy_score(original_target, oof_prediction)),
            "log_loss": float(
                log_loss(
                    original_target,
                    oof_probability,
                    labels=np.arange(len(CLASS_LABELS)),
                )
            ),
            "per_class_f1": {label: float(report[label]["f1-score"]) for label in CLASS_LABELS},
            "confusion_matrix": confusion_matrix(
                original_target, oof_prediction, labels=np.arange(len(CLASS_LABELS))
            ).tolist(),
        },
        "leaderboard": None,
        "runtime": {
            "seconds": float(time.perf_counter() - started_perf),
            "hardware": platform.platform(),
        },
        "artifacts": {
            "resolved_config": relative_posix(resolved_path, ROOT),
            "oof": relative_posix(oof_path, ROOT),
            "test_probability": relative_posix(test_probability_path, ROOT),
            "submission": relative_posix(submission_path, ROOT),
            "models": relative_posix(model_dir, ROOT),
            "submission_sha256": submission_validation["sha256"],
        },
        "notes": config["notes"],
    }
    write_json(metrics_path, metrics)
    validate_json_document(metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json")

    comparison = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "verification_type": "base_and_specialist_checkpoint_inference",
        "test_probability_allclose": True,
        "test_probability_max_abs_diff": float(
            np.max(np.abs(test_probability - reproduced_test_probability))
        ),
        "submission_sha256": submission_validation["sha256"],
        "test_label_agreement": 1.0,
        "passed": True,
    }
    write_json(reproducibility_dir / "comparison.json", comparison)
    write_json(reproducibility_dir / "original_metrics.json", metrics)
    write_json(
        reproducibility_dir / "reproduction_metrics.json",
        {"experiment_id": context.experiment_id, **comparison},
    )
    artifacts = [
        *[{"kind": "checkpoint", **file_record(path), "storage_uri": None} for path in model_artifacts],
        {"kind": "oof_probability", **file_record(oof_path), "storage_uri": None},
        {"kind": "test_probability", **file_record(test_probability_path), "storage_uri": None},
        {"kind": "submission", **file_record(submission_path), "storage_uri": None},
        {"kind": "metrics", **file_record(metrics_path), "storage_uri": None},
        {"kind": "resolved_config", **file_record(resolved_path), "storage_uri": None},
    ]
    write_json(
        reproducibility_dir / "artifact_manifest.json",
        {
            "experiment_id": context.experiment_id,
            "issue_number": context.issue_number,
            "reproducibility_status": "INFERENCE_VERIFIED",
            "source_commit": source_commit,
            "source_tag": None,
            "dirty_worktree": False,
            "release_url": None,
            "verifier": resolved["experiment"]["owner"],
            "verified_at": comparison["verified_at"],
            "artifacts": artifacts,
        },
    )
    (reproducibility_dir / "REPRODUCE.md").write_text(
        "# EXP-592 재현\n\n"
        "EXP-589 checkpoint와 feature cache를 먼저 복구한 뒤 실행합니다.\n\n"
        "```bash\nuv sync --frozen\n"
        "uv run python scripts/run_exp592_hierarchical_pair_specialists.py\n```\n",
        encoding="utf-8",
    )
    checksum_paths = [metrics_path, resolved_path, oof_path, test_probability_path, submission_path, *model_artifacts]
    (reproducibility_dir / "checksums.sha256").write_text(
        "".join(f"{sha256_file(path)}  {relative_posix(path, ROOT)}\n" for path in checksum_paths),
        encoding="utf-8",
    )
    print(json.dumps({"metrics": metrics["oof"], "reproducibility": comparison}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
