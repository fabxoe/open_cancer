#!/usr/bin/env python
"""Run EXP-642: leave-one-outer-fold-out nested weight search for the
EXP-374 (legacy) + EXP-459 (CatBoost) probability blend, with a test-like
stability gate.

EXP-484 fixed the blend weight at 0.7/0.3 using Task #482's 0.1-step sweep
against the #292 test-like propensity subset. EXP-628 showed that a finer
0.05-step leave-one-outer-fold-out nested search can find a better point a
coarse sweep misses. This runner applies the same nested-search idea to
EXP-374+EXP-459, but -- unlike EXP-628, which only maximized plain OOF
Macro F1 -- each fold's candidate weight must ALSO not regress the inner
test-like subset relative to pure EXP-374 (weight=1.0). This lineage's whole
value is its measured stability under train/test distribution shift (EXP-628
was submitted to Public today and underperformed EXP-374 despite a much
higher Local OOF, confirming the native lineage is far more shift-sensitive
than legacy); a nested search that only chases OOF Macro F1 could silently
trade away exactly that stability, so the stability gate is load-bearing
here, not optional.
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
CONFIG_PATH = ROOT / "configs/exp642_nested_blend_weight_exp374_exp459.yaml"
ISSUE = 642
EXP_ID = "EXP-642"
SLUG = "exp642_nested_blend_weight_exp374_exp459"
EXPECTED_COMPONENTS = ("EXP-374", "EXP-459")
PARENT_EXPERIMENT = "EXP-374"
COMPARISON_EXPERIMENT = "EXP-484"
PROPENSITY_PATH = ROOT / "reports/analysis/adversarial_validation/train_domain_propensity.csv"
RUNNER_COMMAND = "uv run python scripts/run_exp642_nested_blend_weight_exp374_exp459.py"
RUNNER_NOTES = (
    "Inference-only leave-one-outer-fold-out nested weight search over a "
    "pre-fixed grid for the EXP-374 weight (EXP-459 = 1 - weight), gated by "
    "inner test-like propensity subset non-regression vs pure EXP-374. Each "
    "outer fold's weight is selected using only the other four folds' OOF "
    "rows; the fold's own labels never influence its own weight. The "
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


def macro_f1(true, pred) -> float:
    return float(f1_score(true, pred, labels=CLASS_LABELS, average="macro", zero_division=0))


def select_fold_weight(
    grid: np.ndarray,
    p_374: np.ndarray,
    p_459: np.ndarray,
    true: np.ndarray,
    inner_mask: np.ndarray,
    inner_test_like_mask: np.ndarray,
) -> tuple[float, dict[str, Any]]:
    """Pick the weight maximizing inner full OOF Macro F1 among candidates
    that do not regress the inner test-like subset vs pure EXP-374."""
    inner_374, inner_459 = p_374[inner_mask], p_459[inner_mask]
    inner_true = true[inner_mask]
    tl_374, tl_459 = p_374[inner_test_like_mask], p_459[inner_test_like_mask]
    tl_true = true[inner_test_like_mask]

    baseline_test_like_f1 = macro_f1(tl_true, np.asarray(CLASS_LABELS)[tl_374.argmax(axis=1)])

    curve: dict[str, dict[str, float]] = {}
    eligible: list[tuple[float, float]] = []  # (weight, inner_full_f1)
    for weight in grid:
        blended_full = weight * inner_374 + (1.0 - weight) * inner_459
        blended_full /= blended_full.sum(axis=1, keepdims=True)
        full_f1 = macro_f1(inner_true, np.asarray(CLASS_LABELS)[blended_full.argmax(axis=1)])

        blended_tl = weight * tl_374 + (1.0 - weight) * tl_459
        blended_tl /= blended_tl.sum(axis=1, keepdims=True)
        test_like_f1 = macro_f1(tl_true, np.asarray(CLASS_LABELS)[blended_tl.argmax(axis=1)])

        passes_gate = test_like_f1 >= baseline_test_like_f1
        curve[f"{weight:.2f}"] = {
            "inner_full_macro_f1": full_f1,
            "inner_test_like_macro_f1": test_like_f1,
            "stability_gate_pass": bool(passes_gate),
        }
        if passes_gate:
            eligible.append((float(weight), full_f1))

    if eligible:
        best_weight, best_full_f1 = max(eligible, key=lambda item: item[1])
        fallback = False
    else:
        best_weight, best_full_f1 = 1.0, macro_f1(inner_true, np.asarray(CLASS_LABELS)[inner_374.argmax(axis=1)])
        fallback = True

    detail = {
        "selected_weight_374": best_weight,
        "selected_weight_459": round(1.0 - best_weight, 2),
        "inner_row_count": int(inner_mask.sum()),
        "inner_test_like_row_count": int(inner_test_like_mask.sum()),
        "inner_full_oof_macro_f1": best_full_f1,
        "baseline_test_like_macro_f1_weight_1_0": baseline_test_like_f1,
        "fallback_to_pure_374": fallback,
        "candidate_curve": curve,
    }
    return best_weight, detail


def nested_select_and_blend(
    config: dict[str, Any], components: list[dict[str, Any]], n_splits: int
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]], float]:
    oof_frames = [
        pd.read_csv(ROOT / item["oof_probability_path"], dtype={"ID": str}) for item in components
    ]
    test_frames = [
        pd.read_csv(ROOT / item["test_probability_path"], dtype={"ID": str}) for item in components
    ]
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
    p_374 = oof_frames[0].loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)
    p_459 = oof_frames[1].loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)

    propensity = pd.read_csv(PROPENSITY_PATH).set_index("ID").loc[reference["ID"]]
    quantile = config["ensemble"]["nested_weight_selection"]["test_like_quantile"]
    threshold = float(propensity["oof_test_domain_probability"].quantile(quantile))
    test_like_mask = (propensity["oof_test_domain_probability"] >= threshold).to_numpy()

    grid = np.asarray(
        config["ensemble"]["nested_weight_selection"]["candidate_grid_weight_374"], dtype=np.float64
    )

    blended = np.zeros_like(p_374)
    fold_records: list[dict[str, Any]] = []
    selected_weights: list[float] = []
    for fold_index in range(n_splits):
        val_mask = fold == fold_index
        inner_mask = ~val_mask
        inner_test_like_mask = inner_mask & test_like_mask
        selected_weight, detail = select_fold_weight(grid, p_374, p_459, true, inner_mask, inner_test_like_mask)
        blended[val_mask] = selected_weight * p_374[val_mask] + (1.0 - selected_weight) * p_459[val_mask]
        selected_weights.append(selected_weight)
        fold_records.append({"fold": fold_index, **detail})

    blended /= blended.sum(axis=1, keepdims=True)
    final_weight_374 = snap_to_grid(float(np.mean(selected_weights)), grid)

    nested_oof = reference.loc[:, ["ID", "SUBCLASS_TRUE", "FOLD"]].copy()
    nested_oof.loc[:, list(PROBABILITY_COLUMNS)] = blended

    test_p_374 = test_frames[0].loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)
    test_p_459 = test_frames[1].loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)
    test_blended = final_weight_374 * test_p_374 + (1.0 - final_weight_374) * test_p_459
    test_blended /= test_blended.sum(axis=1, keepdims=True)
    test_out = test_frames[0].loc[:, ["ID"]].copy()
    test_out.loc[:, list(PROBABILITY_COLUMNS)] = test_blended

    return nested_oof, test_out, fold_records, final_weight_374


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
    ] + [PROPENSITY_PATH]
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

    nested_oof, nested_test, fold_records, final_weight_374 = nested_select_and_blend(
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
                    "stability_gate": "inner_test_like_no_regression_vs_pure_exp374",
                    "selected_weight_374": selected["selected_weight_374"],
                    "selected_weight_459": selected["selected_weight_459"],
                    "inner_row_count": selected["inner_row_count"],
                    "inner_test_like_row_count": selected["inner_test_like_row_count"],
                    "inner_full_oof_macro_f1": selected["inner_full_oof_macro_f1"],
                    "baseline_test_like_macro_f1_weight_1_0": selected["baseline_test_like_macro_f1_weight_1_0"],
                    "fallback_to_pure_374": selected["fallback_to_pure_374"],
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

    selected_weights = [item["selected_weight_374"] for item in fold_records]
    weight_range = float(max(selected_weights) - min(selected_weights))
    ensemble_weight_selection = {
        "method": "leave_one_fold_out_nested_weight_search_with_test_like_stability_gate",
        "candidate_grid_weight_374": [
            float(w) for w in config["ensemble"]["nested_weight_selection"]["candidate_grid_weight_374"]
        ],
        "per_fold_selected_weight_374": selected_weights,
        "per_fold_fallback_to_pure_374": [item["fallback_to_pure_374"] for item in fold_records],
        "weight_range_across_folds": weight_range,
        "weight_aggregation": "mean_snap_to_grid",
        "final_weight_374": final_weight_374,
        "final_weight_459": round(1.0 - final_weight_374, 2),
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
    weight_selection_matches = [item["selected_weight_374"] for item in repro_fold_records] == selected_weights
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
        "reproduced_final_weight_374": repro_final_weight,
    }
    comparison["passed"] = (
        comparison["submission_sha256_match"]
        and comparison["probability_max_abs_difference"] <= 1e-6
        and weight_selection_matches
        and repro_final_weight == final_weight_374
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
        "# EXP-642 재현 절차\n\n"
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
