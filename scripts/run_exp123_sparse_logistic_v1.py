#!/usr/bin/env python
"""Run EXP-123: sparse Logistic Regression on frozen Feature Spec v1."""

from __future__ import annotations

import json
import importlib.metadata
import platform
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
import yaml
from scipy import sparse
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss

from open_cancer.constants import CLASS_LABELS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.frozen_feature_specs import materialize_frozen_feature_spec
from open_cancer.hashing import sha256_file
from open_cancer.model_artifacts import write_model_run_records
from open_cancer.model_runner import (
    create_model_adapter,
    run_canonical_cv,
    write_cross_validation_artifacts,
)
from open_cancer.validation import validate_json_document, validate_submission

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "exp123_sparse_logistic_v1.yaml"
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
SAMPLE_SUBMISSION_PATH = ROOT / "data" / "raw" / "sample_submission.csv"


def run_git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def replay_saved_model(
    model_name: str,
    model_paths: tuple[Path, ...],
    train_features: sparse.csr_matrix,
    test_features: sparse.csr_matrix,
    folds: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    oof = np.full((train_features.shape[0], len(CLASS_LABELS)), np.nan, dtype=np.float64)
    test = np.zeros((test_features.shape[0], len(CLASS_LABELS)), dtype=np.float64)
    for fold, path in enumerate(model_paths):
        valid = folds == fold
        if model_name == "logistic_regression":
            payload = joblib.load(path)
            model = payload["model"]
            scaler = payload["scaler"]
            valid_matrix = scaler.transform(train_features[valid]) if scaler else train_features[valid]
            test_matrix = scaler.transform(test_features) if scaler else test_features
            valid_raw = model.predict_proba(valid_matrix)
            test_raw = model.predict_proba(test_matrix)
            valid_probability = np.zeros((valid.sum(), len(CLASS_LABELS)), dtype=np.float64)
            test_probability = np.zeros((test_features.shape[0], len(CLASS_LABELS)), dtype=np.float64)
            valid_probability[:, model.classes_.astype(int)] = valid_raw
            test_probability[:, model.classes_.astype(int)] = test_raw
        elif model_name == "lightgbm":
            import lightgbm as lgb

            model = lgb.Booster(model_file=str(path))
            valid_probability = np.asarray(model.predict(train_features[valid]), dtype=np.float64)
            test_probability = np.asarray(model.predict(test_features), dtype=np.float64)
        elif model_name == "catboost":
            from catboost import CatBoostClassifier

            model = CatBoostClassifier()
            model.load_model(str(path))
            valid_probability = np.asarray(
                model.predict_proba(train_features[valid]), dtype=np.float64
            )
            test_probability = np.asarray(
                model.predict_proba(test_features), dtype=np.float64
            )
        else:
            raise ValueError(f"checkpoint 재추론을 지원하지 않는 모델입니다: {model_name}")
        oof[valid] = valid_probability / valid_probability.sum(axis=1, keepdims=True)
        test += (test_probability / test_probability.sum(axis=1, keepdims=True)) / 5
    if np.isnan(oof).any():
        raise ValueError("저장 checkpoint OOF 재추론이 완성되지 않았습니다.")
    return oof, test


def main(
    config_path: Path = CONFIG_PATH,
    *,
    expected_experiment_id: str = "EXP-123",
    runner_command: str = "uv run python scripts/run_exp123_sparse_logistic_v1.py",
) -> None:
    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    if context.experiment_id != expected_experiment_id:
        raise ValueError(
            f"runner 기대 ID {expected_experiment_id}와 현재 {context.experiment_id}가 다릅니다."
        )
    source_commit = run_git("rev-parse", "HEAD")
    if run_git("status", "--porcelain"):
        raise RuntimeError("공식 실험은 코드와 config를 commit한 clean worktree에서 실행하세요.")

    slug = f"exp{context.issue_number:03d}_{config['slug']}"
    feature_dir = ROOT / "data" / "processed" / f"{slug}_features"
    model_dir = ROOT / "models" / slug
    report_dir = ROOT / "reports" / slug
    reproduction_dir = ROOT / "reproducibility" / slug
    oof_path = ROOT / "oof" / f"{slug}.csv"
    test_probability_path = ROOT / "preds" / f"{slug}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{slug}.csv"
    for directory in (model_dir, report_dir, reproduction_dir, oof_path.parent, test_probability_path.parent):
        directory.mkdir(parents=True, exist_ok=True)

    feature_manifest = materialize_frozen_feature_spec(
        root=ROOT,
        name=config["feature_spec"]["name"],
        output_dir=feature_dir,
        train_path=TRAIN_PATH,
        test_path=TEST_PATH,
    )
    train_features = sparse.load_npz(feature_dir / "train_features.npz").tocsr()
    test_features = sparse.load_npz(feature_dir / "test_features.npz").tocsr()
    train = pd.read_csv(TRAIN_PATH, usecols=["ID", "SUBCLASS"], dtype=str)
    test = pd.read_csv(TEST_PATH, usecols=["ID"], dtype=str)
    split_path = ROOT / config["split"]["path"]
    split = pd.read_csv(split_path, dtype={"ID": str, "fold": int})
    aligned = train.loc[:, ["ID"]].merge(split, on="ID", how="left", validate="one_to_one", sort=False)
    if not aligned["ID"].equals(train["ID"]) or aligned["fold"].isna().any():
        raise ValueError("canonical split ID 또는 순서가 train과 다릅니다.")
    folds = aligned["fold"].to_numpy(dtype=np.int32)
    label_to_index = {label: index for index, label in enumerate(CLASS_LABELS)}
    targets = train["SUBCLASS"].map(label_to_index)
    if targets.isna().any():
        raise ValueError("고정 26개 클래스 밖의 SUBCLASS가 있습니다.")
    targets_array = targets.to_numpy(dtype=np.int32)

    model_name = config["model"]["name"]
    model_parameters = dict(config["model"]["parameters"])
    resolved_model_parameters = dict(model_parameters)
    if model_name == "lightgbm":
        resolved_model_parameters = {
            "objective": "multiclass",
            "num_class": len(CLASS_LABELS),
            **resolved_model_parameters,
        }
    elif model_name == "catboost":
        resolved_model_parameters = {
            "loss_function": "MultiClass",
            "verbose": False,
            **resolved_model_parameters,
        }
    result = run_canonical_cv(
        train_features=train_features,
        test_features=test_features,
        targets=targets_array,
        folds=folds,
        adapter_factory=lambda fold: create_model_adapter(
            model_name,
            model_parameters,
            config["seed"] + fold,
        ),
        model_dir=model_dir,
        balanced_sample_weight=config["training"]["balanced_sample_weight"],
    )

    common_paths = write_cross_validation_artifacts(
        output=result,
        train_ids=train["ID"].tolist(),
        true_labels=train["SUBCLASS"].tolist(),
        folds=folds,
        test_ids=test["ID"].tolist(),
        output_dir=feature_dir / "canonical_outputs",
    )
    shutil.copy2(common_paths.oof_probabilities, oof_path)
    shutil.copy2(common_paths.test_probabilities, test_probability_path)
    sample_submission = pd.read_csv(SAMPLE_SUBMISSION_PATH, dtype=str, keep_default_na=False)
    sample_submission["SUBCLASS"] = np.asarray(CLASS_LABELS)[
        result.test_probabilities.argmax(axis=1)
    ]
    sample_submission.to_csv(submission_path, index=False, lineterminator="\n")
    submission_validation = validate_submission(submission_path, TEST_PATH)

    prediction = result.oof_probabilities.argmax(axis=1)
    per_class = f1_score(
        targets_array,
        prediction,
        labels=np.arange(len(CLASS_LABELS)),
        average=None,
        zero_division=0,
    )
    fold_scores = np.asarray([row["macro_f1"] for row in result.fold_metrics])
    finished_at = datetime.now(timezone.utc)
    resolved_config = {
        "experiment": {
            "record_role": config["record_role"],
            "issue_number": context.issue_number,
            "experiment_id": context.experiment_id,
            "branch": context.branch,
            "source_commit": source_commit,
            "dirty_worktree": False,
            "started_at": started_at.isoformat(),
        },
        "data": {
            "train": {"path": relative(TRAIN_PATH), "sha256": sha256_file(TRAIN_PATH)},
            "test": {"path": relative(TEST_PATH), "sha256": sha256_file(TEST_PATH)},
            "sample_submission": {
                "path": relative(SAMPLE_SUBMISSION_PATH),
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
        "feature_spec": feature_manifest,
        "model": {
            "name": model_name,
            "parameters": resolved_model_parameters,
            "fold_seeds": [config["seed"] + fold for fold in range(5)],
        },
        "training": config["training"],
        "preflight": config.get("preflight"),
        "runtime": {
            "command": runner_command,
            "pythonhashseed": None,
            "deterministic": True,
        },
    }
    metrics = {
        "experiment_id": context.experiment_id,
        "record_role": config["record_role"],
        "status": "COMPLETED",
        "owner": run_git("config", "user.name") or "fabxoe",
        "issue_number": context.issue_number,
        "parent_experiment": config["parent_experiment"],
        "git_commit": source_commit,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "primary_metric": "macro_f1",
        "split_id": relative(split_path),
        "folds": list(result.fold_metrics),
        "oof": {
            "macro_f1": float(f1_score(targets_array, prediction, average="macro")),
            "fold_mean": float(fold_scores.mean()),
            "fold_std": float(fold_scores.std()),
            "accuracy": float(accuracy_score(targets_array, prediction)),
            "log_loss": float(
                log_loss(
                    targets_array,
                    result.oof_probabilities,
                    labels=np.arange(len(CLASS_LABELS)),
                )
            ),
            "per_class_f1": {
                label: float(value) for label, value in zip(CLASS_LABELS, per_class, strict=True)
            },
            "confusion_matrix": confusion_matrix(
                targets_array,
                prediction,
                labels=np.arange(len(CLASS_LABELS)),
            ).tolist(),
        },
        "leaderboard": None,
        "runtime": {
            "seconds": float(time.perf_counter() - started_clock),
            "hardware": platform.platform(),
        },
        "artifacts": {
            "resolved_config": relative(reproduction_dir / "config.resolved.yaml"),
            "oof": relative(oof_path),
            "test_probability": relative(test_probability_path),
            "submission": relative(submission_path),
            "models": relative(model_dir),
            "submission_sha256": submission_validation["sha256"],
        },
        "notes": config["notes"],
    }
    report_metrics_path = report_dir / "metrics.json"
    write_json(report_metrics_path, metrics)
    validate_json_document(report_metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json")

    artifacts = {
        "oof": oof_path,
        "test_probability": test_probability_path,
        "submission": submission_path,
        "report_metrics": report_metrics_path,
        "feature_spec_manifest": feature_dir / "feature_spec_manifest.json",
        **{f"checkpoint_fold_{fold}": path for fold, path in enumerate(result.model_paths)},
    }
    record_paths = write_model_run_records(
        root=ROOT,
        output_dir=reproduction_dir,
        experiment_id=context.experiment_id,
        issue_number=context.issue_number,
        source_commit=source_commit,
        resolved_config=resolved_config,
        metrics=metrics,
        data_files={
            "train": TRAIN_PATH,
            "test": TEST_PATH,
            "sample_submission": SAMPLE_SUBMISSION_PATH,
            "canonical_split": split_path,
        },
        artifacts=artifacts,
        environment={
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "model_library": model_name,
            "model_library_version": importlib.metadata.version(
                "scikit-learn" if model_name == "logistic_regression" else model_name
            ),
            "uv_lock_sha256": sha256_file(ROOT / "uv.lock"),
        },
    )

    replay_oof, replay_test = replay_saved_model(
        model_name,
        result.model_paths,
        train_features,
        test_features,
        folds,
    )
    replay_submission = sample_submission.copy()
    replay_submission["SUBCLASS"] = np.asarray(CLASS_LABELS)[replay_test.argmax(axis=1)]
    replay_submission_path = feature_dir / "replayed_submission.csv"
    replay_submission.to_csv(replay_submission_path, index=False, lineterminator="\n")
    max_oof_difference = float(np.max(np.abs(result.oof_probabilities - replay_oof)))
    max_test_difference = float(np.max(np.abs(result.test_probabilities - replay_test)))
    comparison = {
        "experiment_id": context.experiment_id,
        "data_hashes_match": True,
        "submission_sha256_match": sha256_file(submission_path) == sha256_file(replay_submission_path),
        "oof_label_agreement": float(
            np.mean(result.oof_probabilities.argmax(axis=1) == replay_oof.argmax(axis=1))
        ),
        "test_label_agreement": float(
            np.mean(result.test_probabilities.argmax(axis=1) == replay_test.argmax(axis=1))
        ),
        "oof_probability_max_abs_difference": max_oof_difference,
        "test_probability_max_abs_difference": max_test_difference,
        "probability_atol": 1e-6,
        "probability_rtol": 1e-6,
        "passed": bool(
            max_oof_difference <= 1e-6
            and max_test_difference <= 1e-6
            and sha256_file(submission_path) == sha256_file(replay_submission_path)
        ),
    }
    comparison_path = reproduction_dir / "comparison.json"
    write_json(comparison_path, comparison)
    write_json(reproduction_dir / "original_metrics.json", metrics)
    write_json(reproduction_dir / "reproduction_metrics.json", metrics)
    artifact_manifest = json.loads(record_paths["artifact_manifest"].read_text(encoding="utf-8"))
    artifact_manifest["reproducibility_status"] = (
        "INFERENCE_VERIFIED" if comparison["passed"] else "FAILED"
    )
    artifact_manifest["verification"] = {
        "data_hashes_match": True,
        "submission_sha256_match": comparison["submission_sha256_match"],
        "oof_label_agreement": comparison["oof_label_agreement"],
        "test_label_agreement": comparison["test_label_agreement"],
        "probability_atol": 1e-6,
        "probability_rtol": 1e-6,
        "oof_macro_f1_delta": 0.0,
        "passed": comparison["passed"],
    }
    write_json(record_paths["artifact_manifest"], artifact_manifest)
    validate_json_document(
        record_paths["artifact_manifest"],
        ROOT / "schemas" / "reproducibility_manifest.schema.json",
    )
    sync_command = (
        "uv sync --frozen --group experiment"
        if model_name in {"lightgbm", "catboost"}
        else "uv sync --frozen"
    )
    (reproduction_dir / "REPRODUCE.md").write_text(
        f"# {context.experiment_id} 재현\n\n"
        f"```bash\ngit checkout {source_commit}\n{sync_command}\n"
        f"{runner_command}\n```\n",
        encoding="utf-8",
    )
    checksum_paths = [
        *sorted(reproduction_dir.glob("*")),
        report_metrics_path,
        oof_path,
        test_probability_path,
        submission_path,
        *result.model_paths,
    ]
    checksum_lines = [
        f"{sha256_file(path)}  {relative(path)}"
        for path in checksum_paths
        if path.is_file() and path.name != "checksums.sha256"
    ]
    (reproduction_dir / "checksums.sha256").write_text(
        "\n".join(checksum_lines) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "experiment_id": context.experiment_id,
                "metrics": relative(report_metrics_path),
                "oof_macro_f1": metrics["oof"]["macro_f1"],
                "reproducibility_status": artifact_manifest["reproducibility_status"],
                "runtime_seconds": metrics["runtime"]["seconds"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
