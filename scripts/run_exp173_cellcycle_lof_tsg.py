#!/usr/bin/env python
"""Run EXP-173: EXP-094 Feature Spec v1 + P_lof_in_tsg_cellcycle.

Second pathway-aggregation ablation on the Issue #167/#168 catalog, and a
direct follow-up to EXP-170 (rejected). Baseline is the original EXP-094
v1 spec, not "EXP-170 applied" -- EXP-170 was not adopted. Adds one column:
whether any of the 6 TSG-labeled Cell Cycle genes carries a truncating
(nonsense or frameshift) mutation. See Issue #173 for the pre-check
confirming DLBC/LAML/TGCT have zero positive rate for this flag across all
of train.csv, which is required reading before interpreting per-class
deltas below.
"""

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
from open_cancer.model_runner import create_model_adapter, run_canonical_cv
from open_cancer.pathway_aggregation_features import (
    CELL_CYCLE_TSG_GENES,
    compute_truncating_flag,
)
from open_cancer.paths import relative_posix
from open_cancer.validation import validate_json_document, validate_submission

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "exp173_cellcycle_lof_tsg.yaml"
TRAIN = ROOT / "data" / "raw" / "train.csv"
TEST = ROOT / "data" / "raw" / "test.csv"
SAMPLE = ROOT / "data" / "raw" / "sample_submission.csv"
SLUG = "exp173_cellcycle_lof_tsg"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def main() -> None:
    started = datetime.now(timezone.utc)
    clock = time.perf_counter()
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    dirty = git("status", "--porcelain")
    if context.experiment_id != "EXP-173" or dirty:
        raise RuntimeError(
            "EXP-173은 clean issue-173 브랜치에서만 실행해야 합니다.\n" + dirty
        )

    feature_dir = ROOT / "data" / "processed" / f"{SLUG}_features"
    model_dir = ROOT / "models" / SLUG
    out_dir = ROOT / "reports" / SLUG
    for path in (model_dir, out_dir):
        path.mkdir(parents=True, exist_ok=True)

    materialize_frozen_feature_spec(
        root=ROOT, name="v1", output_dir=feature_dir, train_path=TRAIN, test_path=TEST
    )
    x_train = sparse.load_npz(feature_dir / "train_features.npz").tocsr()
    x_test = sparse.load_npz(feature_dir / "test_features.npz").tocsr()

    train_raw = pd.read_csv(TRAIN, dtype=str, keep_default_na=False)
    test_raw = pd.read_csv(TEST, dtype=str, keep_default_na=False)
    train_flag = compute_truncating_flag(train_raw, CELL_CYCLE_TSG_GENES).astype(np.float32)
    test_flag = compute_truncating_flag(test_raw, CELL_CYCLE_TSG_GENES).astype(np.float32)
    positive_rate_train = float(train_flag.mean())
    positive_rate_test = float(test_flag.mean())

    watch_classes = config.get("watch_classes", [])
    watch_positive_rate_by_class = {
        cls: float(train_flag[train_raw["SUBCLASS"] == cls].mean())
        for cls in watch_classes
    }

    x_train = sparse.hstack([x_train, sparse.csr_matrix(train_flag[:, None])], format="csr")
    x_test = sparse.hstack([x_test, sparse.csr_matrix(test_flag[:, None])], format="csr")

    train = train_raw[["ID", "SUBCLASS"]]
    test = test_raw[["ID"]]
    split_path = ROOT / config["split"]["path"]
    split = train[["ID"]].merge(
        pd.read_csv(split_path, dtype={"ID": str, "fold": int}),
        on="ID",
        how="left",
        validate="one_to_one",
        sort=False,
    )
    folds = split["fold"].to_numpy(dtype=np.int32)
    targets = (
        train["SUBCLASS"]
        .map({label: i for i, label in enumerate(CLASS_LABELS)})
        .to_numpy(dtype=np.int32)
    )
    params = dict(config["model"])
    result = run_canonical_cv(
        train_features=x_train,
        test_features=x_test,
        targets=targets,
        folds=folds,
        adapter_factory=lambda fold: create_model_adapter("xgboost", params, 42 + fold),
        model_dir=model_dir,
        balanced_sample_weight=True,
    )
    pred = result.oof_probabilities.argmax(axis=1)
    f1 = f1_score(targets, pred, average="macro")
    fold_scores = np.asarray([row["macro_f1"] for row in result.fold_metrics])

    baseline = json.loads((ROOT / config["baseline"]["metrics_path"]).read_text(encoding="utf-8"))
    baseline_oof = baseline["oof"]
    per_class_f1 = {
        label: float(value)
        for label, value in zip(
            CLASS_LABELS,
            f1_score(targets, pred, average=None, labels=np.arange(len(CLASS_LABELS)), zero_division=0),
            strict=True,
        )
    }
    per_class_delta = {
        label: per_class_f1[label] - baseline_oof["per_class_f1"][label] for label in CLASS_LABELS
    }
    acceptance = config["acceptance"]
    macro_f1_delta = float(f1) - baseline_oof["macro_f1"]
    fold_std_delta = float(fold_scores.std()) - baseline_oof["fold_std"]
    log_loss_value = float(
        log_loss(targets, result.oof_probabilities, labels=np.arange(len(CLASS_LABELS)))
    )
    log_loss_delta = log_loss_value - baseline_oof["log_loss"]
    verdict = {
        "macro_f1_delta": macro_f1_delta,
        "macro_f1_gate_passed": macro_f1_delta >= acceptance["min_macro_f1_delta"],
        "fold_std_delta": fold_std_delta,
        "fold_std_gate_passed": fold_std_delta < acceptance["max_fold_std_delta"],
        "log_loss_delta": log_loss_delta,
        "log_loss_gate_passed": log_loss_delta <= 0,
        "worst_per_class_f1_delta": min(per_class_delta.values()),
        "per_class_f1_gate_passed": min(per_class_delta.values()) >= 0,
    }
    verdict["adopted"] = all(
        verdict[key]
        for key in (
            "macro_f1_gate_passed",
            "fold_std_gate_passed",
            "log_loss_gate_passed",
            "per_class_f1_gate_passed",
        )
    )
    watch_class_deltas = {cls: per_class_delta[cls] for cls in watch_classes}

    metrics = {
        "experiment_id": "EXP-173",
        "record_role": "official",
        "status": "COMPLETED",
        "owner": git("config", "user.name") or "unknown",
        "issue_number": 173,
        "parent_experiment": "EXP-094",
        "git_commit": git("rev-parse", "HEAD"),
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "primary_metric": "macro_f1",
        "split_id": str(config["split"]["path"]),
        "folds": list(result.fold_metrics),
        "oof": {
            "macro_f1": float(f1),
            "fold_mean": float(fold_scores.mean()),
            "fold_std": float(fold_scores.std()),
            "accuracy": float(accuracy_score(targets, pred)),
            "log_loss": log_loss_value,
            "per_class_f1": per_class_f1,
            "confusion_matrix": confusion_matrix(
                targets, pred, labels=np.arange(len(CLASS_LABELS))
            ).tolist(),
        },
        "artifacts": {
            "feature_spec_manifest": relative_posix(
                feature_dir / "feature_spec_manifest.json", ROOT
            ),
            "models": relative_posix(model_dir, ROOT),
        },
        "runtime": {"seconds": time.perf_counter() - clock},
        "notes": (
            "EXP-094 frozen Feature Spec v1 + P_lof_in_tsg_cellcycle "
            "(6 TSG-labeled Cell Cycle genes, truncating=nonsense+frameshift "
            "only, Issue #167 catalog). Baseline is EXP-094 (not EXP-170, "
            "which was rejected). "
            f"Train positive rate {positive_rate_train:.6f}, test positive "
            f"rate {positive_rate_test:.6f}. Watch-class train positive "
            f"rates: {watch_positive_rate_by_class}. "
            f"Baseline EXP-094 OOF macro_f1 {baseline_oof['macro_f1']:.10f}, "
            f"delta {macro_f1_delta:+.10f}, fold_std delta "
            f"{fold_std_delta:+.10f}, log_loss delta {log_loss_delta:+.10f}, "
            f"watch-class F1 deltas {watch_class_deltas}, worst per-class F1 "
            f"delta {verdict['worst_per_class_f1_delta']:+.10f}. Verdict: "
            f"{'ADOPTED' if verdict['adopted'] else 'NOT ADOPTED'}."
        ),
    }
    metrics_path = out_dir / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    validate_json_document(metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json")

    verdict_path = out_dir / "verdict.json"
    verdict_path.write_text(
        json.dumps(
            {
                **verdict,
                "acceptance_criteria": acceptance,
                "baseline_experiment_id": baseline["experiment_id"],
                "baseline_oof_macro_f1": baseline_oof["macro_f1"],
                "positive_rate_train": positive_rate_train,
                "positive_rate_test": positive_rate_test,
                "watch_classes": watch_classes,
                "watch_class_train_positive_rate": watch_positive_rate_by_class,
                "watch_class_f1_delta": watch_class_deltas,
                "per_class_f1_delta": per_class_delta,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    submission = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
    submission["SUBCLASS"] = np.asarray(CLASS_LABELS)[result.test_probabilities.argmax(axis=1)]
    submission_path = ROOT / "submissions" / f"{SLUG}.csv"
    submission.to_csv(submission_path, index=False, lineterminator="\n")
    validate_submission(submission_path, TEST)
    pd.DataFrame(result.oof_probabilities, columns=CLASS_LABELS).assign(ID=train.ID).to_csv(
        ROOT / "oof" / f"{SLUG}.csv", index=False
    )
    pd.DataFrame(result.test_probabilities, columns=CLASS_LABELS).assign(ID=test.ID).to_csv(
        ROOT / "preds" / f"{SLUG}_test_proba.csv", index=False
    )
    print(
        json.dumps(
            {
                "metrics": str(metrics_path),
                "verdict": str(verdict_path),
                "oof_macro_f1": float(f1),
                "adopted": verdict["adopted"],
                "watch_class_f1_delta": watch_class_deltas,
                "watch_class_train_positive_rate": watch_positive_rate_by_class,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
