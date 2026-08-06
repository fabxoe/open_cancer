#!/usr/bin/env python
"""Run EXP-662 outer-train calibrated hierarchical TF-IDF LinearSVC."""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss
from sklearn.model_selection import StratifiedKFold
from sklearn.svm import LinearSVC

from open_cancer.canonical_event_tokenizer import tokenize_patient_event_row
from open_cancer.constants import CLASS_LABELS
from open_cancer.hashing import sha256_file
from open_cancer.hierarchical_event_adapter import fit_hierarchical_event_adapter
from open_cancer.model_artifacts import (
    build_oof_probability_frame,
    build_test_probability_frame,
    write_model_run_records,
)
from open_cancer.validation import validate_json_document, validate_submission


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/exp662_hierarchical_tfidf_svc_sigmoid.yaml"
SLUG = "exp662_hierarchical_tfidf_svc_sigmoid"
TRAIN_PATH = ROOT / "data/raw/train.csv"
TEST_PATH = ROOT / "data/raw/test.csv"
SAMPLE_PATH = ROOT / "data/raw/sample_submission.csv"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def _tokenize(frame: pd.DataFrame, genes: tuple[str, ...]):
    tokenized = []
    for index, (_, row) in enumerate(frame.iterrows(), start=1):
        tokenized.append(tokenize_patient_event_row(row, genes))
        if index % 500 == 0 or index == len(frame):
            print(f"tokenized {index}/{len(frame)}", flush=True)
    return tuple(tokenized)


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    started = datetime.now(timezone.utc)
    clock = time.perf_counter()
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if config["experiment_id"] != "EXP-662" or config["issue_number"] != 662:
        raise ValueError("EXP-662 identity mismatch")
    branch = _git("branch", "--show-current")
    if branch not in {"662", "issue-662", "662-calibrated-track-b", "issue-662-calibrated-track-b"}:
        raise ValueError(f"Issue #662와 일치하지 않는 branch입니다: {branch}")
    if _git("status", "--porcelain"):
        raise ValueError("공식 실행 전 worktree가 깨끗해야 합니다.")
    source_commit = _git("rev-parse", "HEAD")

    train = pd.read_csv(TRAIN_PATH, dtype=str, keep_default_na=False)
    test = pd.read_csv(TEST_PATH, dtype=str, keep_default_na=False)
    sample = pd.read_csv(SAMPLE_PATH, dtype=str, keep_default_na=False)
    split_path = ROOT / config["split"]["path"]
    folds = pd.read_csv(split_path, dtype={"ID": str, "fold": int})
    genes = tuple(column for column in train if column not in {"ID", "SUBCLASS"})
    if tuple(column for column in test if column != "ID") != genes:
        raise ValueError("train/test gene order mismatch")
    if train["ID"].tolist() != folds["ID"].tolist():
        raise ValueError("canonical split order mismatch")
    if sample["ID"].tolist() != test["ID"].tolist():
        raise ValueError("sample/test ID order mismatch")

    train_tokens = _tokenize(train, genes)
    test_tokens = _tokenize(test, genes)
    y = train["SUBCLASS"].to_numpy()
    fold_values = folds["fold"].to_numpy()
    n_splits = config["split"]["n_splits"]
    oof_probability = np.zeros((len(train), len(CLASS_LABELS)), dtype=np.float64)
    test_probability = np.zeros((len(test), len(CLASS_LABELS)), dtype=np.float64)
    fold_metrics = []
    model_dir = ROOT / f"models/{SLUG}"
    model_dir.mkdir(parents=True, exist_ok=True)

    model_parameters = dict(config["model"])
    model_parameters.pop("class")
    calibration = config["calibration"]
    for fold in range(n_splits):
        fold_started = time.perf_counter()
        fit_idx = np.flatnonzero(fold_values != fold)
        valid_idx = np.flatnonzero(fold_values == fold)
        fit_tokens = tuple(train_tokens[index] for index in fit_idx)
        valid_tokens = tuple(train_tokens[index] for index in valid_idx)
        adapter = fit_hierarchical_event_adapter(
            fit_tokens,
            detail_minimum_support=config["features"]["detail_minimum_patient_support"],
            global_minimum_support=config["features"]["global_minimum_patient_support"],
            normalization=config["features"]["normalization"],
        )
        x_fit = adapter.transform(fit_tokens)
        x_valid = adapter.transform(valid_tokens)
        x_test = adapter.transform(test_tokens)
        tfidf = TfidfTransformer(**config["features"]["tfidf"])
        x_fit = tfidf.fit_transform(x_fit)
        x_valid = tfidf.transform(x_valid)
        x_test = tfidf.transform(x_test)
        inner_cv = StratifiedKFold(
            n_splits=calibration["inner_splits"],
            shuffle=True,
            random_state=config["seed"] + fold,
        )
        model = CalibratedClassifierCV(
            estimator=LinearSVC(**model_parameters),
            method=calibration["method"],
            cv=inner_cv,
            n_jobs=calibration["n_jobs"],
            ensemble=calibration["ensemble"],
        )
        model.fit(x_fit, y[fit_idx])
        if tuple(model.classes_) != CLASS_LABELS:
            raise ValueError("model class order mismatch")
        valid_probability = model.predict_proba(x_valid)
        fold_test_probability = model.predict_proba(x_test)
        oof_probability[valid_idx] = valid_probability
        test_probability += fold_test_probability / n_splits
        prediction = model.classes_[valid_probability.argmax(axis=1)]
        fold_metrics.append(
            {
                "fold": fold,
                "macro_f1": float(f1_score(y[valid_idx], prediction, average="macro", zero_division=0)),
                "accuracy": float(accuracy_score(y[valid_idx], prediction)),
                "log_loss": float(log_loss(y[valid_idx], valid_probability, labels=CLASS_LABELS)),
                "best_iteration": None,
                "model_parameters": {**config["model"], "calibration": dict(calibration)},
                "nested_tuning": {
                    "scope": "outer_train_only",
                    "method": calibration["method"],
                    "inner_splits": calibration["inner_splits"],
                    "random_state": config["seed"] + fold,
                },
                "feature_selection": {
                    "detail_dimension": len(adapter.detail_tokens),
                    "global_dimension": len(adapter.global_tokens),
                    "feature_sha256": adapter.feature_sha256,
                    "adapter_sha256": adapter.adapter_sha256,
                    "tfidf": dict(config["features"]["tfidf"]),
                    "validation_oov": asdict(adapter.audit(valid_tokens)),
                },
            }
        )
        checkpoint = model_dir / f"fold_{fold:02d}.joblib"
        joblib.dump(
            {"model": model, "adapter": adapter, "tfidf": tfidf, "classes": CLASS_LABELS},
            checkpoint,
            compress=3,
        )
        print(
            f"fold {fold}: F1={fold_metrics[-1]['macro_f1']:.10f} "
            f"LL={fold_metrics[-1]['log_loss']:.10f} ({time.perf_counter()-fold_started:.1f}s)",
            flush=True,
        )

    oof_prediction = np.asarray(CLASS_LABELS)[oof_probability.argmax(axis=1)]
    test_prediction = np.asarray(CLASS_LABELS)[test_probability.argmax(axis=1)]
    per_class = f1_score(y, oof_prediction, labels=CLASS_LABELS, average=None, zero_division=0)
    parent_metrics = json.loads(
        (ROOT / "reports/exp545_hierarchical_tfidf_linear/metrics.json").read_text(encoding="utf-8")
    )
    parent_per_class = parent_metrics["oof"]["per_class_f1"]
    per_class_delta = {
        label: float(score - parent_per_class[label])
        for label, score in zip(CLASS_LABELS, per_class, strict=True)
    }
    macro_f1 = float(f1_score(y, oof_prediction, average="macro", zero_division=0))
    oof_log_loss = float(log_loss(y, oof_probability, labels=CLASS_LABELS))
    fold_std = float(np.std([item["macro_f1"] for item in fold_metrics]))
    gates = config["gates"]
    gate_results = {
        "macro_f1_non_degradation": macro_f1 - gates["parent_macro_f1"] >= gates["macro_f1_min_delta"],
        "log_loss_non_degradation": oof_log_loss - gates["parent_log_loss"] <= gates["log_loss_max_delta"],
        "fold_std_regression_limit": fold_std - gates["parent_fold_std"] <= gates["fold_std_max_delta"],
        "per_class_regression_limit": min(per_class_delta.values()) >= -gates["per_class_max_regression"],
    }
    passed = all(gate_results.values())

    oof_dir = ROOT / "oof"
    pred_dir = ROOT / "preds"
    submission_dir = ROOT / "submissions"
    report_dir = ROOT / f"reports/{SLUG}"
    reproducibility_dir = ROOT / f"reproducibility/{SLUG}"
    for directory in (oof_dir, pred_dir, submission_dir, report_dir, reproducibility_dir):
        directory.mkdir(parents=True, exist_ok=True)
    oof_path = oof_dir / f"{SLUG}.csv"
    test_probability_path = pred_dir / f"{SLUG}_test_proba.csv"
    submission_path = submission_dir / f"{SLUG}.csv"
    build_oof_probability_frame(
        ids=train["ID"], true_labels=y, folds=fold_values, probabilities=oof_probability
    ).to_csv(oof_path, index=False, lineterminator="\n")
    build_test_probability_frame(ids=test["ID"], probabilities=test_probability).to_csv(
        test_probability_path, index=False, lineterminator="\n"
    )
    submission = pd.DataFrame({"ID": test["ID"], "SUBCLASS": test_prediction})
    submission.to_csv(submission_path, index=False, lineterminator="\n")
    submission_validation = validate_submission(submission_path, SAMPLE_PATH)

    finished = datetime.now(timezone.utc)
    metrics = {
        "experiment_id": "EXP-662",
        "record_role": "official",
        "status": "COMPLETED",
        "owner": "codex",
        "issue_number": 662,
        "parent_experiment": "EXP-545",
        "git_commit": source_commit,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "primary_metric": "macro_f1",
        "split_id": config["split"]["path"],
        "folds": fold_metrics,
        "oof": {
            "macro_f1": macro_f1,
            "fold_mean": float(np.mean([item["macro_f1"] for item in fold_metrics])),
            "fold_std": fold_std,
            "accuracy": float(accuracy_score(y, oof_prediction)),
            "log_loss": oof_log_loss,
            "per_class_f1": dict(zip(CLASS_LABELS, per_class.tolist(), strict=True)),
            "confusion_matrix": confusion_matrix(y, oof_prediction, labels=CLASS_LABELS).tolist(),
        },
        "leaderboard": None,
        "runtime": {"seconds": float(time.perf_counter() - clock), "hardware": "local CPU"},
        "decision": "ADOPT" if passed else "ARCHIVE_GATE_FAILED",
        "artifacts": {
            "config": _relative(CONFIG_PATH),
            "oof": _relative(oof_path),
            "test_probabilities": _relative(test_probability_path),
            "submission": _relative(submission_path),
            "models": _relative(model_dir),
        },
        "comparison": {
            "parent_experiment": "EXP-545",
            "macro_f1_delta": macro_f1 - gates["parent_macro_f1"],
            "log_loss_delta": oof_log_loss - gates["parent_log_loss"],
            "fold_std_delta": fold_std - gates["parent_fold_std"],
            "minimum_per_class_f1_delta": min(per_class_delta.values()),
            "gate_results": gate_results,
            "passed": passed,
        },
    }
    metrics_path = report_dir / "metrics.json"
    _write_json(metrics_path, metrics)
    validate_json_document(metrics_path, ROOT / "schemas/experiment_metrics.schema.json")

    resolved_config = {**config, "source_commit": source_commit, "runner": _relative(Path(__file__))}
    write_model_run_records(
        root=ROOT,
        output_dir=reproducibility_dir,
        experiment_id="EXP-662",
        issue_number=662,
        source_commit=source_commit,
        resolved_config=resolved_config,
        metrics=metrics,
        data_files={
            "train": TRAIN_PATH,
            "test": TEST_PATH,
            "sample_submission": SAMPLE_PATH,
            "split": split_path,
        },
        artifacts={
            **{f"checkpoint_fold_{fold}": model_dir / f"fold_{fold:02d}.joblib" for fold in range(n_splits)},
            "oof_probabilities": oof_path,
            "test_probabilities": test_probability_path,
            "submission": submission_path,
        },
    )

    reproduced_probability = np.zeros_like(test_probability)
    for fold in range(n_splits):
        checkpoint = joblib.load(model_dir / f"fold_{fold:02d}.joblib")
        x_test = checkpoint["tfidf"].transform(checkpoint["adapter"].transform(test_tokens))
        reproduced_probability += checkpoint["model"].predict_proba(x_test) / n_splits
    reproduced_prediction = np.asarray(CLASS_LABELS)[reproduced_probability.argmax(axis=1)]
    reproduced_submission = pd.DataFrame({"ID": test["ID"], "SUBCLASS": reproduced_prediction})
    with tempfile.TemporaryDirectory() as temporary_directory:
        reproduced_path = Path(temporary_directory) / submission_path.name
        reproduced_submission.to_csv(reproduced_path, index=False, lineterminator="\n")
        reproduced_sha256 = sha256_file(reproduced_path)
    max_diff = float(np.max(np.abs(reproduced_probability - test_probability)))
    verified_at = datetime.now(timezone.utc).isoformat()
    comparison = {
        "verified_at": verified_at,
        "data_hashes_match": True,
        "original_submission_sha256": submission_validation["sha256"],
        "reproduced_submission_sha256": reproduced_sha256,
        "submission_sha256_match": submission_validation["sha256"] == reproduced_sha256,
        "test_label_agreement": float(np.mean(reproduced_prediction == test_prediction)),
        "test_probability_max_abs_diff": max_diff,
        "probability_atol": 1e-12,
        "probability_rtol": 1e-12,
    }
    comparison["passed"] = comparison["submission_sha256_match"] and max_diff <= 1e-12
    _write_json(reproducibility_dir / "comparison.json", comparison)
    manifest_path = reproducibility_dir / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["reproducibility_status"] = "INFERENCE_VERIFIED" if comparison["passed"] else "FAILED"
    manifest["verifier"] = "codex"
    manifest["verified_at"] = verified_at
    manifest["verification"] = {
        "data_hashes_match": True,
        "submission_sha256_match": comparison["submission_sha256_match"],
        "test_label_agreement": comparison["test_label_agreement"],
        "probability_atol": comparison["probability_atol"],
        "probability_rtol": comparison["probability_rtol"],
        "passed": comparison["passed"],
    }
    _write_json(manifest_path, manifest)
    validate_json_document(manifest_path, ROOT / "schemas/reproducibility_manifest.schema.json")

    report_lines = [
        "# EXP-662 outer-train calibrated hierarchical TF-IDF LinearSVC",
        "",
        "EXP-545의 유일한 변경으로 outer-train 내부 3-fold sigmoid calibration을 적용했다.",
        "Outer validation과 test는 모든 vocabulary, TF-IDF, calibration 학습에서 제외했다.",
        "",
        f"- OOF Macro F1: `{macro_f1:.10f}` (Δ `{metrics['comparison']['macro_f1_delta']:+.10f}`)",
        f"- OOF Log Loss: `{oof_log_loss:.10f}` (Δ `{metrics['comparison']['log_loss_delta']:+.10f}`)",
        f"- Fold 표준편차: `{fold_std:.10f}` (Δ `{metrics['comparison']['fold_std_delta']:+.10f}`)",
        f"- 공동 게이트: `{'PASS' if passed else 'FAIL'}`",
        f"- 재현 상태: `{'INFERENCE_VERIFIED' if comparison['passed'] else 'FAILED'}`",
        f"- Submission SHA-256: `{submission_validation['sha256']}`",
        "",
        "게이트 세부 결과:",
        "",
        *[f"- {name}: `{value}`" for name, value in gate_results.items()],
    ]
    (report_dir / "README.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps({"oof": metrics["oof"], "comparison": metrics["comparison"], "reproducibility": comparison}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
