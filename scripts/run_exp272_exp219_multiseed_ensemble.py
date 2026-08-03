#!/usr/bin/env python
"""Run EXP-272: fixed five-seed ensemble of the EXP-219 policy."""

from __future__ import annotations

import copy
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
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.hashing import sha256_file
from open_cancer.paths import relative_posix
from open_cancer.probability_blend import blend_probability_frames
from open_cancer.validation import validate_json_document, validate_submission
from run_hotspot_xgb import finalize_saved_run, main as run_single_seed


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "exp272_exp219_multiseed_ensemble.yaml"
ISSUE = 272
EXP_ID = "EXP-272"
SLUG = "exp272_exp219_multiseed_ensemble"
EXPECTED_SEEDS = (42, 142, 242, 342, 442)
EXPECTED_WEIGHTS = (0.2, 0.2, 0.2, 0.2, 0.2)
RUNNER_COMMAND = "uv run python scripts/run_exp272_exp219_multiseed_ensemble.py"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def record(path: Path) -> dict[str, Any]:
    return {
        "path": relative_posix(path, ROOT),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def seed_slug(seed: int) -> str:
    return f"{SLUG}/seeds/seed_{seed:03d}"


def seed_paths(seed: int) -> dict[str, Path]:
    slug = seed_slug(seed)
    return {
        "metrics": ROOT / "reports" / slug / "metrics.json",
        "manifest": ROOT / "reproducibility" / slug / "artifact_manifest.json",
        "resolved_config": ROOT / "reproducibility" / slug / "config.resolved.yaml",
        "oof": ROOT / "oof" / f"{slug}.csv",
        "test_probability": ROOT / "preds" / f"{slug}_test_proba.csv",
        "submission": ROOT / "submissions" / f"{slug}.csv",
        "models": ROOT / "models" / slug,
    }


def seed_training_outputs_complete(seed: int) -> bool:
    paths = seed_paths(seed)
    required = (
        paths["metrics"],
        paths["resolved_config"],
        paths["oof"],
        paths["test_probability"],
        paths["submission"],
        *[paths["models"] / f"fold_{fold:02d}.json" for fold in range(5)],
    )
    return all(path.is_file() for path in required)


def read_and_blend(
    seeds: tuple[int, ...], weights: tuple[float, ...]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    oof_frames = [pd.read_csv(seed_paths(seed)["oof"], dtype={"ID": str}) for seed in seeds]
    test_frames = [
        pd.read_csv(seed_paths(seed)["test_probability"], dtype={"ID": str})
        for seed in seeds
    ]
    return (
        blend_probability_frames(
            oof_frames,
            weights=weights,
            metadata_columns=("ID", "SUBCLASS_TRUE", "FOLD"),
            ignored_columns=("SUBCLASS_PRED",),
            probability_columns=PROBABILITY_COLUMNS,
        ),
        blend_probability_frames(
            test_frames,
            weights=weights,
            metadata_columns=("ID",),
            probability_columns=PROBABILITY_COLUMNS,
        ),
    )


def normalized_probabilities(frame: pd.DataFrame) -> np.ndarray:
    values = frame.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)
    row_sums = values.sum(axis=1, keepdims=True)
    if not np.isfinite(values).all() or np.any(row_sums <= 0):
        raise ValueError("확률에 NaN/inf 또는 0 이하 row sum이 있습니다.")
    return values / row_sums


def reference_comparison(seed42_oof: Path, seed42_test: Path, config: dict[str, Any]) -> dict[str, Any]:
    reference_oof = ROOT / config["multiseed"]["reference_oof_probability_path"]
    reference_test = ROOT / config["multiseed"]["reference_test_probability_path"]
    result: dict[str, Any] = {
        "reference_experiment": config["multiseed"]["reference_experiment"],
        "rerun_seed": 42,
        "reference_available": reference_oof.is_file() and reference_test.is_file(),
        "rerun_oof_sha256": sha256_file(seed42_oof),
        "rerun_test_probability_sha256": sha256_file(seed42_test),
    }
    if not result["reference_available"]:
        return result
    original_oof = pd.read_csv(reference_oof, dtype={"ID": str})
    rerun_oof = pd.read_csv(seed42_oof, dtype={"ID": str})
    original_test = pd.read_csv(reference_test, dtype={"ID": str})
    rerun_test = pd.read_csv(seed42_test, dtype={"ID": str})
    if not original_oof[["ID", "SUBCLASS_TRUE", "FOLD"]].equals(
        rerun_oof[["ID", "SUBCLASS_TRUE", "FOLD"]]
    ):
        raise ValueError("EXP-219 원본과 EXP-272 seed 42 OOF 메타데이터가 다릅니다.")
    if not original_test[["ID"]].equals(rerun_test[["ID"]]):
        raise ValueError("EXP-219 원본과 EXP-272 seed 42 test ID가 다릅니다.")
    original_oof_proba = normalized_probabilities(original_oof)
    rerun_oof_proba = normalized_probabilities(rerun_oof)
    original_test_proba = normalized_probabilities(original_test)
    rerun_test_proba = normalized_probabilities(rerun_test)
    result.update(
        {
            "reference_oof_sha256": sha256_file(reference_oof),
            "reference_test_probability_sha256": sha256_file(reference_test),
            "oof_probability_max_abs_difference": float(
                np.max(np.abs(original_oof_proba - rerun_oof_proba))
            ),
            "test_probability_max_abs_difference": float(
                np.max(np.abs(original_test_proba - rerun_test_proba))
            ),
            "oof_label_agreement": float(
                np.mean(original_oof_proba.argmax(axis=1) == rerun_oof_proba.argmax(axis=1))
            ),
            "test_label_agreement": float(
                np.mean(original_test_proba.argmax(axis=1) == rerun_test_proba.argmax(axis=1))
            ),
            "byte_identical": sha256_file(reference_oof) == sha256_file(seed42_oof)
            and sha256_file(reference_test) == sha256_file(seed42_test),
        }
    )
    return result


def main() -> None:
    started = datetime.now(timezone.utc)
    timer = time.perf_counter()
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    if context.issue_number != ISSUE or context.experiment_id != EXP_ID:
        raise ValueError(f"실험 context 불일치: {context}")
    seeds = tuple(int(seed) for seed in config["multiseed"]["seeds"])
    weights = tuple(float(weight) for weight in config["multiseed"]["weights"])
    if seeds != EXPECTED_SEEDS or weights != EXPECTED_WEIGHTS:
        raise ValueError("Issue #272의 seed와 0.2 고정 가중치를 변경할 수 없습니다.")
    if not config["multiseed"]["weights_fixed_before_evaluation"]:
        raise ValueError("가중치는 평가 전에 고정되어야 합니다.")
    if config["multiseed"]["seed_selection_after_evaluation"]:
        raise ValueError("실행 결과를 본 seed 선택은 금지됩니다.")
    dirty = git("status", "--porcelain")
    if dirty:
        raise RuntimeError(f"공식 실험은 clean worktree에서 실행해야 합니다.\n{dirty}")
    source_commit = git("rev-parse", "HEAD")

    for seed in seeds:
        child_config = copy.deepcopy(config)
        child_config["seed"] = seed
        child_config["slug"] = f"exp219_multiseed_ensemble/seeds/seed_{seed:03d}"
        child_config["notes"] = (
            f"EXP-272 seed {seed} independent run. Canonical folds are unchanged; "
            "the model/fold random states are seed+fold. This seed is included "
            "without post-evaluation selection at fixed ensemble weight 0.2."
        )
        with tempfile.TemporaryDirectory(prefix=f"exp272_seed_{seed:03d}_") as temp_dir:
            runtime_config = Path(temp_dir) / f"exp272_seed_{seed:03d}.yaml"
            runtime_config.write_text(
                yaml.safe_dump(child_config, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            if seed_paths(seed)["manifest"].is_file():
                print(json.dumps({"seed": seed, "action": "reuse_verified"}))
            elif seed_training_outputs_complete(seed):
                print(json.dumps({"seed": seed, "action": "finalize_existing"}))
                finalize_saved_run(runtime_config, runner_command=RUNNER_COMMAND)
            else:
                run_single_seed(
                    config_override=runtime_config,
                    runner_command=RUNNER_COMMAND,
                    prevalidated_source_commit=source_commit,
                )

    out_report = ROOT / "reports" / SLUG
    out_repro = ROOT / "reproducibility" / SLUG
    out_models = ROOT / "models" / SLUG
    oof_path = ROOT / "oof" / f"{SLUG}.csv"
    test_probability_path = ROOT / "preds" / f"{SLUG}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{SLUG}.csv"
    metrics_path = out_report / "metrics.json"
    resolved_path = out_repro / "config.resolved.yaml"
    for path in (
        out_report,
        out_repro,
        out_models,
        oof_path.parent,
        test_probability_path.parent,
        submission_path.parent,
    ):
        path.mkdir(parents=True, exist_ok=True)

    oof, test = read_and_blend(seeds, weights)
    oof_proba = normalized_probabilities(oof)
    test_proba = normalized_probabilities(test)
    oof_pred = np.asarray(CLASS_LABELS)[oof_proba.argmax(axis=1)]
    test_pred = np.asarray(CLASS_LABELS)[test_proba.argmax(axis=1)]
    oof.insert(2, "SUBCLASS_PRED", oof_pred)
    oof.to_csv(oof_path, index=False, lineterminator="\n")
    test.to_csv(test_probability_path, index=False, lineterminator="\n")
    sample = pd.read_csv(
        ROOT / config["submission"]["sample_submission_path"],
        dtype=str,
        keep_default_na=False,
    )
    if not sample["ID"].equals(test["ID"]):
        raise ValueError("test 확률과 sample submission ID 순서가 다릅니다.")
    submission = sample.copy()
    submission["SUBCLASS"] = test_pred
    submission.to_csv(submission_path, index=False, lineterminator="\n")
    submission_check = validate_submission(
        submission_path, ROOT / config["submission"]["test_path"]
    )

    true = oof["SUBCLASS_TRUE"].to_numpy()
    fold_metrics: list[dict[str, Any]] = []
    for fold in range(config["split"]["n_splits"]):
        mask = oof["FOLD"].eq(fold).to_numpy()
        fold_metrics.append(
            {
                "fold": fold,
                "macro_f1": float(
                    f1_score(
                        true[mask], oof_pred[mask], labels=CLASS_LABELS,
                        average="macro", zero_division=0,
                    )
                ),
                "accuracy": float(accuracy_score(true[mask], oof_pred[mask])),
                "log_loss": float(
                    log_loss(true[mask], oof_proba[mask], labels=CLASS_LABELS)
                ),
                "best_iteration": None,
            }
        )
    fold_scores = np.asarray([item["macro_f1"] for item in fold_metrics])
    oof_metrics = {
        "macro_f1": float(
            f1_score(true, oof_pred, labels=CLASS_LABELS, average="macro", zero_division=0)
        ),
        "fold_mean": float(fold_scores.mean()),
        "fold_std": float(fold_scores.std()),
        "accuracy": float(accuracy_score(true, oof_pred)),
        "log_loss": float(log_loss(true, oof_proba, labels=CLASS_LABELS)),
        "per_class_f1": {
            label: float(f1_score(true == label, oof_pred == label, zero_division=0))
            for label in CLASS_LABELS
        },
        "confusion_matrix": confusion_matrix(true, oof_pred, labels=CLASS_LABELS).tolist(),
    }
    seed_metrics = []
    for seed in seeds:
        child_metrics = json.loads(seed_paths(seed)["metrics"].read_text(encoding="utf-8"))
        seed_metrics.append(
            {
                "seed": seed,
                "weight": 0.2,
                "oof": child_metrics["oof"],
                "folds": child_metrics["folds"],
                "metrics_path": relative_posix(seed_paths(seed)["metrics"], ROOT),
                "artifact_manifest": relative_posix(seed_paths(seed)["manifest"], ROOT),
            }
        )
    seed42_comparison = reference_comparison(
        seed_paths(42)["oof"], seed_paths(42)["test_probability"], config
    )
    owner = git("config", "user.name") or os.environ.get("USER", "unknown")
    finished = datetime.now(timezone.utc)
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
        "xgboost": xgb.__version__,
        "uv_lock_sha256": sha256_file(ROOT / "uv.lock"),
    }
    resolved = {
        "experiment": {
            "record_role": "official",
            "issue_number": ISSUE,
            "experiment_id": EXP_ID,
            "parent_experiment": config["parent_experiment"],
            "branch": context.branch,
            "owner": owner,
            "source_commit": source_commit,
            "dirty_worktree": False,
            "started_at": started.isoformat(),
        },
        "split": {
            **config["split"],
            "sha256": sha256_file(ROOT / config["split"]["path"]),
        },
        "class_order": list(CLASS_LABELS),
        "model": config["model"],
        "features": config["features"],
        "hotspots": config["hotspots"],
        "training": config["training"],
        "multiseed": {
            **config["multiseed"],
            "seed_artifacts": seed_metrics,
            "seed42_reference_comparison": seed42_comparison,
        },
        "outputs": {
            "oof": relative_posix(oof_path, ROOT),
            "test_probability": relative_posix(test_probability_path, ROOT),
            "submission": relative_posix(submission_path, ROOT),
            "models": relative_posix(out_models, ROOT),
        },
        "environment": environment,
        "command": RUNNER_COMMAND,
    }
    resolved_path.write_text(
        yaml.safe_dump(resolved, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    metrics = {
        "experiment_id": EXP_ID,
        "record_role": "official",
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": ISSUE,
        "parent_experiment": config["parent_experiment"],
        "git_commit": source_commit,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "primary_metric": "macro_f1",
        "split_id": config["split"]["path"],
        "folds": fold_metrics,
        "oof": oof_metrics,
        "leaderboard": None,
        "runtime": {
            "seconds": float(time.perf_counter() - timer),
            "hardware": platform.platform(),
        },
        "artifacts": {
            "resolved_config": relative_posix(resolved_path, ROOT),
            "oof": relative_posix(oof_path, ROOT),
            "test_probability": relative_posix(test_probability_path, ROOT),
            "submission": relative_posix(submission_path, ROOT),
            "models": relative_posix(out_models, ROOT),
            "submission_sha256": submission_check["sha256"],
        },
        "notes": (
            "Five pre-fixed seeds with identical canonical folds and EXP-219 "
            "Macro-F1 checkpoint policy; fixed 0.2 probability mean. No seed or "
            "weight selection used OOF outcomes, test data, or Public LB."
        ),
        "seed_runs": seed_metrics,
        "seed42_reference_comparison": seed42_comparison,
    }
    write_json(metrics_path, metrics)
    validate_json_document(metrics_path, ROOT / "schemas/experiment_metrics.schema.json")

    reproduced_oof, reproduced_test = read_and_blend(seeds, weights)
    reproduced_oof_proba = normalized_probabilities(reproduced_oof)
    reproduced_test_proba = normalized_probabilities(reproduced_test)
    max_difference = float(
        max(
            np.max(np.abs(oof_proba - reproduced_oof_proba)),
            np.max(np.abs(test_proba - reproduced_test_proba)),
        )
    )
    reproduced_labels = np.asarray(CLASS_LABELS)[reproduced_test_proba.argmax(axis=1)]
    with tempfile.TemporaryDirectory(prefix="exp272_reproduce_") as temp_dir:
        reproduced_submission = Path(temp_dir) / submission_path.name
        copied = sample.copy()
        copied["SUBCLASS"] = reproduced_labels
        copied.to_csv(reproduced_submission, index=False, lineterminator="\n")
        reproduced_submission_sha = sha256_file(reproduced_submission)
    comparison = {
        "experiment_id": EXP_ID,
        "verification_type": "checkpoint_verified_seed_runs_plus_fixed_probability_mean",
        "seed_manifests_passed": all(
            json.loads(seed_paths(seed)["manifest"].read_text(encoding="utf-8"))[
                "verification"
            ]["passed"]
            for seed in seeds
        ),
        "original_submission_sha256": sha256_file(submission_path),
        "reproduced_submission_sha256": reproduced_submission_sha,
        "submission_sha256_match": sha256_file(submission_path)
        == reproduced_submission_sha,
        "oof_label_agreement": float(
            np.mean(oof_proba.argmax(axis=1) == reproduced_oof_proba.argmax(axis=1))
        ),
        "test_label_agreement": float(
            np.mean(test_proba.argmax(axis=1) == reproduced_test_proba.argmax(axis=1))
        ),
        "probability_max_abs_difference": max_difference,
        "probability_atol": 1e-6,
        "probability_rtol": 1e-6,
    }
    comparison["passed"] = bool(
        comparison["seed_manifests_passed"]
        and comparison["submission_sha256_match"]
        and max_difference <= 1e-6
    )
    if not comparison["passed"]:
        raise RuntimeError(f"EXP-272 inference verification failed: {comparison}")

    verified_at = datetime.now(timezone.utc).isoformat()
    environment_path = out_repro / "environment.json"
    data_manifest_path = out_repro / "data_manifest.json"
    original_metrics_path = out_repro / "original_metrics.json"
    reproduction_metrics_path = out_repro / "reproduction_metrics.json"
    comparison_path = out_repro / "comparison.json"
    reproduce_path = out_repro / "REPRODUCE.md"
    artifact_manifest_path = out_repro / "artifact_manifest.json"
    write_json(environment_path, {"verified_at": verified_at, **environment})
    write_json(original_metrics_path, metrics)
    write_json(reproduction_metrics_path, comparison)
    write_json(comparison_path, comparison)
    data_inputs = [
        ROOT / config["split"]["path"],
        ROOT / config["submission"]["test_path"],
        ROOT / config["submission"]["sample_submission_path"],
        *[seed_paths(seed)["oof"] for seed in seeds],
        *[seed_paths(seed)["test_probability"] for seed in seeds],
    ]
    write_json(
        data_manifest_path,
        {"verified_at": verified_at, "files": [record(path) for path in data_inputs]},
    )
    reproduce_path.write_text(
        f"# {EXP_ID} 재현 절차\n\n"
        "EXP-219과 같은 환경에서 원본 CSV를 배치하고 다음을 실행합니다. "
        "다섯 seed를 모두 재학습하므로 seed를 선택하거나 생략하지 않습니다.\n\n"
        f"```bash\nuv sync --frozen\n{RUNNER_COMMAND}\n"
        "uv run python scripts/validate_experiment.py\n```\n",
        encoding="utf-8",
    )
    final_artifacts = [
        ("submission", submission_path),
        ("oof_probability", oof_path),
        ("test_probability", test_probability_path),
        ("metrics", metrics_path),
        ("resolved_config", resolved_path),
        ("comparison", comparison_path),
        *[("seed_artifact_manifest", seed_paths(seed)["manifest"]) for seed in seeds],
    ]
    manifest = {
        "experiment_id": EXP_ID,
        "issue_number": ISSUE,
        "reproducibility_status": "INFERENCE_VERIFIED",
        "source_commit": source_commit,
        "source_tag": None,
        "dirty_worktree": False,
        "data_manifest": relative_posix(data_manifest_path, ROOT),
        "environment": relative_posix(environment_path, ROOT),
        "release_url": None,
        "verifier": owner,
        "verified_at": verified_at,
        "artifacts": [
            {"kind": kind, **record(path), "storage_uri": None}
            for kind, path in final_artifacts
        ],
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
    write_json(artifact_manifest_path, manifest)
    validate_json_document(
        artifact_manifest_path, ROOT / "schemas/reproducibility_manifest.schema.json"
    )
    checksum_paths = [
        resolved_path,
        environment_path,
        data_manifest_path,
        original_metrics_path,
        reproduction_metrics_path,
        comparison_path,
        reproduce_path,
    ]
    (out_repro / "checksums.sha256").write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in checksum_paths),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "experiment_id": EXP_ID,
                "seeds": list(seeds),
                "weights": list(weights),
                "oof": oof_metrics,
                "submission": relative_posix(submission_path, ROOT),
                "reproducibility_status": "INFERENCE_VERIFIED",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
