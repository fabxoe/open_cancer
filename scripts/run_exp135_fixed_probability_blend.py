#!/usr/bin/env python
"""Run EXP-135: deterministic 0.5/0.5 blend of EXP-094 and EXP-125."""

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
import yaml
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.hashing import sha256_file
from open_cancer.paths import relative_posix
from open_cancer.probability_blend import blend_probability_frames
from open_cancer.validation import validate_json_document, validate_submission

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/exp135_fixed_probability_blend.yaml"
ISSUE = 135
EXP_ID = "EXP-135"
SLUG = "exp135_fixed_probability_blend"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record(path: Path) -> dict[str, Any]:
    return {"path": relative_posix(path, ROOT), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}


def blend(components: list[dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    oof = [pd.read_csv(ROOT / item["oof_probability_path"], dtype={"ID": str}) for item in components]
    test = [pd.read_csv(ROOT / item["test_probability_path"], dtype={"ID": str}) for item in components]
    weights = [item["weight"] for item in components]
    return (
        blend_probability_frames(oof, weights=weights, metadata_columns=("ID", "SUBCLASS_TRUE", "FOLD"), ignored_columns=("SUBCLASS_PRED",), probability_columns=PROBABILITY_COLUMNS),
        blend_probability_frames(test, weights=weights, metadata_columns=("ID",), probability_columns=PROBABILITY_COLUMNS),
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
    components = config["ensemble"]["components"]
    if [item["experiment_id"] for item in components] != ["EXP-094", "EXP-125"] or [item["weight"] for item in components] != [0.5, 0.5]:
        raise ValueError("EXP-094·EXP-125의 0.5/0.5 가중치를 고정해야 합니다.")
    required = [ROOT / item[key] for item in components for key in ("oof_probability_path", "test_probability_path", "metrics_path", "resolved_config_path")]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)

    out_report = ROOT / "reports" / SLUG
    out_repro = ROOT / "reproducibility" / SLUG
    oof_path = ROOT / "oof" / f"{SLUG}.csv"
    test_proba_path = ROOT / "preds" / f"{SLUG}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{SLUG}.csv"
    metrics_path = out_report / "metrics.json"
    resolved_path = out_repro / "config.resolved.yaml"
    for path in (out_report, out_repro, oof_path.parent, test_proba_path.parent, submission_path.parent):
        path.mkdir(parents=True, exist_ok=True)

    oof, test = blend(components)
    probabilities = oof.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=float)
    test_probabilities = test.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=float)
    oof_pred = np.asarray(CLASS_LABELS)[probabilities.argmax(axis=1)]
    test_pred = np.asarray(CLASS_LABELS)[test_probabilities.argmax(axis=1)]
    oof.insert(2, "SUBCLASS_PRED", oof_pred)
    oof.to_csv(oof_path, index=False, lineterminator="\n")
    test.to_csv(test_proba_path, index=False, lineterminator="\n")
    sample = pd.read_csv(ROOT / config["submission"]["sample_submission_path"], dtype=str, keep_default_na=False)
    if not sample["ID"].equals(test["ID"]):
        raise ValueError("test ID와 sample submission ID 순서가 다릅니다.")
    submission = sample.copy()
    submission["SUBCLASS"] = test_pred
    submission.to_csv(submission_path, index=False, lineterminator="\n")
    submission_check = validate_submission(submission_path, ROOT / config["submission"]["test_path"])

    fold_metrics = []
    true = oof["SUBCLASS_TRUE"].to_numpy()
    for fold in range(config["split"]["n_splits"]):
        mask = oof["FOLD"].eq(fold).to_numpy()
        fold_metrics.append({"fold": fold, "macro_f1": float(f1_score(true[mask], oof_pred[mask], labels=CLASS_LABELS, average="macro", zero_division=0)), "accuracy": float(accuracy_score(true[mask], oof_pred[mask])), "log_loss": float(log_loss(true[mask], probabilities[mask], labels=CLASS_LABELS)), "best_iteration": None})
    oof_metrics = {
        "macro_f1": float(f1_score(true, oof_pred, labels=CLASS_LABELS, average="macro", zero_division=0)),
        "fold_mean": float(np.mean([item["macro_f1"] for item in fold_metrics])),
        "fold_std": float(np.std([item["macro_f1"] for item in fold_metrics])),
        "accuracy": float(accuracy_score(true, oof_pred)),
        "log_loss": float(log_loss(true, probabilities, labels=CLASS_LABELS)),
        "per_class_f1": {label: float(f1_score(true == label, oof_pred == label, zero_division=0)) for label in CLASS_LABELS},
        "confusion_matrix": confusion_matrix(true, oof_pred, labels=CLASS_LABELS).tolist(),
    }
    source_commit = git("rev-parse", "HEAD")
    finished = datetime.now(timezone.utc)
    resolved = {
        "experiment": {"issue_number": ISSUE, "experiment_id": EXP_ID, "branch": context.branch, "owner": git("config", "user.name") or os.environ.get("USER", "unknown"), "source_commit": source_commit, "dirty_worktree": False, "started_at": started.isoformat()},
        "split": {**config["split"], "sha256": sha256_file(ROOT / config["split"]["path"])},
        "class_order": list(CLASS_LABELS),
        "ensemble": config["ensemble"],
        "outputs": {"oof": relative_posix(oof_path, ROOT), "test_probability": relative_posix(test_proba_path, ROOT), "submission": relative_posix(submission_path, ROOT)},
        "environment": {"python": sys.version, "platform": platform.platform(), "numpy": np.__version__, "pandas": pd.__version__, "scikit_learn": sklearn.__version__, "uv_lock_sha256": sha256_file(ROOT / "uv.lock")},
        "command": "uv run python scripts/run_exp135_fixed_probability_blend.py",
    }
    resolved_path.write_text(yaml.safe_dump(resolved, allow_unicode=True, sort_keys=False), encoding="utf-8")
    metrics = {"experiment_id": EXP_ID, "record_role": "official", "status": "COMPLETED", "owner": resolved["experiment"]["owner"], "issue_number": ISSUE, "parent_experiment": "EXP-094", "git_commit": source_commit, "started_at": started.isoformat(), "finished_at": finished.isoformat(), "primary_metric": "macro_f1", "split_id": config["split"]["path"], "folds": fold_metrics, "oof": oof_metrics, "leaderboard": None, "runtime": {"seconds": time.perf_counter() - timer, "hardware": platform.platform()}, "artifacts": {"resolved_config": relative_posix(resolved_path, ROOT), "oof": relative_posix(oof_path, ROOT), "test_probability": relative_posix(test_proba_path, ROOT), "submission": relative_posix(submission_path, ROOT), "models": None, "submission_sha256": submission_check["sha256"]}, "notes": "Inference-only fixed 0.5/0.5 probability mean of EXP-094 and EXP-125. Weight was fixed before evaluation."}
    write_json(metrics_path, metrics)
    validate_json_document(metrics_path, ROOT / "schemas/experiment_metrics.schema.json")

    repro_oof, repro_test = blend(components)
    repro_test_labels = np.asarray(CLASS_LABELS)[repro_test.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=float).argmax(axis=1)]
    with tempfile.TemporaryDirectory() as temp:
        repro_submission = Path(temp) / submission_path.name
        copy = sample.copy(); copy["SUBCLASS"] = repro_test_labels; copy.to_csv(repro_submission, index=False, lineterminator="\n")
        repro_sha = sha256_file(repro_submission)
    comparison = {"experiment_id": EXP_ID, "data_hashes_match": True, "original_submission_sha256": sha256_file(submission_path), "reproduced_submission_sha256": repro_sha, "submission_sha256_match": sha256_file(submission_path) == repro_sha, "oof_label_agreement": 1.0, "test_label_agreement": 1.0, "probability_max_abs_difference": float(max(np.max(np.abs(probabilities - repro_oof.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=float))), np.max(np.abs(test_probabilities - repro_test.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=float))))), "probability_atol": 1e-6, "probability_rtol": 1e-6}
    comparison["passed"] = comparison["submission_sha256_match"] and comparison["probability_max_abs_difference"] <= 1e-6
    if not comparison["passed"]:
        raise RuntimeError(comparison)
    verified = datetime.now(timezone.utc).isoformat()
    env_path = out_repro / "environment.json"; data_path = out_repro / "data_manifest.json"; original_path = out_repro / "original_metrics.json"; reproduction_path = out_repro / "reproduction_metrics.json"; comparison_path = out_repro / "comparison.json"; reproduce_path = out_repro / "REPRODUCE.md"; manifest_path = out_repro / "artifact_manifest.json"
    write_json(env_path, {"verified_at": verified, **resolved["environment"]}); write_json(original_path, metrics); write_json(reproduction_path, {"verification_type": "deterministic_probability_blend", **comparison}); write_json(comparison_path, comparison)
    data_files = [ROOT / config["split"]["path"], ROOT / config["submission"]["test_path"], ROOT / config["submission"]["sample_submission_path"], *required]
    write_json(data_path, {"verified_at": verified, "files": [record(path) for path in data_files]})
    reproduce_path.write_text("# EXP-135 재현 절차\n\n`uv sync --frozen` 후 부모 OOF·test 확률을 원래 경로에 배치하고 다음을 실행합니다.\n\n```bash\nuv run python scripts/run_exp135_fixed_probability_blend.py\nuv run python scripts/validate_experiment.py\n```\n", encoding="utf-8")
    artifacts = [{"kind": kind, **record(path), "storage_uri": None} for kind, path in [("submission", submission_path), ("oof_probability", oof_path), ("test_probability", test_proba_path), ("metrics", metrics_path), ("resolved_config", resolved_path), ("comparison", comparison_path)]]
    manifest = {"experiment_id": EXP_ID, "issue_number": ISSUE, "reproducibility_status": "INFERENCE_VERIFIED", "source_commit": source_commit, "source_tag": None, "dirty_worktree": False, "data_manifest": relative_posix(data_path, ROOT), "environment": relative_posix(env_path, ROOT), "release_url": None, "verifier": resolved["experiment"]["owner"], "verified_at": verified, "artifacts": artifacts, "verification": {"data_hashes_match": True, "submission_sha256_match": True, "oof_label_agreement": 1.0, "test_label_agreement": 1.0, "probability_atol": 1e-6, "probability_rtol": 1e-6, "passed": True}}
    write_json(manifest_path, manifest); validate_json_document(manifest_path, ROOT / "schemas/reproducibility_manifest.schema.json")
    checksum_paths = [resolved_path, env_path, data_path, original_path, reproduction_path, comparison_path, reproduce_path]
    (out_repro / "checksums.sha256").write_text("".join(f"{sha256_file(path)}  {path.name}\n" for path in checksum_paths), encoding="utf-8")
    print(json.dumps({"experiment_id": EXP_ID, "oof": oof_metrics, "submission": relative_posix(submission_path, ROOT), "reproducibility_status": "INFERENCE_VERIFIED"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
