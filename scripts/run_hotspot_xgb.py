#!/usr/bin/env python
"""Run a config-driven XGBoost experiment with fixed literature hotspots.

The 15 additions come from scripts/explore_hotspot_candidate_mining.py, which
scans the full EXP-012 COSMIC protect-gene whitelist (361 genes) for
positions with a single consistent reference amino acid and enough evidence
after excluding "artifact cluster" occurrences (same-gene position-sets that
recur identically far too often to be real tumor biology -- see
reports/exp012_feature_analysis/hotspot_artifact_clusters.csv). Out of the
482 positions that passed those automated filters, only individually
well-established literature hotspots were kept by hand (PIK3CA E542K/Q546/
N345, PTEN R130/R233, FBXW7 R505, AKT1 E17K, U2AF1 S34, APC R1450/R876,
POLE P286R/V411L, KIT D816, FGFR3 S249C, RAC1 P29S). Ambiguous or
non-driver-gene candidates (HLA-A polymorphism, PABPC1, SIRPA, ATP1A1, the
~50-codon TP53 extension, KMT2D, PLEC, ...) were deliberately left out.
"""

from __future__ import annotations

import json
import argparse
import os
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
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
)
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.hashing import sha256_file
from open_cancer.mutation_features import (
    resolve_position_features_from_config,
    resolve_position_options_from_config,
)
from open_cancer.paths import relative_posix
from open_cancer.hotspot_features import (
    build_hotspot_augmented_features,
    resolve_hotspot_config,
    validate_hotspot_train_evidence,
)
from open_cancer.mutation_features import (
    resolve_position_features_from_config,
    resolve_position_options_from_config,
)
from open_cancer.validation import validate_json_document, validate_submission
from run_exp005_xgb_mutation_features import verify_saved_inference, write_local_dashboard


ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
SAMPLE_SUBMISSION_PATH = ROOT / "data" / "raw" / "sample_submission.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def run_git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(
    config_override: Path | None = None,
    *,
    fold_feature_builder: Any | None = None,
) -> None:
    args = parse_args() if config_override is None else None
    started_at = datetime.now(timezone.utc)
    start_time = time.perf_counter()
    config_path = (args.config if args is not None else config_override).resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)

    artifact_slug = f"exp{context.issue_number:03d}_{config['slug']}"
    split_path = ROOT / config["split"]["path"]
    report_dir = ROOT / "reports" / artifact_slug
    model_dir = ROOT / "models" / artifact_slug
    oof_path = ROOT / "oof" / f"{artifact_slug}.csv"
    test_probability_path = ROOT / "preds" / f"{artifact_slug}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{artifact_slug}.csv"
    reproducibility_dir = ROOT / "reproducibility" / artifact_slug
    feature_dir = ROOT / "data" / "processed" / f"{artifact_slug}_features"
    resolved_config_path = reproducibility_dir / "config.resolved.yaml"
    metrics_path = report_dir / "metrics.json"
    for directory in (
        report_dir,
        model_dir,
        oof_path.parent,
        test_probability_path.parent,
        submission_path.parent,
        reproducibility_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    source_commit = run_git("rev-parse", "HEAD")
    dirty_worktree = bool(run_git("status", "--porcelain"))
    if dirty_worktree:
        raise RuntimeError(
            "공식 실험은 clean worktree에서만 실행할 수 있습니다. "
            "코드와 config를 먼저 commit한 뒤 다시 실행하세요."
        )
    owner = run_git("config", "user.name") or os.environ.get("USER", "unknown")
    hotspot_config = config.get("hotspots", {})
    hotspots, evidence_hotspots, minimum_matching_rows = resolve_hotspot_config(hotspot_config)
    selected_position_features = resolve_position_features_from_config(config)
    position_options = resolve_position_options_from_config(config)
    selected_robust_aggregates = tuple(
        config.get("features", {}).get("robust_aggregates", [])
    )
    feature_report = build_hotspot_augmented_features(
        TRAIN_PATH,
        TEST_PATH,
        feature_dir,
        hotspots=hotspots,
        base_feature_options={
            "selected_robust_aggregates": selected_robust_aggregates,
            "selected_position_features": selected_position_features,
            **position_options,
        },
    )
    base_dir = Path(feature_report["base_dir"])

    train_meta = pd.read_csv(TRAIN_PATH, usecols=["ID", "SUBCLASS"], dtype=str)
    test_meta = pd.read_csv(TEST_PATH, usecols=["ID"], dtype=str)
    sample_submission = pd.read_csv(SAMPLE_SUBMISSION_PATH, dtype=str, keep_default_na=False)
    folds = pd.read_csv(split_path, dtype={"ID": str, "fold": int})
    train = train_meta.merge(folds, on="ID", how="left", validate="one_to_one", sort=False)
    if not train["ID"].equals(train_meta["ID"]):
        raise ValueError("fold 병합 과정에서 train 순서가 변경됐습니다.")
    if train["fold"].isna().any():
        raise ValueError("공용 split에 없는 train ID가 있습니다.")

    fold_hotspot_train_evidence: dict[str, list[dict[str, object]]] = {}
    for fold in range(config["split"]["n_splits"]):
        fold_train_indices = set(np.flatnonzero(~train["fold"].eq(fold).to_numpy()).tolist())
        fold_hotspot_train_evidence[str(fold)] = validate_hotspot_train_evidence(
            TRAIN_PATH,
            gene_start_column=2,
            hotspots=evidence_hotspots,
            minimum_matching_rows=minimum_matching_rows,
            include_row_indices=fold_train_indices,
        )

    x_all = sparse.load_npz(feature_dir / "train_features.npz")
    x_test = sparse.load_npz(feature_dir / "test_features.npz")
    all_feature_names = tuple(
        json.loads((feature_dir / "feature_names.json").read_text(encoding="utf-8"))
    )
    feature_train_ids = pd.read_csv(base_dir / "train_ids.csv", dtype=str)["ID"]
    feature_test_ids = pd.read_csv(base_dir / "test_ids.csv", dtype=str)["ID"]
    if not feature_train_ids.equals(train["ID"]) or not feature_test_ids.equals(test_meta["ID"]):
        raise ValueError("피처 행렬 ID 순서가 원본과 다릅니다.")

    label_encoder = LabelEncoder().fit(list(CLASS_LABELS))
    if list(label_encoder.classes_) != list(CLASS_LABELS):
        raise ValueError("고정 클래스 순서와 LabelEncoder 순서가 다릅니다.")
    y = label_encoder.transform(train["SUBCLASS"]).astype(np.int32)

    model_params = {
        **config["model"],
        "num_class": len(CLASS_LABELS),
    }
    resolved_config = {
        "experiment": {
            "record_role": config["record_role"],
            "issue_number": context.issue_number,
            "experiment_id": context.experiment_id,
            "component_experiments": config.get("component_experiments", []),
            "branch": context.branch,
            "owner": owner,
            "source_commit": source_commit,
            "dirty_worktree": dirty_worktree,
            "started_at": started_at.isoformat(),
        },
        "data": {
            "train": {"path": relative_posix(TRAIN_PATH, ROOT), "sha256": sha256_file(TRAIN_PATH)},
            "test": {"path": relative_posix(TEST_PATH, ROOT), "sha256": sha256_file(TEST_PATH)},
            "sample_submission": {
                "path": relative_posix(SAMPLE_SUBMISSION_PATH, ROOT),
                "sha256": sha256_file(SAMPLE_SUBMISSION_PATH),
            },
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
            "requested_families": config.get("features", {}),
            "hotspot_table": hotspot_config.get("table", "extended_34"),
            "hotspot_evidence_scope": hotspot_config.get(
                "evidence_scope", "additions_15"
            ),
            "fold_train_hotspot_evidence": fold_hotspot_train_evidence,
            "minimum_matching_train_rows": minimum_matching_rows,
            "selection_uses_test_data": False,
        },
        "feature_outputs": {
            name: {
                **metadata,
                "path": relative_posix(Path(metadata["path"]), ROOT),
            }
            for name, metadata in feature_report["outputs"].items()
        },
        "model": {
            "class": "xgboost.XGBClassifier",
            "parameters": model_params,
        },
        "training": {
            **config["training"],
            "fold_seeds": [config["seed"] + fold for fold in range(config["split"]["n_splits"])],
            "command": (
                "uv run python scripts/run_hotspot_xgb.py --config "
                f"{relative_posix(config_path, ROOT)}"
            ),
        },
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
    reproducibility_dir.mkdir(parents=True, exist_ok=True)
    resolved_config_path.write_text(
        yaml.safe_dump(resolved_config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    n_splits = config["split"]["n_splits"]
    oof_proba = np.full((len(train), len(CLASS_LABELS)), np.nan, dtype=np.float32)
    test_proba = np.zeros((len(test_meta), len(CLASS_LABELS)), dtype=np.float32)
    fold_metrics: list[dict[str, Any]] = []
    fold_test_matrices: list[sparse.csr_matrix] = []
    fold_feature_records: list[dict[str, Any]] = []

    for fold in range(n_splits):
        valid_mask = train["fold"].eq(fold).to_numpy()
        train_indices = np.flatnonzero(~valid_mask)
        valid_indices = np.flatnonzero(valid_mask)
        y_train = y[train_indices]
        y_valid = y[valid_indices]
        x_train_fold = x_all[train_indices]
        x_valid_fold = x_all[valid_indices]
        x_test_fold = x_test
        if fold_feature_builder is not None:
            extra = fold_feature_builder(
                fold=fold,
                train_indices=train_indices,
                valid_indices=valid_indices,
                base_train=x_train_fold,
                base_validation=x_valid_fold,
                base_test=x_test_fold,
                base_feature_names=all_feature_names,
                target=y_train,
            )
            x_train_fold = sparse.hstack(
                [x_train_fold, extra.train], format="csr", dtype=np.float32
            )
            x_valid_fold = sparse.hstack(
                [x_valid_fold, extra.validation], format="csr", dtype=np.float32
            )
            x_test_fold = sparse.hstack(
                [x_test_fold, extra.test], format="csr", dtype=np.float32
            )
            fold_test_matrices.append(x_test_fold)
            fold_feature_records.append(
                {
                    "fold": fold,
                    "feature_names": list(extra.feature_names),
                    "registry": extra.registry,
                }
            )
        sample_weight = (
            compute_sample_weight(class_weight="balanced", y=y_train)
            if config["training"]["balanced_sample_weight"]
            else None
        )
        model = xgb.XGBClassifier(
            **model_params,
            random_state=config["seed"] + fold,
        )
        model.fit(
            x_train_fold,
            y_train,
            sample_weight=sample_weight,
            eval_set=[(x_valid_fold, y_valid)],
            verbose=False,
        )
        valid_proba = model.predict_proba(x_valid_fold).astype(np.float32)
        fold_test_proba = model.predict_proba(x_test_fold).astype(np.float32)
        oof_proba[valid_indices] = valid_proba
        test_proba += fold_test_proba / n_splits
        valid_pred = valid_proba.argmax(axis=1)
        best_iteration = getattr(model, "best_iteration", None)
        result = {
            "fold": fold,
            "macro_f1": float(f1_score(y_valid, valid_pred, average="macro")),
            "accuracy": float(accuracy_score(y_valid, valid_pred)),
            "log_loss": float(log_loss(y_valid, valid_proba, labels=np.arange(len(CLASS_LABELS)))),
            "best_iteration": None if best_iteration is None else int(best_iteration),
        }
        fold_metrics.append(result)
        model.save_model(model_dir / f"fold_{fold:02d}.json")
        print(json.dumps(result, ensure_ascii=False))

    if np.isnan(oof_proba).any():
        raise ValueError("OOF 확률에 채워지지 않은 값이 있습니다.")
    if fold_feature_builder is not None:
        resolved_config["fold_train_features"] = fold_feature_records
        resolved_config_path.write_text(
            yaml.safe_dump(resolved_config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    oof_pred = oof_proba.argmax(axis=1)
    test_pred = test_proba.argmax(axis=1)
    report = classification_report(
        y,
        oof_pred,
        labels=np.arange(len(CLASS_LABELS)),
        target_names=CLASS_LABELS,
        output_dict=True,
        zero_division=0,
    )
    fold_scores = np.asarray([item["macro_f1"] for item in fold_metrics])
    finished_at = datetime.now(timezone.utc)

    oof_frame = pd.DataFrame(
        {
            "ID": train["ID"],
            "SUBCLASS_TRUE": train["SUBCLASS"],
            "SUBCLASS_PRED": label_encoder.inverse_transform(oof_pred),
            "FOLD": train["fold"].astype(int),
        }
    )
    oof_frame.loc[:, list(PROBABILITY_COLUMNS)] = oof_proba
    oof_frame.to_csv(oof_path, index=False, lineterminator="\n")

    test_probability_frame = pd.DataFrame({"ID": test_meta["ID"]})
    test_probability_frame.loc[:, list(PROBABILITY_COLUMNS)] = test_proba
    test_probability_frame.to_csv(test_probability_path, index=False, lineterminator="\n")

    submission = sample_submission.copy()
    submission["SUBCLASS"] = label_encoder.inverse_transform(test_pred)
    submission.to_csv(submission_path, index=False, lineterminator="\n")
    submission_validation = validate_submission(submission_path, TEST_PATH)

    metrics = {
        "experiment_id": context.experiment_id,
        "record_role": config["record_role"],
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": context.issue_number,
        "parent_experiment": config.get("parent_experiment", "EXP-005"),
        "git_commit": source_commit,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "primary_metric": "macro_f1",
        "split_id": relative_posix(split_path, ROOT),
        "folds": fold_metrics,
        "oof": {
            "macro_f1": float(f1_score(y, oof_pred, average="macro")),
            "fold_mean": float(fold_scores.mean()),
            "fold_std": float(fold_scores.std()),
            "accuracy": float(accuracy_score(y, oof_pred)),
            "log_loss": float(log_loss(y, oof_proba, labels=np.arange(len(CLASS_LABELS)))),
            "per_class_f1": {
                label: float(report[label]["f1-score"]) for label in CLASS_LABELS
            },
            "confusion_matrix": confusion_matrix(
                y,
                oof_pred,
                labels=np.arange(len(CLASS_LABELS)),
            ).tolist(),
        },
        "leaderboard": None,
        "runtime": {
            "seconds": float(time.perf_counter() - start_time),
            "hardware": platform.platform(),
        },
        "artifacts": {
            "resolved_config": relative_posix(resolved_config_path, ROOT),
            "oof": relative_posix(oof_path, ROOT),
            "test_probability": relative_posix(test_probability_path, ROOT),
            "submission": relative_posix(submission_path, ROOT),
            "models": relative_posix(model_dir, ROOT),
            "submission_sha256": submission_validation["sha256"],
        },
        "notes": config.get(
            "notes",
            "EXP-005 mutation-type features plus fixed 34 literature hotspots "
            "with reference-amino-acid matching and train-only evidence checks.",
        ),
    }
    write_json(metrics_path, metrics)
    validate_json_document(metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json")
    local_dashboard_path = write_local_dashboard(
        artifact_slug=artifact_slug,
        metrics=metrics,
        feature_dir=feature_dir,
        highlighted_features=("hotspot__known_hotspot_total_count",),
        comparison_metrics_path=(
            ROOT / config["comparison_metrics_path"]
            if config.get("comparison_metrics_path")
            else None
        ),
    )
    verify_saved_inference(
        context=context,
        source_commit=source_commit,
        owner=owner,
        artifact_slug=artifact_slug,
        config=config,
        resolved_config=resolved_config,
        resolved_config_path=resolved_config_path,
        metrics=metrics,
        metrics_path=metrics_path,
        model_dir=model_dir,
        oof_path=oof_path,
        reproducibility_dir=reproducibility_dir,
        test_features=x_test,
        test_ids=test_meta["ID"],
        test_probability_path=test_probability_path,
        submission_path=submission_path,
        fold_test_features=(
            fold_test_matrices if fold_feature_builder is not None else None
        ),
    )
    print(
        json.dumps(
            {
                "metrics": str(metrics_path),
                "local_dashboard": str(local_dashboard_path),
                "oof": metrics["oof"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
