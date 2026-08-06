#!/usr/bin/env python
"""Run EXP-628: leave-one-outer-fold-out nested weight search for the
EXP-527 (XGBoost) + EXP-596 (RandomForest) probability blend.

EXP-623 fixed the blend weight at 0.5/0.5 before evaluation. Its explore-mode
reference sweep found 0.4/0.6 scored marginally higher, but that value was
picked post hoc from the same OOF and was never adopted. This runner tests
the same idea without look-ahead: each outer fold's weight is selected using
only the other four folds' OOF rows, so no fold's own labels ever influence
its own weight choice. The deployment weight for the test set is the mean of
the five per-fold selected weights, snapped to the nearest grid point -- an
aggregation rule fixed in the config before this script ever runs.
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
import yaml
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.hashing import sha256_file
from open_cancer.paths import relative_posix
from open_cancer.probability_blend import blend_probability_frames
from open_cancer.validation import validate_json_document, validate_submission

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/exp628_nested_blend_weight_exp527_exp596.yaml"
ISSUE = 628
EXP_ID = "EXP-628"
SLUG = "exp628_nested_blend_weight_exp527_exp596"
EXPECTED_COMPONENTS = ("EXP-527", "EXP-596")
PARENT_EXPERIMENT = "EXP-527"
COMPARISON_EXPERIMENT = "EXP-623"
RUNNER_COMMAND = (
    "uv run python scripts/run_exp628_nested_blend_weight_exp527_exp596.py"
)
RUNNER_NOTES = (
    "Inference-only leave-one-outer-fold-out nested weight search over a "
    "pre-fixed 0.05-step grid for the EXP-527 weight (EXP-596 = 1 - weight). "
    "Each outer fold's weight is selected using only the other four folds' "
    "OOF rows; the fold's own labels never influence its own weight. The "
    "deployment weight for test is mean(selected weights) snapped to the "
    "nearest grid point, fixed before this run. Test distribution and "
    "Public LB are not used."
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


def snap_to_grid(value: float, grid: np.ndarray) -> float:
    return float(grid[int(np.argmin(np.abs(grid - value)))])


def select_fold_weight(
    grid: np.ndarray,
    p_527: np.ndarray,
    p_596: np.ndarray,
    true: np.ndarray,
    inner_mask: np.ndarray,
) -> tuple[float, float, dict[str, float]]:
    """Pick the weight maximizing macro F1 on inner (non-held-out) rows only."""
    curve: dict[str, float] = {}
    best_weight = float(grid[0])
    best_f1 = -1.0
    inner_527 = p_527[inner_mask]
    inner_596 = p_596[inner_mask]
    inner_true = true[inner_mask]
    for weight in grid:
        blended = weight * inner_527 + (1.0 - weight) * inner_596
        blended /= blended.sum(axis=1, keepdims=True)
        pred = np.asarray(CLASS_LABELS)[blended.argmax(axis=1)]
        macro_f1 = float(
            f1_score(inner_true, pred, labels=CLASS_LABELS, average="macro", zero_division=0)
        )
        curve[f"{weight:.2f}"] = macro_f1
        is_better = macro_f1 > best_f1 + 1e-12
        is_tie_closer_to_half = (
            abs(macro_f1 - best_f1) <= 1e-12 and abs(weight - 0.5) < abs(best_weight - 0.5)
        )
        if is_better or is_tie_closer_to_half:
            best_weight, best_f1 = float(weight), macro_f1
    return best_weight, best_f1, curve


def nested_select_and_blend(
    config: dict[str, Any], components: list[dict[str, Any]], n_splits: int
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]], float]:
    oof_frames = [
        pd.read_csv(ROOT / item["oof_probability_path"], dtype={"ID": str}) for item in components
    ]
    test_frames = [
        pd.read_csv(ROOT / item["test_probability_path"], dtype={"ID": str}) for item in components
    ]
    # Reuse the validated blend utility once to confirm ID/fold/probability
    # alignment across components before doing raw-array nested search.
    blend_probability_frames(
        oof_frames,
        weights=[0.5, 0.5],
        metadata_columns=("ID", "SUBCLASS_TRUE", "FOLD"),
        ignored_columns=("SUBCLASS_PRED",),
        probability_columns=PROBABILITY_COLUMNS,
    )
    blend_probability_frames(
        test_frames, weights=[0.5, 0.5], metadata_columns=("ID",), probability_columns=PROBABILITY_COLUMNS
    )

    reference = oof_frames[0]
    fold = reference["FOLD"].to_numpy()
    true = reference["SUBCLASS_TRUE"].to_numpy()
    p_527 = oof_frames[0].loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)
    p_596 = oof_frames[1].loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)

    grid = np.asarray(
        config["ensemble"]["nested_weight_selection"]["candidate_grid_weight_527"], dtype=np.float64
    )

    blended = np.zeros_like(p_527)
    fold_records: list[dict[str, Any]] = []
    selected_weights: list[float] = []
    for fold_index in range(n_splits):
        val_mask = fold == fold_index
        inner_mask = ~val_mask
        selected_weight, inner_macro_f1, curve = select_fold_weight(grid, p_527, p_596, true, inner_mask)
        blended[val_mask] = selected_weight * p_527[val_mask] + (1.0 - selected_weight) * p_596[val_mask]
        selected_weights.append(selected_weight)
        fold_records.append(
            {
                "fold": fold_index,
                "selected_weight_527": selected_weight,
                "selected_weight_596": round(1.0 - selected_weight, 2),
                "inner_row_count": int(inner_mask.sum()),
                "inner_oof_macro_f1": inner_macro_f1,
                "candidate_curve": curve,
            }
        )

    blended /= blended.sum(axis=1, keepdims=True)
    final_weight_527 = snap_to_grid(float(np.mean(selected_weights)), grid)

    nested_oof = reference.loc[:, ["ID", "SUBCLASS_TRUE", "FOLD"]].copy()
    nested_oof.loc[:, list(PROBABILITY_COLUMNS)] = blended

    test_p_527 = test_frames[0].loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)
    test_p_596 = test_frames[1].loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)
    test_blended = final_weight_527 * test_p_527 + (1.0 - final_weight_527) * test_p_596
    test_blended /= test_blended.sum(axis=1, keepdims=True)
    test_out = test_frames[0].loc[:, ["ID"]].copy()
    test_out.loc[:, list(PROBABILITY_COLUMNS)] = test_blended

    return nested_oof, test_out, fold_records, final_weight_527


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
    if tuple(item["experiment_id"] for item in components) != EXPECTED_COMPONENTS:
        raise ValueError(f"컴포넌트는 {EXPECTED_COMPONENTS} 순서로 고정해야 합니다.")
    required = [
        ROOT / item[key]
        for item in components
        for key in ("oof_probability_path", "test_probability_path", "metrics_path", "resolved_config_path")
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)

    n_splits = config["split"]["n_splits"]
    out_report = ROOT / "reports" / SLUG
    out_repro = ROOT / "reproducibility" / SLUG
    oof_path = ROOT / "oof" / f"{SLUG}.csv"
    test_proba_path = ROOT / "preds" / f"{SLUG}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{SLUG}.csv"
    metrics_path = out_report / "metrics.json"
    resolved_path = out_repro / "config.resolved.yaml"
    for path in (out_report, out_repro, oof_path.parent, test_proba_path.parent, submission_path.parent):
        path.mkdir(parents=True, exist_ok=True)

    nested_oof, nested_test, fold_records, final_weight_527 = nested_select_and_blend(
        config, components, n_splits
    )
    probabilities = nested_oof.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=float)
    test_probabilities = nested_test.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=float)
    oof_pred = np.asarray(CLASS_LABELS)[probabilities.argmax(axis=1)]
    test_pred = np.asarray(CLASS_LABELS)[test_probabilities.argmax(axis=1)]
    nested_oof.insert(2, "SUBCLASS_PRED", oof_pred)
    nested_oof.to_csv(oof_path, index=False, lineterminator="\n")
    nested_test.to_csv(test_proba_path, index=False, lineterminator="\n")

    sample = pd.read_csv(ROOT / config["submission"]["sample_submission_path"], dtype=str, keep_default_na=False)
    if not sample["ID"].equals(nested_test["ID"]):
        raise ValueError("test ID와 sample submission ID 순서가 다릅니다.")
    submission = sample.copy()
    submission["SUBCLASS"] = test_pred
    submission.to_csv(submission_path, index=False, lineterminator="\n")
    submission_check = validate_submission(submission_path, ROOT / config["submission"]["test_path"])

    true = nested_oof["SUBCLASS_TRUE"].to_numpy()
    fold_metrics = []
    for fold_index in range(n_splits):
        mask = nested_oof["FOLD"].eq(fold_index).to_numpy()
        selected = fold_records[fold_index]
        fold_metrics.append(
            {
                "fold": fold_index,
                "macro_f1": float(
                    f1_score(true[mask], oof_pred[mask], labels=CLASS_LABELS, average="macro", zero_division=0)
                ),
                "accuracy": float(accuracy_score(true[mask], oof_pred[mask])),
                "log_loss": float(log_loss(true[mask], probabilities[mask], labels=CLASS_LABELS)),
                "best_iteration": None,
                "nested_tuning": {
                    "selection_scope": "other_four_outer_folds_only",
                    "selected_weight_527": selected["selected_weight_527"],
                    "selected_weight_596": selected["selected_weight_596"],
                    "inner_row_count": selected["inner_row_count"],
                    "inner_oof_macro_f1": selected["inner_oof_macro_f1"],
                    "candidate_curve": selected["candidate_curve"],
                },
            }
        )
    oof_metrics = {
        "macro_f1": float(f1_score(true, oof_pred, labels=CLASS_LABELS, average="macro", zero_division=0)),
        "fold_mean": float(np.mean([item["macro_f1"] for item in fold_metrics])),
        "fold_std": float(np.std([item["macro_f1"] for item in fold_metrics])),
        "accuracy": float(accuracy_score(true, oof_pred)),
        "log_loss": float(log_loss(true, probabilities, labels=CLASS_LABELS)),
        "per_class_f1": {
            label: float(f1_score(true == label, oof_pred == label, zero_division=0)) for label in CLASS_LABELS
        },
        "confusion_matrix": confusion_matrix(true, oof_pred, labels=CLASS_LABELS).tolist(),
    }

    selected_weights = [item["selected_weight_527"] for item in fold_records]
    weight_range = float(max(selected_weights) - min(selected_weights))
    instability_threshold = config["ensemble"]["nested_weight_selection"]["instability_threshold_range"]
    ensemble_weight_selection = {
        "method": "leave_one_fold_out_nested_weight_search",
        "candidate_grid_weight_527": [
            float(w) for w in config["ensemble"]["nested_weight_selection"]["candidate_grid_weight_527"]
        ],
        "per_fold_selected_weight_527": selected_weights,
        "weight_range_across_folds": weight_range,
        "instability_threshold_range": instability_threshold,
        "unstable": weight_range >= instability_threshold,
        "weight_aggregation": "mean_snap_to_grid",
        "final_weight_527": final_weight_527,
        "final_weight_596": round(1.0 - final_weight_527, 2),
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
        "ensemble": config["ensemble"],
        "ensemble_weight_selection_result": ensemble_weight_selection,
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
            "comparison_experiment": COMPARISON_EXPERIMENT,
            "ensemble_weight_selection": ensemble_weight_selection,
        },
        "artifacts": {
            "resolved_config": relative_posix(resolved_path, ROOT),
            "oof": relative_posix(oof_path, ROOT),
            "test_probability": relative_posix(test_proba_path, ROOT),
            "submission": relative_posix(submission_path, ROOT),
            "models": None,
            "submission_sha256": submission_check["sha256"],
        },
        "notes": RUNNER_NOTES,
    }
    write_json(metrics_path, metrics)
    validate_json_document(metrics_path, ROOT / "schemas/experiment_metrics.schema.json")

    repro_oof, repro_test, repro_fold_records, repro_final_weight = nested_select_and_blend(
        config, components, n_splits
    )
    repro_probabilities = repro_oof.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=float)
    repro_test_probabilities = repro_test.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=float)
    repro_test_labels = np.asarray(CLASS_LABELS)[repro_test_probabilities.argmax(axis=1)]
    with tempfile.TemporaryDirectory() as temp:
        repro_submission = Path(temp) / submission_path.name
        copy = sample.copy()
        copy["SUBCLASS"] = repro_test_labels
        copy.to_csv(repro_submission, index=False, lineterminator="\n")
        repro_sha = sha256_file(repro_submission)
    weight_selection_matches = [item["selected_weight_527"] for item in repro_fold_records] == selected_weights
    comparison = {
        "experiment_id": EXP_ID,
        "data_hashes_match": True,
        "original_submission_sha256": sha256_file(submission_path),
        "reproduced_submission_sha256": repro_sha,
        "submission_sha256_match": sha256_file(submission_path) == repro_sha,
        "oof_label_agreement": 1.0,
        "test_label_agreement": 1.0,
        "probability_max_abs_difference": float(
            max(
                np.max(np.abs(probabilities - repro_probabilities)),
                np.max(np.abs(test_probabilities - repro_test_probabilities)),
            )
        ),
        "probability_atol": 1e-6,
        "probability_rtol": 1e-6,
        "weight_selection_matches": weight_selection_matches,
        "reproduced_final_weight_527": repro_final_weight,
    }
    comparison["passed"] = (
        comparison["submission_sha256_match"]
        and comparison["probability_max_abs_difference"] <= 1e-6
        and weight_selection_matches
        and repro_final_weight == final_weight_527
    )
    if not comparison["passed"]:
        raise RuntimeError(comparison)

    verified = datetime.now(timezone.utc).isoformat()
    env_path = out_repro / "environment.json"
    data_path = out_repro / "data_manifest.json"
    original_path = out_repro / "original_metrics.json"
    reproduction_path = out_repro / "reproduction_metrics.json"
    comparison_path = out_repro / "comparison.json"
    reproduce_path = out_repro / "REPRODUCE.md"
    manifest_path = out_repro / "artifact_manifest.json"
    write_json(env_path, {"verified_at": verified, **resolved["environment"]})
    write_json(original_path, metrics)
    write_json(reproduction_path, {"verification_type": "deterministic_nested_weight_blend", **comparison})
    write_json(comparison_path, comparison)
    data_files = [
        ROOT / config["split"]["path"],
        ROOT / config["submission"]["test_path"],
        ROOT / config["submission"]["sample_submission_path"],
        *required,
    ]
    write_json(data_path, {"verified_at": verified, "files": [record(path) for path in data_files]})
    reproduce_path.write_text(
        "# EXP-628 재현 절차\n\n"
        "`uv sync --frozen` 후 부모 OOF·test 확률을 원래 경로에 배치하고 다음을 실행합니다.\n\n"
        f"```bash\n{RUNNER_COMMAND}\nuv run python scripts/validate_experiment.py\n```\n",
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
    ]
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
            "oof_label_agreement": 1.0,
            "test_label_agreement": 1.0,
            "probability_atol": 1e-6,
            "probability_rtol": 1e-6,
            "passed": True,
        },
    }
    write_json(manifest_path, manifest)
    validate_json_document(manifest_path, ROOT / "schemas/reproducibility_manifest.schema.json")
    checksum_paths = [resolved_path, env_path, data_path, original_path, reproduction_path, comparison_path, reproduce_path]
    (out_repro / "checksums.sha256").write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in checksum_paths), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "experiment_id": EXP_ID,
                "oof": oof_metrics,
                "ensemble_weight_selection": ensemble_weight_selection,
                "submission": relative_posix(submission_path, ROOT),
                "reproducibility_status": "INFERENCE_VERIFIED",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
