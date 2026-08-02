#!/usr/bin/env python
"""Run EXP-160: fold-safe permutation negative control for max_residue_position.

Contract (Issue #80 follow-up, PROJECT_CONTEXT.md Feature Factory operating
rules): shuffle `{gene}__max_residue_position` values only within each outer
fold's TRAIN partition, only among samples that already carry a non-zero
position for that gene, grouped by that gene's mutation-type indicator
signature where possible. Validation-fold positions and all other features
stay untouched. Test is not used. Model hyperparameters and the per-fold
model random_state are identical to EXP-069 so the permutation seed is the
only thing that varies across repeats.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
import xgboost as xgb
import yaml
from scipy import sparse
from sklearn.metrics import accuracy_score, f1_score, log_loss
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.constants import CLASS_LABELS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.hashing import sha256_file
from open_cancer.mutation_features import (
    build_mutation_features,
    resolve_position_features_from_config,
    resolve_position_options_from_config,
)
from open_cancer.paths import relative_posix
from open_cancer.validation import validate_json_document

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "exp160_residue_position_negative_control.yaml"
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
FEATURE_DIR = (
    ROOT / "data" / "processed" / "feature_factory" / "v1" / "exp069_max_residue_position"
)
ARTIFACT_SLUG = "exp160_residue_position_negative_control"
EXPECTED_ISSUE_NUMBER = 160
BASELINE_METRICS_PATH = ROOT / "reports" / "exp069_xgb_max_residue_position" / "metrics.json"
STRATA_TYPES: tuple[str, ...] = (
    "missense",
    "synonymous",
    "nonsense",
    "frameshift",
    "complex",
)


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


def build_strata_block(
    matrix: sparse.csr_matrix, genes: list[str], name_to_index: dict[str, int]
) -> np.ndarray:
    """Return a (n_rows, n_genes) uint8 array of mutation-type bit signatures."""

    strata = np.zeros((matrix.shape[0], len(genes)), dtype=np.uint8)
    for bit, type_name in enumerate(STRATA_TYPES):
        indices = np.array([name_to_index[f"{gene}__{type_name}"] for gene in genes])
        block = np.asarray(matrix[:, indices].todense()) > 0
        strata |= block.astype(np.uint8) << bit
    return strata


def permute_position_block(
    position_block: np.ndarray,
    strata_block: np.ndarray,
    train_mask: np.ndarray,
    seed: int,
) -> np.ndarray:
    """Fold-safe, gene-wise, strata-aware permutation of one condition."""

    rng = np.random.default_rng(seed)
    permuted = position_block.copy()
    n_genes = position_block.shape[1]
    for gene_index in range(n_genes):
        column = position_block[:, gene_index]
        eligible = np.flatnonzero((column != 0) & train_mask)
        if eligible.size < 2:
            continue
        strata_column = strata_block[eligible, gene_index]
        for key in np.unique(strata_column):
            group = eligible[strata_column == key]
            if group.size < 2:
                continue
            permuted[group, gene_index] = rng.permutation(column[group])
    return permuted


def set_dense_columns(
    matrix: sparse.csr_matrix, indices: np.ndarray, values: np.ndarray
) -> sparse.csr_matrix:
    """Return a copy of matrix with the given columns replaced by dense values."""

    lil = matrix.tolil(copy=True)
    lil[:, indices] = values
    return lil.tocsr()


def main() -> None:
    started_at = datetime.now(timezone.utc)
    start_time = time.perf_counter()
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    expected_experiment_id = f"EXP-{EXPECTED_ISSUE_NUMBER:03d}"
    if (
        context.experiment_id != expected_experiment_id
        or context.issue_number != EXPECTED_ISSUE_NUMBER
    ):
        raise ValueError(
            f"이 script는 Issue #{EXPECTED_ISSUE_NUMBER} 브랜치의 "
            f"{expected_experiment_id} 전용입니다."
        )

    source_commit = run_git("rev-parse", "HEAD")
    dirty_status = run_git("status", "--porcelain")
    if dirty_status:
        raise RuntimeError(
            "공식 실험은 clean worktree에서만 실행할 수 있습니다.\n" + dirty_status
        )
    owner = run_git("config", "user.name") or "unknown"

    selected_position_features = resolve_position_features_from_config(config)
    position_options = resolve_position_options_from_config(config)
    feature_report = build_mutation_features(
        TRAIN_PATH,
        TEST_PATH,
        FEATURE_DIR,
        include_robust_aggregates=False,
        selected_position_features=selected_position_features,
        **position_options,
    )

    with TRAIN_PATH.open("r", encoding="utf-8", newline="") as file:
        import csv

        genes = next(csv.reader(file))[2:]

    split_path = ROOT / config["split"]["path"]
    train_meta = pd.read_csv(TRAIN_PATH, usecols=["ID", "SUBCLASS"], dtype=str)
    folds = pd.read_csv(split_path, dtype={"ID": str, "fold": int})
    train = train_meta.merge(folds, on="ID", how="left", validate="one_to_one", sort=False)
    if not train["ID"].equals(train_meta["ID"]):
        raise ValueError("fold 병합 과정에서 train 순서가 변경됐습니다.")

    x_all = sparse.load_npz(FEATURE_DIR / "train_features.npz")
    all_feature_names: list[str] = json.loads(
        (FEATURE_DIR / "feature_names.json").read_text(encoding="utf-8")
    )
    feature_train_ids = pd.read_csv(FEATURE_DIR / "train_ids.csv", dtype=str)["ID"]
    if not feature_train_ids.equals(train["ID"]):
        raise ValueError("피처 행렬 ID 순서가 원본과 다릅니다.")

    label_encoder = LabelEncoder().fit(list(CLASS_LABELS))
    if list(label_encoder.classes_) != list(CLASS_LABELS):
        raise ValueError("고정 클래스 순서와 LabelEncoder 순서가 다릅니다.")
    y = label_encoder.transform(train["SUBCLASS"]).astype(np.int32)

    name_to_index = {name: index for index, name in enumerate(all_feature_names)}
    target_feature = config["negative_control"]["target_feature"]
    pos_idx = np.array([name_to_index[f"{gene}__{target_feature}"] for gene in genes])
    position_block = np.asarray(x_all[:, pos_idx].todense(), dtype=np.float32)
    strata_block = build_strata_block(x_all, genes, name_to_index)

    n_splits = config["split"]["n_splits"]
    model_seed_base = config["negative_control"]["model_seed_base"]
    permutation_seeds: list[int] = config["negative_control"]["permutation_seeds"]
    model_params = {**config["model"], "num_class": len(CLASS_LABELS)}

    baseline = json.loads(BASELINE_METRICS_PATH.read_text(encoding="utf-8"))
    baseline_fold_scores = [item["macro_f1"] for item in baseline["folds"]]

    per_seed_results: list[dict[str, Any]] = []
    fold_matrix = np.zeros((len(permutation_seeds), n_splits), dtype=np.float64)

    for seed_position, permutation_seed in enumerate(permutation_seeds):
        oof_proba = np.full((len(train), len(CLASS_LABELS)), np.nan, dtype=np.float32)
        fold_scores: list[dict[str, Any]] = []
        for fold in range(n_splits):
            valid_mask = train["fold"].eq(fold).to_numpy()
            train_mask = ~valid_mask
            train_indices = np.flatnonzero(train_mask)
            valid_indices = np.flatnonzero(valid_mask)
            y_train = y[train_indices]
            y_valid = y[valid_indices]

            fold_permutation_seed = permutation_seed * 100 + fold
            permuted_block = permute_position_block(
                position_block, strata_block, train_mask, fold_permutation_seed
            )

            x_train_fold = set_dense_columns(
                x_all[train_indices], pos_idx, permuted_block[train_indices]
            )
            x_valid_fold = x_all[valid_indices]

            sample_weight = (
                compute_sample_weight(class_weight="balanced", y=y_train)
                if config["training"]["balanced_sample_weight"]
                else None
            )
            model = xgb.XGBClassifier(
                **model_params, random_state=model_seed_base + fold
            )
            model.fit(
                x_train_fold,
                y_train,
                sample_weight=sample_weight,
                eval_set=[(x_valid_fold, y_valid)],
                verbose=False,
            )
            valid_proba = model.predict_proba(x_valid_fold).astype(np.float32)
            oof_proba[valid_indices] = valid_proba
            valid_pred = valid_proba.argmax(axis=1)
            best_iteration = getattr(model, "best_iteration", None)
            result = {
                "fold": fold,
                "macro_f1": float(f1_score(y_valid, valid_pred, average="macro")),
                "accuracy": float(accuracy_score(y_valid, valid_pred)),
                "log_loss": float(
                    log_loss(y_valid, valid_proba, labels=np.arange(len(CLASS_LABELS)))
                ),
                "best_iteration": None if best_iteration is None else int(best_iteration),
            }
            fold_scores.append(result)
            fold_matrix[seed_position, fold] = result["macro_f1"]
            print(
                json.dumps(
                    {"permutation_seed": permutation_seed, **result}, ensure_ascii=False
                )
            )

        if np.isnan(oof_proba).any():
            raise ValueError("OOF 확률에 채워지지 않은 값이 있습니다.")
        oof_pred = oof_proba.argmax(axis=1)
        seed_oof_macro_f1 = float(f1_score(y, oof_pred, average="macro"))
        per_seed_results.append(
            {
                "permutation_seed": permutation_seed,
                "fold_macro_f1": [item["macro_f1"] for item in fold_scores],
                "fold_accuracy": [item["accuracy"] for item in fold_scores],
                "fold_log_loss": [item["log_loss"] for item in fold_scores],
                "oof_macro_f1": seed_oof_macro_f1,
                "fold_std": float(np.std([item["macro_f1"] for item in fold_scores])),
            }
        )

    finished_at = datetime.now(timezone.utc)

    per_fold_summary = []
    for fold in range(n_splits):
        permuted_scores = fold_matrix[:, fold]
        per_fold_summary.append(
            {
                "fold": fold,
                "baseline_macro_f1": baseline_fold_scores[fold],
                "permuted_mean_macro_f1": float(permuted_scores.mean()),
                "permuted_std_across_seeds": float(permuted_scores.std()),
                "delta_mean_vs_baseline": float(
                    permuted_scores.mean() - baseline_fold_scores[fold]
                ),
            }
        )

    permuted_oof_scores = np.array([item["oof_macro_f1"] for item in per_seed_results])
    overall = {
        "baseline_oof_macro_f1": baseline["oof"]["macro_f1"],
        "baseline_fold_std": baseline["oof"]["fold_std"],
        "permuted_oof_macro_f1_mean": float(permuted_oof_scores.mean()),
        "permuted_oof_macro_f1_std": float(permuted_oof_scores.std()),
        "delta_mean_vs_baseline": float(
            permuted_oof_scores.mean() - baseline["oof"]["macro_f1"]
        ),
    }

    report_dir = ROOT / "reports" / ARTIFACT_SLUG
    reproducibility_dir = ROOT / "reproducibility" / ARTIFACT_SLUG
    resolved_config_path = reproducibility_dir / "config.resolved.yaml"
    metrics_path = report_dir / "metrics.json"
    detail_path = report_dir / "permutation_detail.json"
    for directory in (report_dir, reproducibility_dir):
        directory.mkdir(parents=True, exist_ok=True)

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
        "data": {
            "train": {"path": relative_posix(TRAIN_PATH, ROOT), "sha256": sha256_file(TRAIN_PATH)},
            "test": {"path": relative_posix(TEST_PATH, ROOT), "sha256": sha256_file(TEST_PATH)},
            "class_order": list(CLASS_LABELS),
        },
        "split": {
            **config["split"],
            "sha256": sha256_file(split_path),
            "method": "StratifiedKFold",
            "shuffle": True,
            "seed": config["seed"],
        },
        "features": {
            **feature_report["feature_contract"],
            "requested_families": config["features"],
        },
        "feature_outputs": {
            name: {**metadata, "path": relative_posix(Path(metadata["path"]), ROOT)}
            for name, metadata in feature_report["outputs"].items()
        },
        "model": {"class": "xgboost.XGBClassifier", "parameters": model_params},
        "training": config["training"],
        "negative_control": config["negative_control"],
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "xgboost": xgb.__version__,
            "uv_lock_sha256": sha256_file(ROOT / "uv.lock"),
        },
    }
    resolved_config_path.write_text(
        yaml.safe_dump(resolved_config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    detail = {
        "experiment_id": context.experiment_id,
        "baseline_source": relative_posix(BASELINE_METRICS_PATH, ROOT),
        "baseline_experiment_id": baseline["experiment_id"],
        "permutation_seeds": permutation_seeds,
        "model_seed_base": model_seed_base,
        "per_seed": per_seed_results,
        "per_fold_summary": per_fold_summary,
        "overall": overall,
    }
    write_json(detail_path, detail)

    mean_fold_macro_f1 = fold_matrix.mean(axis=0)
    folds_summary = [
        {
            "fold": fold,
            "macro_f1": float(mean_fold_macro_f1[fold]),
            "accuracy": float(
                np.mean([item["fold_accuracy"][fold] for item in per_seed_results])
            ),
            "log_loss": float(
                np.mean([item["fold_log_loss"][fold] for item in per_seed_results])
            ),
            "best_iteration": None,
        }
        for fold in range(n_splits)
    ]

    metrics = {
        "experiment_id": context.experiment_id,
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": context.issue_number,
        "parent_experiment": "EXP-069",
        "git_commit": source_commit,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "primary_metric": "macro_f1",
        "split_id": relative_posix(split_path, ROOT),
        "folds": folds_summary,
        "oof": {
            "macro_f1": overall["permuted_oof_macro_f1_mean"],
            "fold_mean": float(mean_fold_macro_f1.mean()),
            "fold_std": float(mean_fold_macro_f1.std()),
            "accuracy": float(
                np.mean([item["fold_accuracy"] for item in per_seed_results])
            ),
            "log_loss": float(
                np.mean([item["fold_log_loss"] for item in per_seed_results])
            ),
        },
        "leaderboard": None,
        "runtime": {
            "seconds": float(time.perf_counter() - start_time),
            "hardware": platform.platform(),
        },
        "artifacts": {
            "resolved_config": relative_posix(resolved_config_path, ROOT),
            "permutation_detail": relative_posix(detail_path, ROOT),
        },
        "notes": (
            "Fold-safe, gene-wise, mutation-type-stratified permutation of "
            "max_residue_position within each outer fold's train partition "
            "only (validation kept original, test unused), repeated over 5 "
            "permutation seeds with the EXP-069 model random_state held "
            "fixed per fold. 'oof.macro_f1' and per-fold scores above are "
            "means across the 5 permutation seeds; see permutation_detail.json "
            "for the full per-seed, per-fold breakdown and the paired "
            "comparison against the EXP-069 baseline."
        ),
    }
    write_json(metrics_path, metrics)
    validate_json_document(metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json")

    print(json.dumps({"overall": overall}, ensure_ascii=False, indent=2))
    print(json.dumps({"per_fold_summary": per_fold_summary}, ensure_ascii=False, indent=2))
    print(json.dumps({"metrics": str(metrics_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
