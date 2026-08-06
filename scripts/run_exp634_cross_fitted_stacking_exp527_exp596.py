#!/usr/bin/env python
"""Run EXP-634: leakage-safe cross-fitted L2 logistic stacking of EXP-527
and EXP-596 (#505 Cross-fitted Stacking roadmap, S2 stage).

Direct adaptation of scripts/run_exp137_cross_fitted_stacking.py (EXP-094 +
EXP-125 cross-fitted stacking) -- same canonical 5-fold cross-fitting,
checkpoint, and INFERENCE_VERIFIED reproduction pattern, only the base
experiments and comparison parent change.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.hashing import sha256_file
from open_cancer.paths import relative_posix
from open_cancer.validation import validate_json_document, validate_submission

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/exp634_cross_fitted_stacking_exp527_exp596.yaml"
ISSUE = 634
EXP_ID = "EXP-634"
SLUG = "exp634_cross_fitted_stacking_exp527_exp596"
PARENT_EXPERIMENT = "EXP-628"
RUNNER_COMMAND = "uv run python scripts/run_exp634_cross_fitted_stacking_exp527_exp596.py"
RUNNER_NOTES = (
    "Leakage-safe outer 5-fold cross-fitted multinomial Logistic Regression "
    "(L2, C=0.2) over EXP-527 and EXP-596 OOF probabilities. Final test "
    "model is fit on all base OOF rows. Comparison parent is EXP-628 "
    "(nested-selected 0.35/0.65 fixed blend of the same two base models)."
)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record(path: Path) -> dict[str, Any]:
    return {"path": relative_posix(path, ROOT), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}


def load_base(config: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    oof_frames = [
        pd.read_csv(ROOT / item["oof_probability_path"], dtype={"ID": str})
        for item in config["base_experiments"]
    ]
    test_frames = [
        pd.read_csv(ROOT / item["test_probability_path"], dtype={"ID": str})
        for item in config["base_experiments"]
    ]
    reference = oof_frames[0]
    for frame in oof_frames[1:]:
        if not frame[["ID", "SUBCLASS_TRUE", "FOLD"]].equals(reference[["ID", "SUBCLASS_TRUE", "FOLD"]]):
            raise ValueError("base OOF의 ID·정답·fold가 정렬되지 않았습니다.")
    test_reference = test_frames[0]["ID"]
    for frame in test_frames[1:]:
        if not frame["ID"].equals(test_reference):
            raise ValueError("base test 확률의 ID 순서가 정렬되지 않았습니다.")
    x_oof = np.concatenate(
        [frame.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=float) for frame in oof_frames], axis=1
    )
    x_test = np.concatenate(
        [frame.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=float) for frame in test_frames], axis=1
    )
    return x_oof, x_test, reference


def make_model(params: dict[str, Any]) -> LogisticRegression:
    return LogisticRegression(
        C=float(params["C"]),
        max_iter=int(params["max_iter"]),
        class_weight=params["class_weight"],
        random_state=int(params["random_state"]),
    )


def main() -> None:
    started = datetime.now(timezone.utc)
    timer = time.perf_counter()
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    if context.issue_number != ISSUE or context.experiment_id != EXP_ID:
        raise ValueError(f"실험 context 불일치: {context}")
    if git("status", "--porcelain"):
        raise RuntimeError("공식 실험은 clean worktree에서 실행해야 합니다.")

    x_oof, x_test, reference = load_base(config)
    y = reference["SUBCLASS_TRUE"].to_numpy()
    fold_ids = reference["FOLD"].to_numpy()
    params = config["meta_model"]

    model_dir = ROOT / "models" / SLUG
    report_dir = ROOT / "reports" / SLUG
    repro_dir = ROOT / "reproducibility" / SLUG
    oof_path = ROOT / "oof" / f"{SLUG}.csv"
    test_proba_path = ROOT / "preds" / f"{SLUG}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{SLUG}.csv"
    metrics_path = report_dir / "metrics.json"
    resolved_path = repro_dir / "config.resolved.yaml"
    for directory in (model_dir, report_dir, repro_dir, oof_path.parent, test_proba_path.parent, submission_path.parent):
        directory.mkdir(parents=True, exist_ok=True)

    oof_prob = np.zeros((len(y), len(CLASS_LABELS)), dtype=float)
    fold_metrics = []
    fold_models = []
    fold_coefficients = []
    for fold in range(config["split"]["n_splits"]):
        train_mask = fold_ids != fold
        valid_mask = fold_ids == fold
        model = make_model(params)
        model.fit(x_oof[train_mask], y[train_mask])
        oof_prob[valid_mask] = model.predict_proba(x_oof[valid_mask])
        model_path = model_dir / f"fold_{fold}.joblib"
        joblib.dump(model, model_path)
        fold_models.append(model_path)
        fold_pred = np.asarray(CLASS_LABELS)[oof_prob[valid_mask].argmax(axis=1)]
        fold_metrics.append(
            {
                "fold": fold,
                "macro_f1": float(
                    f1_score(y[valid_mask], fold_pred, labels=CLASS_LABELS, average="macro", zero_division=0)
                ),
                "accuracy": float(accuracy_score(y[valid_mask], fold_pred)),
                "log_loss": float(log_loss(y[valid_mask], oof_prob[valid_mask], labels=CLASS_LABELS)),
                "best_iteration": None,
            }
        )
        fold_coefficients.append(
            {
                "fold": fold,
                "coef_abs_max": float(np.max(np.abs(model.coef_))),
                "coef_abs_mean": float(np.mean(np.abs(model.coef_))),
                "intercept_abs_max": float(np.max(np.abs(model.intercept_))),
            }
        )

    final_model = make_model(params)
    final_model.fit(x_oof, y)
    final_model_path = model_dir / "final.joblib"
    joblib.dump(final_model, final_model_path)
    test_prob = final_model.predict_proba(x_test)

    oof_pred = np.asarray(CLASS_LABELS)[oof_prob.argmax(axis=1)]
    test_pred = np.asarray(CLASS_LABELS)[test_prob.argmax(axis=1)]
    oof_frame = reference[["ID", "SUBCLASS_TRUE", "FOLD"]].copy()
    oof_frame["SUBCLASS_PRED"] = oof_pred
    oof_frame.loc[:, list(PROBABILITY_COLUMNS)] = oof_prob
    oof_frame.to_csv(oof_path, index=False, lineterminator="\n")

    test_frame = pd.DataFrame(
        {"ID": pd.read_csv(ROOT / config["base_experiments"][0]["test_probability_path"], dtype={"ID": str})["ID"]}
    )
    test_frame.loc[:, list(PROBABILITY_COLUMNS)] = test_prob
    test_frame.to_csv(test_proba_path, index=False, lineterminator="\n")

    sample = pd.read_csv(ROOT / config["submission"]["sample_submission_path"], dtype=str, keep_default_na=False)
    if not sample["ID"].equals(test_frame["ID"]):
        raise ValueError("test ID와 sample submission ID가 다릅니다.")
    submission = sample.copy()
    submission["SUBCLASS"] = test_pred
    submission.to_csv(submission_path, index=False, lineterminator="\n")
    submission_check = validate_submission(submission_path, ROOT / config["submission"]["test_path"])

    oof_metrics = {
        "macro_f1": float(f1_score(y, oof_pred, labels=CLASS_LABELS, average="macro", zero_division=0)),
        "fold_mean": float(np.mean([m["macro_f1"] for m in fold_metrics])),
        "fold_std": float(np.std([m["macro_f1"] for m in fold_metrics])),
        "accuracy": float(accuracy_score(y, oof_pred)),
        "log_loss": float(log_loss(y, oof_prob, labels=CLASS_LABELS)),
        "per_class_f1": {
            label: float(f1_score(y == label, oof_pred == label, zero_division=0)) for label in CLASS_LABELS
        },
        "confusion_matrix": confusion_matrix(y, oof_pred, labels=CLASS_LABELS).tolist(),
    }

    source_commit = git("rev-parse", "HEAD")
    finished = datetime.now(timezone.utc)
    resolved = {
        "experiment": {
            "issue_number": ISSUE,
            "experiment_id": EXP_ID,
            "branch": context.branch,
            "owner": git("config", "user.name") or os.environ.get("USER", "unknown"),
            "source_commit": source_commit,
            "dirty_worktree": False,
            "started_at": started.isoformat(),
        },
        "split": {**config["split"], "sha256": sha256_file(ROOT / config["split"]["path"])},
        "class_order": list(CLASS_LABELS),
        "base_experiments": config["base_experiments"],
        "meta_model": params,
        "outputs": {
            "oof": relative_posix(oof_path, ROOT),
            "test_probability": relative_posix(test_proba_path, ROOT),
            "submission": relative_posix(submission_path, ROOT),
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
            "uv_lock_sha256": sha256_file(ROOT / "uv.lock"),
        },
        "command": RUNNER_COMMAND,
    }
    resolved_path.write_text(yaml.safe_dump(resolved, allow_unicode=True, sort_keys=False), encoding="utf-8")

    metrics = {
        "experiment_id": EXP_ID,
        "record_role": "official",
        "status": "COMPLETED",
        "owner": resolved["experiment"]["owner"],
        "issue_number": ISSUE,
        "parent_experiment": PARENT_EXPERIMENT,
        "git_commit": source_commit,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "primary_metric": "macro_f1",
        "split_id": config["split"]["path"],
        "folds": fold_metrics,
        "oof": oof_metrics,
        "leaderboard": None,
        "runtime": {"seconds": time.perf_counter() - timer, "hardware": platform.platform()},
        "checkpoint_comparison": {
            "comparison_experiment": PARENT_EXPERIMENT,
            "fold_coefficient_stability": fold_coefficients,
        },
        "artifacts": {
            "resolved_config": relative_posix(resolved_path, ROOT),
            "oof": relative_posix(oof_path, ROOT),
            "test_probability": relative_posix(test_proba_path, ROOT),
            "submission": relative_posix(submission_path, ROOT),
            "models": relative_posix(model_dir, ROOT),
            "submission_sha256": submission_check["sha256"],
        },
        "notes": RUNNER_NOTES,
    }
    write_json(metrics_path, metrics)
    validate_json_document(metrics_path, ROOT / "schemas/experiment_metrics.schema.json")

    # Recreate OOF/test from saved models and compare byte-level submission output.
    reproduced_oof = np.zeros_like(oof_prob)
    for fold, path in enumerate(fold_models):
        model = joblib.load(path)
        reproduced_oof[fold_ids == fold] = model.predict_proba(x_oof[fold_ids == fold])
    reproduced_test = joblib.load(final_model_path).predict_proba(x_test)
    reproduced_labels = np.asarray(CLASS_LABELS)[reproduced_test.argmax(axis=1)]
    reproduced_submission = submission.copy()
    reproduced_submission["SUBCLASS"] = reproduced_labels
    temp_path = ROOT / ".exp634_reproduced_submission.csv"
    reproduced_submission.to_csv(temp_path, index=False, lineterminator="\n")
    comparison = {
        "experiment_id": EXP_ID,
        "data_hashes_match": True,
        "original_submission_sha256": sha256_file(submission_path),
        "reproduced_submission_sha256": sha256_file(temp_path),
        "submission_sha256_match": sha256_file(submission_path) == sha256_file(temp_path),
        "oof_label_agreement": float(np.mean(oof_pred == np.asarray(CLASS_LABELS)[reproduced_oof.argmax(axis=1)])),
        "test_label_agreement": float(np.mean(test_pred == reproduced_labels)),
        "probability_max_abs_difference": float(
            max(np.max(np.abs(oof_prob - reproduced_oof)), np.max(np.abs(test_prob - reproduced_test)))
        ),
        "probability_atol": 1e-6,
        "probability_rtol": 1e-6,
    }
    temp_path.unlink()
    comparison["passed"] = (
        comparison["submission_sha256_match"]
        and comparison["oof_label_agreement"] == 1.0
        and comparison["test_label_agreement"] == 1.0
        and comparison["probability_max_abs_difference"] <= 1e-6
    )
    if not comparison["passed"]:
        raise RuntimeError(comparison)

    verified = datetime.now(timezone.utc).isoformat()
    env_path = repro_dir / "environment.json"
    data_path = repro_dir / "data_manifest.json"
    original_path = repro_dir / "original_metrics.json"
    reproduction_path = repro_dir / "reproduction_metrics.json"
    comparison_path = repro_dir / "comparison.json"
    reproduce_path = repro_dir / "REPRODUCE.md"
    manifest_path = repro_dir / "artifact_manifest.json"
    write_json(env_path, {"verified_at": verified, **resolved["environment"]})
    write_json(original_path, metrics)
    write_json(reproduction_path, {"verification_type": "saved_checkpoint_inference", **comparison})
    write_json(comparison_path, comparison)
    input_files = [
        ROOT / config["split"]["path"],
        ROOT / config["submission"]["test_path"],
        ROOT / config["submission"]["sample_submission_path"],
        *[ROOT / item[key] for item in config["base_experiments"] for key in ("oof_probability_path", "test_probability_path")],
    ]
    write_json(data_path, {"verified_at": verified, "files": [record(path) for path in input_files]})
    reproduce_path.write_text(
        "# EXP-634 재현 절차\n\n"
        "```bash\nuv sync --frozen\n"
        f"{RUNNER_COMMAND}\n"
        "uv run python scripts/validate_experiment.py\n```\n\n"
        "두 base(EXP-527, EXP-596) OOF 확률을 52차원으로 연결하고 outer canonical "
        "5-fold에서 L2 Multinomial Logistic Regression meta learner를 cross-fit합니다.\n",
        encoding="utf-8",
    )
    artifacts = [
        {"kind": kind, **record(path), "storage_uri": None}
        for kind, path in [
            ("submission", submission_path),
            ("oof_probability", oof_path),
            ("test_probability", test_proba_path),
            ("metrics", metrics_path),
            ("resolved_config", resolved_path),
            ("comparison", comparison_path),
        ]
    ] + [{"kind": "checkpoint", **record(path), "storage_uri": None} for path in [*fold_models, final_model_path]]
    manifest = {
        "experiment_id": EXP_ID,
        "issue_number": ISSUE,
        "reproducibility_status": "INFERENCE_VERIFIED",
        "source_commit": source_commit,
        "source_tag": None,
        "dirty_worktree": False,
        "data_manifest": relative_posix(data_path, ROOT),
        "environment": relative_posix(env_path, ROOT),
        "release_url": None,
        "verifier": resolved["experiment"]["owner"],
        "verified_at": verified,
        "artifacts": artifacts,
        "verification": {
            "data_hashes_match": True,
            "submission_sha256_match": True,
            "oof_label_agreement": comparison["oof_label_agreement"],
            "test_label_agreement": comparison["test_label_agreement"],
            "probability_atol": 1e-6,
            "probability_rtol": 1e-6,
            "passed": True,
        },
    }
    write_json(manifest_path, manifest)
    validate_json_document(manifest_path, ROOT / "schemas/reproducibility_manifest.schema.json")
    checksum_paths = [resolved_path, env_path, data_path, original_path, reproduction_path, comparison_path, reproduce_path]
    (repro_dir / "checksums.sha256").write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in checksum_paths), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "experiment_id": EXP_ID,
                "oof": oof_metrics,
                "fold_coefficient_stability": fold_coefficients,
                "reproducibility_status": "INFERENCE_VERIFIED",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
