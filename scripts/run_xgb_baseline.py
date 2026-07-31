#!/usr/bin/env python
"""Run the official Issue-derived XGBoost mutation-presence baseline."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import scipy
import sklearn
import xgboost as xgb
import yaml
from scipy import sparse
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.hashing import sha256_file, sha256_lines
from open_cancer.paths import relative_posix
from open_cancer.validation import (
    validate_competition_data,
    validate_json_document,
    validate_submission,
)
from open_cancer.xgb_baseline import (
    align_fold_ids,
    encode_fixed_labels,
    load_resolved_baseline_config,
    mutation_presence_matrix,
    select_gene_columns,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _relative(path: Path) -> str:
    return relative_posix(path, PROJECT_ROOT)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/exp003_xgb_baseline.yaml"),
        help="기본값을 덮어쓸 최소 YAML config",
    )
    return parser


def main() -> None:
    runtime_started = time.perf_counter()
    args = _build_parser().parse_args()
    config_path = (PROJECT_ROOT / args.config).resolve()
    config = load_resolved_baseline_config(config_path)
    context = resolve_experiment_context("experiment", cwd=PROJECT_ROOT)
    if context.experiment_id is None or context.issue_number is None:
        raise RuntimeError("공식 실험 ID를 만들 수 없습니다.")

    git_commit = _git_output("rev-parse", "HEAD")
    dirty_worktree = bool(_git_output("status", "--porcelain"))
    if dirty_worktree:
        raise RuntimeError(
            "공식 실험은 clean worktree에서만 시작할 수 있습니다. "
            "코드와 config를 먼저 커밋하세요."
        )

    seed = int(config["run"]["seed"])
    python_hash_seed = os.environ.get("PYTHONHASHSEED")
    if python_hash_seed != str(seed):
        raise RuntimeError(
            f"PYTHONHASHSEED={seed}로 실행해야 합니다. 현재 값: {python_hash_seed!r}"
        )

    started_at = _utc_now()
    np.random.seed(seed)

    data_paths = {
        key: (PROJECT_ROOT / value).resolve()
        for key, value in config["data"].items()
    }
    data_summary = validate_competition_data(
        data_paths["train_path"],
        data_paths["test_path"],
        data_paths["sample_submission_path"],
    )
    for key, config_key in (
        ("train", "train_path"),
        ("test", "test_path"),
        ("sample_submission", "sample_submission_path"),
    ):
        data_summary["files"][key]["path"] = _relative(data_paths[config_key])

    train = pd.read_csv(data_paths["train_path"], dtype=str, keep_default_na=False)
    test = pd.read_csv(data_paths["test_path"], dtype=str, keep_default_na=False)
    fold_table = pd.read_csv(
        data_paths["split_path"],
        dtype={"ID": str, "fold": int},
        keep_default_na=False,
    )
    gene_columns = list(train.columns[2:])
    gene_whitelist_path_value = config["features"].get("gene_whitelist_path")
    gene_selection_manifest: dict[str, Any] = {
        "gene_whitelist_path": None,
        "gene_whitelist_sha256": None,
        "gene_count": len(gene_columns),
        "gene_order_sha256": sha256_lines(gene_columns),
    }
    if gene_whitelist_path_value:
        gene_whitelist_path = (PROJECT_ROOT / gene_whitelist_path_value).resolve()
        gene_columns = select_gene_columns(gene_columns, gene_whitelist_path)
        gene_selection_manifest = {
            "gene_whitelist_path": _relative(gene_whitelist_path),
            "gene_whitelist_sha256": sha256_file(gene_whitelist_path),
            "gene_count": len(gene_columns),
            "gene_order_sha256": sha256_lines(gene_columns),
        }
    y = encode_fixed_labels(train["SUBCLASS"])
    n_splits = int(config["run"]["n_splits"])
    fold_ids = align_fold_ids(train["ID"], fold_table, n_splits)

    x_train = mutation_presence_matrix(train, gene_columns)
    x_test = mutation_presence_matrix(test, gene_columns)
    if bool(config["features"]["include_mutation_burden"]):
        train_burden = np.asarray(x_train.sum(axis=1), dtype=np.float32)
        test_burden = np.asarray(x_test.sum(axis=1), dtype=np.float32)
        x_train = sparse.hstack([x_train, train_burden], format="csr", dtype=np.float32)
        x_test = sparse.hstack([x_test, test_burden], format="csr", dtype=np.float32)

    artifact_slug = f"{context.artifact_prefix}_{config['experiment']['slug']}"
    model_dir = PROJECT_ROOT / "models" / artifact_slug
    oof_dir = PROJECT_ROOT / "oof" / artifact_slug
    prediction_dir = PROJECT_ROOT / "preds" / artifact_slug
    report_dir = PROJECT_ROOT / "reports" / artifact_slug
    reproduction_dir = PROJECT_ROOT / "reproducibility" / artifact_slug
    submission_path = PROJECT_ROOT / "submissions" / f"{artifact_slug}.csv"
    for directory in (model_dir, oof_dir, prediction_dir, report_dir, reproduction_dir):
        directory.mkdir(parents=True, exist_ok=True)

    model_params = dict(config["model"]["params"])
    model_params["n_jobs"] = int(config["run"]["n_jobs"])
    use_balanced_weight = bool(config["model"]["use_balanced_sample_weight"])
    oof_probabilities = np.full(
        (len(train), len(CLASS_LABELS)),
        np.nan,
        dtype=np.float32,
    )
    test_probabilities = np.zeros(
        (len(test), len(CLASS_LABELS)),
        dtype=np.float32,
    )
    fold_metrics: list[dict[str, int | float | None]] = []
    checkpoint_paths: list[Path] = []

    for fold in range(n_splits):
        valid_mask = fold_ids == fold
        train_indices = np.flatnonzero(~valid_mask)
        valid_indices = np.flatnonzero(valid_mask)
        fold_seed = seed + fold
        sample_weight = (
            compute_sample_weight(class_weight="balanced", y=y[train_indices])
            if use_balanced_weight
            else None
        )

        model = xgb.XGBClassifier(**model_params, random_state=fold_seed)
        model.fit(
            x_train[train_indices],
            y[train_indices],
            sample_weight=sample_weight,
            eval_set=[(x_train[valid_indices], y[valid_indices])],
            verbose=False,
        )
        if not np.array_equal(model.classes_, np.arange(len(CLASS_LABELS))):
            raise RuntimeError(f"fold {fold}의 확률 클래스 순서가 고정 순서와 다릅니다.")

        valid_probabilities = model.predict_proba(x_train[valid_indices]).astype(np.float32)
        fold_test_probabilities = model.predict_proba(x_test).astype(np.float32)
        oof_probabilities[valid_indices] = valid_probabilities
        test_probabilities += fold_test_probabilities / n_splits
        valid_predictions = valid_probabilities.argmax(axis=1)

        checkpoint_path = model_dir / f"fold_{fold:02d}.json"
        model.save_model(checkpoint_path)
        checkpoint_paths.append(checkpoint_path)
        fold_result = {
            "fold": fold,
            "macro_f1": float(
                f1_score(y[valid_indices], valid_predictions, average="macro")
            ),
            "accuracy": float(accuracy_score(y[valid_indices], valid_predictions)),
            "log_loss": float(
                log_loss(
                    y[valid_indices],
                    valid_probabilities,
                    labels=np.arange(len(CLASS_LABELS)),
                )
            ),
            "best_iteration": int(model.best_iteration),
            "train_rows": int(len(train_indices)),
            "valid_rows": int(len(valid_indices)),
            "seed": fold_seed,
        }
        fold_metrics.append(fold_result)
        print(
            f"fold={fold} macro_f1={fold_result['macro_f1']:.6f} "
            f"best_iteration={fold_result['best_iteration']}",
            flush=True,
        )

    if np.isnan(oof_probabilities).any():
        raise RuntimeError("OOF 확률에 채워지지 않은 값이 있습니다.")
    if not np.allclose(oof_probabilities.sum(axis=1), 1.0, atol=1e-5):
        raise RuntimeError("OOF 클래스 확률 합이 1이 아닙니다.")
    if not np.allclose(test_probabilities.sum(axis=1), 1.0, atol=1e-5):
        raise RuntimeError("test 클래스 확률 합이 1이 아닙니다.")

    oof_predictions = oof_probabilities.argmax(axis=1)
    test_predictions = test_probabilities.argmax(axis=1)
    per_class_values = f1_score(y, oof_predictions, average=None)
    per_class_f1 = {
        label: float(score)
        for label, score in zip(CLASS_LABELS, per_class_values, strict=True)
    }
    oof_macro_f1 = float(f1_score(y, oof_predictions, average="macro"))
    fold_scores = [float(item["macro_f1"]) for item in fold_metrics]

    oof_probability_path = oof_dir / "oof_probabilities.npy"
    test_probability_path = prediction_dir / "test_probabilities.npy"
    oof_prediction_path = oof_dir / "oof_predictions.csv"
    test_probability_csv_path = prediction_dir / "test_probabilities.csv"
    class_f1_path = report_dir / "class_f1.csv"
    metrics_path = report_dir / "metrics.json"
    resolved_config_path = reproduction_dir / "config.resolved.yaml"

    np.save(oof_probability_path, oof_probabilities)
    np.save(test_probability_path, test_probabilities)
    pd.DataFrame(
        {
            "ID": train["ID"],
            "true": train["SUBCLASS"],
            "pred": [CLASS_LABELS[index] for index in oof_predictions],
            "fold": fold_ids,
        }
    ).to_csv(oof_prediction_path, index=False, lineterminator="\n")
    test_probability_frame = pd.DataFrame(
        test_probabilities,
        columns=PROBABILITY_COLUMNS,
    )
    test_probability_frame.insert(0, "ID", test["ID"])
    test_probability_frame.to_csv(
        test_probability_csv_path,
        index=False,
        lineterminator="\n",
    )
    pd.DataFrame(
        {
            "class": CLASS_LABELS,
            "f1": per_class_values,
        }
    ).sort_values("f1").to_csv(class_f1_path, index=False, lineterminator="\n")
    pd.DataFrame(
        {
            "ID": test["ID"],
            "SUBCLASS": [CLASS_LABELS[index] for index in test_predictions],
        }
    ).to_csv(submission_path, index=False, lineterminator="\n")
    submission_summary = validate_submission(submission_path, data_paths["test_path"])

    finished_at = _utc_now()
    owner = _git_output("config", "user.name") or "unknown"
    split_sha256 = sha256_file(data_paths["split_path"])
    metrics: dict[str, Any] = {
        "experiment_id": context.experiment_id,
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": context.issue_number,
        "parent_experiment": None,
        "git_commit": git_commit,
        "started_at": started_at,
        "finished_at": finished_at,
        "primary_metric": "macro_f1",
        "split_id": f"stratified_5fold_seed42:{split_sha256}",
        "folds": [
            {
                key: value
                for key, value in item.items()
                if key in {"fold", "macro_f1", "accuracy", "log_loss", "best_iteration"}
            }
            for item in fold_metrics
        ],
        "oof": {
            "macro_f1": oof_macro_f1,
            "fold_mean": float(np.mean(fold_scores)),
            "fold_std": float(np.std(fold_scores)),
            "accuracy": float(accuracy_score(y, oof_predictions)),
            "log_loss": float(
                log_loss(y, oof_probabilities, labels=np.arange(len(CLASS_LABELS)))
            ),
            "per_class_f1": per_class_f1,
            "confusion_matrix": confusion_matrix(y, oof_predictions).tolist(),
        },
        "leaderboard": None,
        "runtime": {
            "seconds": float(time.perf_counter() - runtime_started),
            "hardware": platform.platform(),
        },
        "artifacts": {
            "config": _relative(resolved_config_path),
            "oof_predictions": _relative(oof_prediction_path),
            "oof_probabilities": _relative(oof_probability_path),
            "test_probabilities": _relative(test_probability_path),
            "submission": _relative(submission_path),
            "class_f1": _relative(class_f1_path),
            "models": _relative(model_dir),
        },
        "notes": (
            "순수 mutation-presence, mutation burden와 class weight 미사용. "
            + (
                f"유전자 화이트리스트 적용: {gene_selection_manifest['gene_count']}개 "
                f"(원본 경로 라이선스 제한으로 미커밋, config.resolved.yaml의 "
                f"feature_manifest.gene_selection 참고, "
                f"gene_order_sha256={gene_selection_manifest['gene_order_sha256']})"
                if gene_whitelist_path_value
                else f"전체 {gene_selection_manifest['gene_count']}개 유전자 컬럼 사용"
            )
        ),
    }

    resolved_config: dict[str, Any] = {
        **config,
        "identity": {
            "experiment_id": context.experiment_id,
            "issue_number": context.issue_number,
            "branch": context.branch,
            "owner": owner,
            "git_commit": git_commit,
            "dirty_worktree_at_start": dirty_worktree,
            "started_at": started_at,
            "finished_at": finished_at,
        },
        "data_manifest": {
            **data_summary,
            "split": {
                "path": _relative(data_paths["split_path"]),
                "sha256": split_sha256,
                "n_splits": n_splits,
                "fold_counts": {
                    str(key): int(value)
                    for key, value in fold_table["fold"].value_counts().sort_index().items()
                },
            },
        },
        "feature_manifest": {
            "matrix_shape_train": list(x_train.shape),
            "matrix_shape_test": list(x_test.shape),
            "train_nonzero": int(x_train.nnz),
            "test_nonzero": int(x_test.nnz),
            "class_order": list(CLASS_LABELS),
            "gene_selection": gene_selection_manifest,
        },
        "environment": {
            "os": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
            "xgboost": xgb.__version__,
            "pythonhashseed": python_hash_seed,
            "uv_lock_sha256": sha256_file(PROJECT_ROOT / "uv.lock"),
        },
        "resolved_model_params": {
            **model_params,
            "fold_seeds": [seed + fold for fold in range(n_splits)],
            "use_balanced_sample_weight": use_balanced_weight,
            "best_iterations": [item["best_iteration"] for item in fold_metrics],
        },
        "command": {
            "train": (
                f"PYTHONHASHSEED={seed} uv run python "
                f"scripts/run_xgb_baseline.py --config {_relative(config_path)}"
            )
        },
        "outputs": {
            **metrics["artifacts"],
            "test_probability_csv": _relative(test_probability_csv_path),
            "metrics": _relative(metrics_path),
            "submission_sha256": submission_summary["sha256"],
            "checkpoints": [_relative(path) for path in checkpoint_paths],
        },
    }
    resolved_config_path.write_text(
        yaml.safe_dump(resolved_config, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    _write_json(metrics_path, metrics)
    validate_json_document(
        metrics_path,
        PROJECT_ROOT / "schemas" / "experiment_metrics.schema.json",
    )

    print(
        json.dumps(
            {
                "experiment_id": context.experiment_id,
                "oof_macro_f1": oof_macro_f1,
                "fold_macro_f1": fold_scores,
                "submission": _relative(submission_path),
                "submission_sha256": submission_summary["sha256"],
                "metrics": _relative(metrics_path),
                "resolved_config": _relative(resolved_config_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
