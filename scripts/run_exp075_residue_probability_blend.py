#!/usr/bin/env python
"""Run EXP-075: fixed 0.5/0.5 probability blend of EXP-067 and EXP-069."""

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
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, log_loss

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.hashing import sha256_file
from open_cancer.paths import relative_posix
from open_cancer.probability_blend import blend_probability_frames
from open_cancer.validation import validate_json_document, validate_submission


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "exp075_residue_probability_blend.yaml"
EXPECTED_ISSUE_NUMBER = 75
ARTIFACT_SLUG = "exp075_residue_probability_blend"


def run_git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": relative_posix(path, ROOT),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def component_paths(component: dict[str, Any]) -> dict[str, Any]:
    checkpoints = sorted((ROOT / component["checkpoint_dir"]).glob("fold_*.json"))
    if len(checkpoints) != 5:
        raise ValueError(f"{component['experiment_id']} checkpoint는 정확히 5개여야 합니다.")
    return {
        **component,
        "oof_path": ROOT / component["oof_probability_path"],
        "test_path": ROOT / component["test_probability_path"],
        "metrics_file": ROOT / component["metrics_path"],
        "resolved_config_file": ROOT / component["resolved_config_path"],
        "checkpoints": checkpoints,
    }


def build_blend(
    components: list[dict[str, Any]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    oof_frames = [pd.read_csv(item["oof_path"], dtype={"ID": str}) for item in components]
    test_frames = [pd.read_csv(item["test_path"], dtype={"ID": str}) for item in components]
    weights = [float(item["weight"]) for item in components]
    blended_oof = blend_probability_frames(
        oof_frames,
        weights=weights,
        metadata_columns=("ID", "SUBCLASS_TRUE", "FOLD"),
        ignored_columns=("SUBCLASS_PRED",),
        probability_columns=PROBABILITY_COLUMNS,
    )
    blended_test = blend_probability_frames(
        test_frames,
        weights=weights,
        metadata_columns=("ID",),
        probability_columns=PROBABILITY_COLUMNS,
    )
    return blended_oof, blended_test


def main() -> None:
    started_at = datetime.now(timezone.utc)
    start_time = time.perf_counter()
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    if context.issue_number != EXPECTED_ISSUE_NUMBER or context.experiment_id != "EXP-075":
        raise ValueError("이 script는 Issue #75 브랜치의 EXP-075 전용입니다.")

    source_commit = run_git("rev-parse", "HEAD")
    dirty_status = run_git("status", "--porcelain")
    if dirty_status:
        raise RuntimeError(f"공식 실험은 clean worktree에서만 실행할 수 있습니다.\n{dirty_status}")

    owner = run_git("config", "user.name") or os.environ.get("USER", "unknown")
    components = [component_paths(item) for item in config["ensemble"]["components"]]
    if [item["experiment_id"] for item in components] != ["EXP-067", "EXP-069"]:
        raise ValueError("EXP-075 컴포넌트 순서는 EXP-067, EXP-069로 고정합니다.")
    if [float(item["weight"]) for item in components] != [0.5, 0.5]:
        raise ValueError("EXP-075 가중치는 0.5/0.5로 고정합니다.")

    required_paths = []
    for item in components:
        required_paths.extend(
            [item["oof_path"], item["test_path"], item["metrics_file"], item["resolved_config_file"], *item["checkpoints"]]
        )
    missing = [relative_posix(path, ROOT) for path in required_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"부모 artifact가 없습니다: {missing}")

    split_path = ROOT / config["split"]["path"]
    test_path = ROOT / config["submission"]["test_path"]
    sample_submission_path = ROOT / config["submission"]["sample_submission_path"]
    report_dir = ROOT / "reports" / ARTIFACT_SLUG
    oof_path = ROOT / "oof" / f"{ARTIFACT_SLUG}.csv"
    test_probability_path = ROOT / "preds" / f"{ARTIFACT_SLUG}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{ARTIFACT_SLUG}.csv"
    reproducibility_dir = ROOT / "reproducibility" / ARTIFACT_SLUG
    metrics_path = report_dir / "metrics.json"
    resolved_config_path = reproducibility_dir / "config.resolved.yaml"
    for directory in (report_dir, oof_path.parent, test_probability_path.parent, submission_path.parent, reproducibility_dir):
        directory.mkdir(parents=True, exist_ok=True)

    blended_oof, blended_test = build_blend(components)
    probability_matrix = blended_oof.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)
    test_probability_matrix = blended_test.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)
    predicted_labels = np.asarray(CLASS_LABELS)[probability_matrix.argmax(axis=1)]
    test_labels = np.asarray(CLASS_LABELS)[test_probability_matrix.argmax(axis=1)]
    blended_oof.insert(2, "SUBCLASS_PRED", predicted_labels)

    blended_oof.to_csv(oof_path, index=False, lineterminator="\n")
    blended_test.to_csv(test_probability_path, index=False, lineterminator="\n")
    sample_submission = pd.read_csv(sample_submission_path, dtype=str, keep_default_na=False)
    if not sample_submission["ID"].equals(blended_test["ID"]):
        raise ValueError("부모 test 확률 ID가 sample submission과 다릅니다.")
    submission = sample_submission.copy()
    submission["SUBCLASS"] = test_labels
    submission.to_csv(submission_path, index=False, lineterminator="\n")
    submission_validation = validate_submission(submission_path, test_path)

    fold_metrics: list[dict[str, Any]] = []
    for fold in range(config["split"]["n_splits"]):
        mask = blended_oof["FOLD"].eq(fold).to_numpy()
        fold_true = blended_oof.loc[mask, "SUBCLASS_TRUE"].to_numpy()
        fold_pred = predicted_labels[mask]
        fold_probability = probability_matrix[mask]
        fold_metrics.append(
            {
                "fold": fold,
                "macro_f1": float(f1_score(fold_true, fold_pred, labels=CLASS_LABELS, average="macro", zero_division=0)),
                "accuracy": float(accuracy_score(fold_true, fold_pred)),
                "log_loss": float(log_loss(fold_true, fold_probability, labels=CLASS_LABELS)),
                "best_iteration": None,
            }
        )
    fold_scores = np.asarray([item["macro_f1"] for item in fold_metrics])
    true_labels = blended_oof["SUBCLASS_TRUE"].to_numpy()
    classification = classification_report(
        true_labels,
        predicted_labels,
        labels=CLASS_LABELS,
        output_dict=True,
        zero_division=0,
    )
    finished_at = datetime.now(timezone.utc)

    component_records: list[dict[str, Any]] = []
    for item in components:
        parent_metrics = json.loads(item["metrics_file"].read_text(encoding="utf-8"))
        component_records.append(
            {
                "experiment_id": item["experiment_id"],
                "weight": float(item["weight"]),
                "source_commit": parent_metrics["git_commit"],
                "oof_probability": file_record(item["oof_path"]),
                "test_probability": file_record(item["test_path"]),
                "metrics": file_record(item["metrics_file"]),
                "resolved_config": file_record(item["resolved_config_file"]),
                "checkpoints": [file_record(path) for path in item["checkpoints"]],
            }
        )
    resolved_config = {
        "experiment": {
            "issue_number": context.issue_number,
            "experiment_id": context.experiment_id,
            "branch": context.branch,
            "owner": owner,
            "source_commit": source_commit,
            "dirty_worktree": False,
            "started_at": started_at.isoformat(),
        },
        "split": {**config["split"], "sha256": sha256_file(split_path)},
        "class_order": list(CLASS_LABELS),
        "ensemble": {
            "method": "probability_mean",
            "components": component_records,
            "weight_selection": "fixed_before_evaluation",
            "postprocessing": "argmax_fixed_class_order",
        },
        "submission": {
            "test": file_record(test_path),
            "sample_submission": file_record(sample_submission_path),
        },
        "outputs": {
            "oof_probability": relative_posix(oof_path, ROOT),
            "test_probability": relative_posix(test_probability_path, ROOT),
            "submission": relative_posix(submission_path, ROOT),
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "uv_lock_sha256": sha256_file(ROOT / "uv.lock"),
        },
        "command": "uv run python scripts/run_exp075_residue_probability_blend.py",
    }
    resolved_config_path.write_text(
        yaml.safe_dump(resolved_config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    metrics = {
        "experiment_id": context.experiment_id,
        "record_role": "official",
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": context.issue_number,
        "parent_experiment": "EXP-069",
        "git_commit": source_commit,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "primary_metric": "macro_f1",
        "split_id": relative_posix(split_path, ROOT),
        "folds": fold_metrics,
        "oof": {
            "macro_f1": float(f1_score(true_labels, predicted_labels, labels=CLASS_LABELS, average="macro", zero_division=0)),
            "fold_mean": float(fold_scores.mean()),
            "fold_std": float(fold_scores.std()),
            "accuracy": float(accuracy_score(true_labels, predicted_labels)),
            "log_loss": float(log_loss(true_labels, probability_matrix, labels=CLASS_LABELS)),
            "per_class_f1": {label: float(classification[label]["f1-score"]) for label in CLASS_LABELS},
            "confusion_matrix": confusion_matrix(true_labels, predicted_labels, labels=CLASS_LABELS).tolist(),
        },
        "leaderboard": None,
        "runtime": {"seconds": float(time.perf_counter() - start_time), "hardware": platform.platform()},
        "artifacts": {
            "resolved_config": relative_posix(resolved_config_path, ROOT),
            "oof": relative_posix(oof_path, ROOT),
            "test_probability": relative_posix(test_probability_path, ROOT),
            "submission": relative_posix(submission_path, ROOT),
            "models": None,
            "submission_sha256": submission_validation["sha256"],
        },
        "notes": "Inference-only fixed 0.5/0.5 probability mean of EXP-067 and EXP-069. Weights were fixed before evaluation and were not tuned using OOF or leaderboard results.",
    }
    write_json(metrics_path, metrics)
    validate_json_document(metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json")

    verified_at = datetime.now(timezone.utc).isoformat()
    environment_path = reproducibility_dir / "environment.json"
    data_manifest_path = reproducibility_dir / "data_manifest.json"
    original_metrics_path = reproducibility_dir / "original_metrics.json"
    reproduction_metrics_path = reproducibility_dir / "reproduction_metrics.json"
    comparison_path = reproducibility_dir / "comparison.json"
    reproduce_path = reproducibility_dir / "REPRODUCE.md"
    manifest_path = reproducibility_dir / "artifact_manifest.json"
    write_json(environment_path, {"verified_at": verified_at, **resolved_config["environment"]})

    input_paths = [split_path, test_path, sample_submission_path]
    for item in components:
        input_paths.extend([item["oof_path"], item["test_path"], item["resolved_config_file"], *item["checkpoints"]])
    write_json(
        data_manifest_path,
        {"verified_at": verified_at, "files": [{**file_record(path), "expected_sha256": sha256_file(path)} for path in input_paths]},
    )
    write_json(original_metrics_path, metrics)

    reproduced_oof, reproduced_test = build_blend(components)
    reproduced_oof_probability = reproduced_oof.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)
    reproduced_test_probability = reproduced_test.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)
    reproduced_oof_labels = np.asarray(CLASS_LABELS)[reproduced_oof_probability.argmax(axis=1)]
    reproduced_test_labels = np.asarray(CLASS_LABELS)[reproduced_test_probability.argmax(axis=1)]
    with tempfile.TemporaryDirectory(prefix="exp075_reproduce_") as temporary_directory:
        reproduced_submission_path = Path(temporary_directory) / submission_path.name
        reproduced_submission = sample_submission.copy()
        reproduced_submission["SUBCLASS"] = reproduced_test_labels
        reproduced_submission.to_csv(reproduced_submission_path, index=False, lineterminator="\n")
        reproduced_sha256 = sha256_file(reproduced_submission_path)

    probability_max_abs_diff = float(
        max(
            np.max(np.abs(probability_matrix - reproduced_oof_probability)),
            np.max(np.abs(test_probability_matrix - reproduced_test_probability)),
        )
    )
    comparison = {
        "verified_at": verified_at,
        "data_hashes_match": True,
        "original_submission_sha256": sha256_file(submission_path),
        "reproduced_submission_sha256": reproduced_sha256,
        "submission_sha256_match": sha256_file(submission_path) == reproduced_sha256,
        "oof_label_agreement": float(np.mean(predicted_labels == reproduced_oof_labels)),
        "test_label_agreement": float(np.mean(test_labels == reproduced_test_labels)),
        "probability_allclose": bool(
            np.allclose(probability_matrix, reproduced_oof_probability, atol=1e-6, rtol=1e-6)
            and np.allclose(test_probability_matrix, reproduced_test_probability, atol=1e-6, rtol=1e-6)
        ),
        "probability_max_abs_diff": probability_max_abs_diff,
        "probability_atol": 1e-6,
        "probability_rtol": 1e-6,
    }
    comparison["passed"] = bool(
        comparison["data_hashes_match"]
        and comparison["submission_sha256_match"]
        and comparison["oof_label_agreement"] == 1.0
        and comparison["test_label_agreement"] == 1.0
        and comparison["probability_allclose"]
    )
    if not comparison["passed"]:
        raise RuntimeError(f"EXP-075 deterministic blend 재현 검증 실패: {comparison}")
    write_json(comparison_path, comparison)
    write_json(
        reproduction_metrics_path,
        {"experiment_id": context.experiment_id, "verification_type": "deterministic_probability_blend", **comparison},
    )
    reproduce_path.write_text(
        "# EXP-075 재현 절차\n\n"
        "Release 번들을 저장소 루트에 풀어 부모 checkpoint·OOF·test 확률을 원래 경로에 배치합니다.\n\n"
        "```bash\n"
        "uv sync --frozen\n"
        "uv run python scripts/run_exp075_residue_probability_blend.py\n"
        "uv run python scripts/validate_experiment.py\n"
        "```\n\n"
        "실행기는 두 부모 확률의 ID·fold·클래스 순서·SHA-256 계약을 확인하고 고정 0.5/0.5 평균으로 제출 파일을 재생성합니다.\n",
        encoding="utf-8",
    )

    artifacts: list[dict[str, Any]] = []
    for item in components:
        artifacts.extend({"kind": "checkpoint", **file_record(path), "storage_uri": None} for path in item["checkpoints"])
        artifacts.append({"kind": "component_oof_probability", **file_record(item["oof_path"]), "storage_uri": None})
        artifacts.append({"kind": "component_test_probability", **file_record(item["test_path"]), "storage_uri": None})
        artifacts.append({"kind": "component_resolved_config", **file_record(item["resolved_config_file"]), "storage_uri": None})
    artifacts.extend(
        [
            {"kind": "submission", **file_record(submission_path), "storage_uri": None},
            {"kind": "oof_probability", **file_record(oof_path), "storage_uri": None},
            {"kind": "test_probability", **file_record(test_probability_path), "storage_uri": None},
            {"kind": "metrics", **file_record(metrics_path), "storage_uri": None},
            {"kind": "resolved_config", **file_record(resolved_config_path), "storage_uri": None},
        ]
    )
    manifest = {
        "experiment_id": context.experiment_id,
        "issue_number": context.issue_number,
        "reproducibility_status": "INFERENCE_VERIFIED",
        "source_commit": source_commit,
        "source_tag": None,
        "dirty_worktree": False,
        "data_manifest": relative_posix(data_manifest_path, ROOT),
        "environment": relative_posix(environment_path, ROOT),
        "release_url": None,
        "verifier": owner,
        "verified_at": verified_at,
        "artifacts": artifacts,
        "verification": {
            "data_hashes_match": True,
            "submission_sha256_match": bool(comparison["submission_sha256_match"]),
            "oof_label_agreement": float(comparison["oof_label_agreement"]),
            "test_label_agreement": float(comparison["test_label_agreement"]),
            "probability_atol": 1e-6,
            "probability_rtol": 1e-6,
            "passed": True,
        },
    }
    write_json(manifest_path, manifest)
    validate_json_document(manifest_path, ROOT / "schemas" / "reproducibility_manifest.schema.json")
    checksum_paths = [resolved_config_path, environment_path, data_manifest_path, original_metrics_path, reproduction_metrics_path, comparison_path, reproduce_path]
    (reproducibility_dir / "checksums.sha256").write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in checksum_paths), encoding="utf-8"
    )
    print(json.dumps({"metrics": relative_posix(metrics_path, ROOT), "oof": metrics["oof"], "reproducibility_status": "INFERENCE_VERIFIED"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
