#!/usr/bin/env python
"""Run EXP-545 hierarchical TF-IDF row-L2 LinearSVC canonical 5-fold."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from scipy.special import softmax
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss
from sklearn.svm import LinearSVC
from sklearn.feature_extraction.text import TfidfTransformer

from open_cancer.canonical_event_tokenizer import tokenize_patient_event_row
from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.hashing import sha256_file
from open_cancer.hierarchical_event_adapter import fit_hierarchical_event_adapter
from open_cancer.validation import validate_submission


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/exp545_hierarchical_tfidf_linear.yaml"
SLUG = "exp545_hierarchical_tfidf_linear"


def _git_sha() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _tokenize(frame: pd.DataFrame, genes: tuple[str, ...]):
    result = []
    for index, (_, row) in enumerate(frame.iterrows(), start=1):
        result.append(tokenize_patient_event_row(row, genes))
        if index % 500 == 0 or index == len(frame):
            print(f"tokenized {index}/{len(frame)}", flush=True)
    return tuple(result)


def main() -> None:
    started = datetime.now(timezone.utc)
    clock = time.perf_counter()
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if config["experiment_id"] != "EXP-545" or config["issue_number"] != 545:
        raise ValueError("EXP-545 identity mismatch")

    train_path = ROOT / "data/raw/train.csv"
    test_path = ROOT / "data/raw/test.csv"
    sample_path = ROOT / "data/raw/sample_submission.csv"
    split_path = ROOT / config["split"]["path"]
    train = pd.read_csv(train_path, dtype=str, keep_default_na=False)
    test = pd.read_csv(test_path, dtype=str, keep_default_na=False)
    sample = pd.read_csv(sample_path, dtype=str, keep_default_na=False)
    folds = pd.read_csv(split_path, dtype={"ID": str, "fold": int})
    genes = tuple(c for c in train if c not in {"ID", "SUBCLASS"})
    if tuple(c for c in test if c != "ID") != genes:
        raise ValueError("train/test gene order mismatch")
    if train["ID"].tolist() != folds["ID"].tolist():
        raise ValueError("canonical split order mismatch")
    if sample["ID"].tolist() != test["ID"].tolist():
        raise ValueError("sample/test ID order mismatch")

    train_tokens = _tokenize(train, genes)
    test_tokens = _tokenize(test, genes)
    y = train["SUBCLASS"].to_numpy()
    fold_values = folds["fold"].to_numpy()
    oof_scores = np.zeros((len(train), len(CLASS_LABELS)), dtype=np.float32)
    test_scores = np.zeros((len(test), len(CLASS_LABELS)), dtype=np.float64)
    fold_metrics = []
    model_dir = ROOT / f"models/{SLUG}"
    model_dir.mkdir(parents=True, exist_ok=True)

    parameters = dict(config["model"])
    parameters.pop("class")
    for fold in range(5):
        fit_idx = np.flatnonzero(fold_values != fold)
        valid_idx = np.flatnonzero(fold_values == fold)
        fit_tokens = tuple(train_tokens[i] for i in fit_idx)
        valid_tokens = tuple(train_tokens[i] for i in valid_idx)
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
        model = LinearSVC(**parameters)
        fold_started = time.perf_counter()
        model.fit(x_fit, y[fit_idx])
        if tuple(model.classes_) != CLASS_LABELS:
            raise ValueError("model class order mismatch")
        valid_score = model.decision_function(x_valid).astype(np.float32)
        test_score = model.decision_function(x_test).astype(np.float32)
        oof_scores[valid_idx] = valid_score
        test_scores += test_score / 5.0
        prediction = model.classes_[np.argmax(valid_score, axis=1)]
        probability = softmax(valid_score, axis=1)
        fold_metrics.append({
            "fold": fold,
            "macro_f1": float(f1_score(y[valid_idx], prediction, average="macro", zero_division=0)),
            "accuracy": float(accuracy_score(y[valid_idx], prediction)),
            "log_loss": float(log_loss(y[valid_idx], probability, labels=CLASS_LABELS)),
            "best_iteration": None,
            "model_parameters": dict(config["model"]),
            "feature_selection": {
                "detail_dimension": len(adapter.detail_tokens),
                "global_dimension": len(adapter.global_tokens),
                "feature_sha256": adapter.feature_sha256,
                "adapter_sha256": adapter.adapter_sha256,
                "tfidf": dict(config["features"]["tfidf"]),
                "validation_oov": asdict(adapter.audit(valid_tokens)),
            },
        })
        joblib.dump(
            {
                "model": model,
                "adapter": adapter,
                "tfidf": tfidf,
                "classes": CLASS_LABELS,
            },
            model_dir / f"fold_{fold:02d}.joblib",
            compress=3,
        )
        print(f"fold {fold}: {fold_metrics[-1]['macro_f1']:.10f} ({time.perf_counter()-fold_started:.1f}s)", flush=True)

    oof_prediction = np.asarray(CLASS_LABELS)[np.argmax(oof_scores, axis=1)]
    oof_probability = softmax(oof_scores, axis=1)
    test_probability = softmax(test_scores, axis=1)
    test_prediction = np.asarray(CLASS_LABELS)[np.argmax(test_scores, axis=1)]

    oof_dir, pred_dir, submission_dir = ROOT / "oof", ROOT / "preds", ROOT / "submissions"
    for directory in (oof_dir, pred_dir, submission_dir):
        directory.mkdir(parents=True, exist_ok=True)
    oof_frame = pd.DataFrame(oof_probability, columns=PROBABILITY_COLUMNS)
    oof_frame.insert(0, "PREDICTED", oof_prediction)
    oof_frame.insert(0, "SUBCLASS", y)
    oof_frame.insert(0, "fold", fold_values)
    oof_frame.insert(0, "ID", train["ID"])
    oof_path = oof_dir / f"{SLUG}.csv"
    oof_frame.to_csv(oof_path, index=False)
    pred_frame = pd.DataFrame(test_probability, columns=PROBABILITY_COLUMNS)
    pred_frame.insert(0, "ID", test["ID"])
    pred_path = pred_dir / f"{SLUG}_test_proba.csv"
    pred_frame.to_csv(pred_path, index=False)
    submission = pd.DataFrame({"ID": test["ID"], "SUBCLASS": test_prediction})
    submission_path = submission_dir / f"{SLUG}.csv"
    submission.to_csv(submission_path, index=False)
    validate_submission(submission_path, sample_path)

    per_class = f1_score(y, oof_prediction, labels=CLASS_LABELS, average=None, zero_division=0)
    finished = datetime.now(timezone.utc)
    metrics = {
        "experiment_id": "EXP-545", "record_role": "official", "status": "COMPLETED",
        "owner": "fabxoe", "issue_number": 545, "parent_experiment": "EXP-541",
        "git_commit": _git_sha(), "started_at": started.isoformat(), "finished_at": finished.isoformat(),
        "primary_metric": "macro_f1", "split_id": config["split"]["path"],
        "folds": fold_metrics,
        "oof": {
            "macro_f1": float(f1_score(y, oof_prediction, average="macro", zero_division=0)),
            "fold_mean": float(np.mean([x["macro_f1"] for x in fold_metrics])),
            "fold_std": float(np.std([x["macro_f1"] for x in fold_metrics])),
            "accuracy": float(accuracy_score(y, oof_prediction)),
            "log_loss": float(log_loss(y, oof_probability, labels=CLASS_LABELS)),
            "per_class_f1": dict(zip(CLASS_LABELS, per_class.tolist(), strict=True)),
            "confusion_matrix": confusion_matrix(y, oof_prediction, labels=CLASS_LABELS).tolist(),
        },
        "leaderboard": None,
        "runtime": {"seconds": float(time.perf_counter()-clock), "hardware": "local CPU"},
        "decision": "PENDING_SPARSE_LINEAR_GATE",
        "artifacts": {
            "config": str(CONFIG_PATH.relative_to(ROOT)), "oof": str(oof_path.relative_to(ROOT)),
            "test_probabilities": str(pred_path.relative_to(ROOT)),
            "submission": str(submission_path.relative_to(ROOT)), "models": str(model_dir.relative_to(ROOT)),
        },
    }
    report_dir = ROOT / f"reports/{SLUG}"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (report_dir / "README.md").write_text(
        "\n".join([
            "# EXP-545 hierarchical TF-IDF row-L2 LinearSVC", "",
            "Parser-v4 canonical event의 hierarchical detail/global TF-IDF row-L2 비교입니다.", "",
            f"- OOF Macro F1: `{metrics['oof']['macro_f1']:.10f}`",
            f"- Fold 표준편차: `{metrics['oof']['fold_std']:.10f}`",
            f"- Accuracy: `{metrics['oof']['accuracy']:.10f}`",
            f"- decision-score softmax Log Loss: `{metrics['oof']['log_loss']:.10f}`",
            f"- Submission SHA-256: `{sha256_file(submission_path)}`", "",
            "EXP-541 row-L2 count와 비교하여 outer-train TF-IDF의 추가 효과를 평가합니다.",
        ])+"\n", encoding="utf-8"
    )
    print(json.dumps(metrics["oof"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
