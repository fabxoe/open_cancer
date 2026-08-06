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
from open_cancer.checkpoint_selection import (
    audit_xgboost_validation_iterations,
    predict_xgboost_at_iteration,
    save_xgboost_iteration_checkpoint,
)
from open_cancer.experiment import resolve_experiment_context
from open_cancer.hashing import sha256_file, sha256_lines
from open_cancer.feature_family import drop_named_base_features
from open_cancer.mutation_features import (
    resolve_position_features_from_config,
    resolve_position_options_from_config,
)
from open_cancer.isoform_position_mask import (
    resolve_isoform_position_mask_from_config,
)
from open_cancer.isoform_relative_position import (
    resolve_isoform_relative_position_from_config,
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
    fold_model_tuner: Any | None = None,
    runner_command: str | None = None,
    prevalidated_source_commit: str | None = None,
    mutation_cell_parser: Any | None = None,
    mutation_parser_contract: dict[str, Any] | None = None,
    hotspot_token_normalizer: Any | None = None,
    fold_sample_weight_multiplier: Any | None = None,
    model_class_labels: tuple[str, ...] | None = None,
    target_aliases: dict[str, str] | None = None,
) -> None:
    args = parse_args() if config_override is None else None
    started_at = datetime.now(timezone.utc)
    start_time = time.perf_counter()
    config_path = (args.config if args is not None else config_override).resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    active_class_labels = tuple(model_class_labels or CLASS_LABELS)
    aliases = dict(target_aliases or {})
    if len(active_class_labels) != len(set(active_class_labels)):
        raise ValueError("모델 클래스 순서에 중복 라벨이 있습니다.")
    if not set(active_class_labels) <= set(CLASS_LABELS):
        raise ValueError("모델 클래스는 대회 고정 26개 라벨의 부분집합이어야 합니다.")
    if not set(aliases) <= set(CLASS_LABELS) or not set(aliases.values()) <= set(
        active_class_labels
    ):
        raise ValueError("target alias가 고정 대회/모델 클래스 범위를 벗어났습니다.")
    active_probability_columns = tuple(
        f"PROBA_{label}" for label in active_class_labels
    )

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
    if prevalidated_source_commit is not None:
        if source_commit != prevalidated_source_commit:
            raise RuntimeError(
                "multi-run 도중 source commit이 변경됐습니다: "
                f"{prevalidated_source_commit} -> {source_commit}"
            )
        # The orchestrating runner checked a clean worktree before creating any
        # seed-specific artifacts. Later calls may see only those generated
        # outputs, while the committed source remains the prevalidated commit.
        dirty_worktree = False
    elif dirty_worktree:
        raise RuntimeError(
            "공식 실험은 clean worktree에서만 실행할 수 있습니다. "
            "코드와 config를 먼저 commit한 뒤 다시 실행하세요."
        )
    owner = run_git("config", "user.name") or os.environ.get("USER", "unknown")
    hotspot_config = config.get("hotspots", {})
    hotspots, evidence_hotspots, minimum_matching_rows = resolve_hotspot_config(hotspot_config)
    selected_position_features = resolve_position_features_from_config(config)
    position_options = resolve_position_options_from_config(config)
    position_token_filter, mask_semantic_contract = (
        resolve_isoform_position_mask_from_config(config, root=ROOT)
    )
    position_token_transformer, relative_semantic_contract = (
        resolve_isoform_relative_position_from_config(config, root=ROOT)
    )
    if mask_semantic_contract is not None and relative_semantic_contract is not None:
        raise ValueError("isoform semantic mask와 relative bin을 동시에 사용할 수 없습니다.")
    position_semantic_contract = (
        relative_semantic_contract or mask_semantic_contract
    )
    selected_robust_aggregates = tuple(
        config.get("features", {}).get("robust_aggregates", [])
    )
    parser_options: dict[str, Any] = {}
    if mutation_cell_parser is not None:
        parser_options = {
            "mutation_cell_parser": mutation_cell_parser,
            "mutation_parser_contract": mutation_parser_contract,
        }
    feature_report = build_hotspot_augmented_features(
        TRAIN_PATH,
        TEST_PATH,
        feature_dir,
        hotspots=hotspots,
        base_feature_options={
            "selected_robust_aggregates": selected_robust_aggregates,
            "selected_position_features": selected_position_features,
            "position_token_filter": position_token_filter,
            "position_token_transformer": position_token_transformer,
            "position_semantic_contract": position_semantic_contract,
            **parser_options,
            **position_options,
        },
        hotspot_token_normalizer=hotspot_token_normalizer,
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

    label_encoder = LabelEncoder().fit(list(active_class_labels))
    if list(label_encoder.classes_) != list(active_class_labels):
        raise ValueError("모델 클래스 순서와 LabelEncoder 순서가 다릅니다.")
    model_targets = train["SUBCLASS"].replace(aliases)
    if not set(model_targets.unique()) <= set(active_class_labels):
        raise ValueError("alias 적용 후에도 모델 클래스에 없는 target이 있습니다.")
    y = label_encoder.transform(model_targets).astype(np.int32)
    evaluation_encoder = LabelEncoder().fit(list(CLASS_LABELS))
    y_evaluation = evaluation_encoder.transform(train["SUBCLASS"]).astype(np.int32)
    model_to_evaluation = evaluation_encoder.transform(active_class_labels).astype(
        np.int32
    )

    model_params = {
        **config["model"],
        "num_class": len(active_class_labels),
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
            "model_class_order": list(active_class_labels),
            "target_aliases": aliases,
            "evaluation_class_order": list(CLASS_LABELS),
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
                runner_command
                or (
                    "uv run python scripts/run_hotspot_xgb.py --config "
                    f"{relative_posix(config_path, ROOT)}"
                )
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
    oof_proba = np.full(
        (len(train), len(active_class_labels)), np.nan, dtype=np.float32
    )
    test_proba = np.zeros(
        (len(test_meta), len(active_class_labels)), dtype=np.float32
    )
    fold_metrics: list[dict[str, Any]] = []
    fold_test_matrices: list[sparse.csr_matrix] = []
    fold_feature_records: list[dict[str, Any]] = []
    fold_tuning_records: list[dict[str, Any]] = []
    fold_sample_weight_records: list[dict[str, Any]] = []
    tuning_artifact_paths: list[Path] = []
    checkpoint_selection = config["training"].get(
        "checkpoint_selection", "training_metric"
    )
    validation_checkpoint_policies = {
        "macro_f1_validation",
        "macro_f1_rolling_median_validation",
    }
    if checkpoint_selection not in {"training_metric", *validation_checkpoint_policies}:
        raise ValueError(f"지원하지 않는 checkpoint selection: {checkpoint_selection}")
    training_metric_oof = (
        np.full((len(train), len(active_class_labels)), np.nan, dtype=np.float32)
        if checkpoint_selection in validation_checkpoint_policies
        else None
    )
    checkpoint_audit_paths: list[Path] = []

    for fold in range(n_splits):
        valid_mask = train["fold"].eq(fold).to_numpy()
        train_indices = np.flatnonzero(~valid_mask)
        valid_indices = np.flatnonzero(valid_mask)
        y_train = y[train_indices]
        y_valid = y[valid_indices]
        y_valid_evaluation = y_evaluation[valid_indices]
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
            (
                x_train_fold,
                x_valid_fold,
                x_test_fold,
                kept_base_feature_names,
            ) = drop_named_base_features(
                x_train_fold,
                x_valid_fold,
                x_test_fold,
                all_feature_names,
                extra.base_feature_names_to_drop,
                allow_empty=bool(extra.feature_names),
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
                    "feature_name_count": len(extra.feature_names),
                    "feature_names_sha256": sha256_lines(extra.feature_names),
                    "feature_name_preview": [
                        *extra.feature_names[:5],
                        *(extra.feature_names[-5:] if len(extra.feature_names) > 5 else ()),
                    ],
                    "registry": extra.registry,
                    "base_feature_names_to_drop_count": len(
                        extra.base_feature_names_to_drop
                    ),
                    "base_feature_names_to_drop_sha256": sha256_lines(
                        extra.base_feature_names_to_drop
                    ),
                    "base_feature_names_to_drop_preview": [
                        *extra.base_feature_names_to_drop[:5],
                        *(
                            extra.base_feature_names_to_drop[-5:]
                            if len(extra.base_feature_names_to_drop) > 5
                            else ()
                        ),
                    ],
                    "base_feature_names_after_drop_sha256": sha256_lines(
                        kept_base_feature_names
                    ),
                }
            )
        fold_model_params = dict(model_params)
        tuning_record: dict[str, Any] | None = None
        if fold_model_tuner is not None:
            tuning = fold_model_tuner(
                fold=fold,
                features=x_train_fold,
                target=y_train,
                base_model_parameters=model_params,
            )
            fold_model_params.update(tuning.parameters)
            tuning_record = tuning.record
            fold_tuning_records.append(tuning.record)
            tuning_artifact_paths.extend(tuning.artifact_paths)
        sample_weight = (
            compute_sample_weight(class_weight="balanced", y=y_train)
            if config["training"]["balanced_sample_weight"]
            else None
        )
        if fold_sample_weight_multiplier is not None:
            base_sample_weight = (
                sample_weight
                if sample_weight is not None
                else compute_sample_weight(class_weight="balanced", y=y_train)
            )
            multiplier = fold_sample_weight_multiplier(
                fold=fold,
                train_indices=train_indices,
                y_train=y_train,
                base_sample_weight=base_sample_weight,
            )
            sample_weight = (
                base_sample_weight * multiplier
                if multiplier is not None
                else base_sample_weight
            )
            fold_sample_weight_records.append(
                {
                    "fold": fold,
                    "applied": multiplier is not None,
                    "multiplier_min": (
                        float(np.min(multiplier)) if multiplier is not None else None
                    ),
                    "multiplier_max": (
                        float(np.max(multiplier)) if multiplier is not None else None
                    ),
                    "multiplier_mean": (
                        float(np.mean(multiplier)) if multiplier is not None else None
                    ),
                    "adjusted_sample_count": (
                        int(np.sum(multiplier != 1.0))
                        if multiplier is not None
                        else 0
                    ),
                }
            )
        model = xgb.XGBClassifier(
            **fold_model_params,
            random_state=config["seed"] + fold,
        )
        model.fit(
            x_train_fold,
            y_train,
            sample_weight=sample_weight,
            eval_set=[(x_valid_fold, y_valid)],
            verbose=False,
        )
        checkpoint_audit: dict[str, Any] | None = None
        if checkpoint_selection in validation_checkpoint_policies:
            checkpoint_audit = audit_xgboost_validation_iterations(
                model,
                x_valid_fold,
                y_valid,
                selection_policy=checkpoint_selection,
                rolling_window_size=config["training"].get(
                    "checkpoint_rolling_window"
                ),
                minimum_iteration=config["training"].get(
                    "checkpoint_min_iteration"
                ),
                model_class_count=len(active_class_labels),
                evaluation_targets=y_valid_evaluation,
                prediction_evaluation_indices=model_to_evaluation,
                evaluation_class_count=len(CLASS_LABELS),
            )
            selected_iteration = int(
                checkpoint_audit["selected_checkpoint"]["iteration"]
            )
            training_best_iteration = int(
                checkpoint_audit["training_metric_best"]["iteration"]
            )
            valid_proba = predict_xgboost_at_iteration(
                model,
                x_valid_fold,
                selected_iteration,
                class_count=len(active_class_labels),
            ).astype(np.float32)
            fold_test_proba = predict_xgboost_at_iteration(
                model,
                x_test_fold,
                selected_iteration,
                class_count=len(active_class_labels),
            ).astype(np.float32)
            assert training_metric_oof is not None
            training_metric_oof[valid_indices] = predict_xgboost_at_iteration(
                model,
                x_valid_fold,
                training_best_iteration,
                class_count=len(active_class_labels),
            ).astype(np.float32)
            audit_path = model_dir / f"fold_{fold:02d}_checkpoint_audit.json"
            write_json(audit_path, checkpoint_audit)
            checkpoint_audit_paths.append(audit_path)
            save_xgboost_iteration_checkpoint(
                model, model_dir / f"fold_{fold:02d}.json", selected_iteration
            )
        else:
            valid_proba = model.predict_proba(x_valid_fold).astype(np.float32)
            fold_test_proba = model.predict_proba(x_test_fold).astype(np.float32)
            selected_iteration = getattr(model, "best_iteration", None)
            model.save_model(model_dir / f"fold_{fold:02d}.json")
        oof_proba[valid_indices] = valid_proba
        test_proba += fold_test_proba / n_splits
        valid_pred = valid_proba.argmax(axis=1)
        valid_pred_evaluation = model_to_evaluation[valid_pred]
        result = {
            "fold": fold,
            "macro_f1": float(
                f1_score(
                    y_valid_evaluation,
                    valid_pred_evaluation,
                    labels=np.arange(len(CLASS_LABELS)),
                    average="macro",
                    zero_division=0,
                )
            ),
            "merged_24_macro_f1": float(
                f1_score(
                    y_valid,
                    valid_pred,
                    labels=np.arange(len(active_class_labels)),
                    average="macro",
                    zero_division=0,
                )
            ),
            "accuracy": float(accuracy_score(y_valid_evaluation, valid_pred_evaluation)),
            "merged_24_accuracy": float(accuracy_score(y_valid, valid_pred)),
            "log_loss": float(
                log_loss(
                    y_valid,
                    valid_proba,
                    labels=np.arange(len(active_class_labels)),
                )
            ),
            "best_iteration": (
                None if selected_iteration is None else int(selected_iteration)
            ),
            "model_parameters": fold_model_params,
        }
        if tuning_record is not None:
            result["nested_tuning"] = {
                key: tuning_record[key]
                for key in (
                    "fit_scope",
                    "test_or_outer_validation_used_for_selection",
                    "study_name",
                    "sampler",
                    "sampler_seed",
                    "inner_n_splits",
                    "requested_trials",
                    "completed_trials",
                    "best_trial",
                    "best_value",
                    "best_parameters",
                    "database_path",
                )
            }
        if checkpoint_audit is not None:
            result["checkpoint_selection"] = {
                "policy": checkpoint_selection,
                "training_metric_best": checkpoint_audit["training_metric_best"],
                "macro_f1_best": checkpoint_audit["macro_f1_best"],
                "selected_checkpoint": checkpoint_audit["selected_checkpoint"],
                "macro_f1_delta": checkpoint_audit["macro_f1_delta"],
                "audit_path": relative_posix(checkpoint_audit_paths[-1], ROOT),
            }
            if "rolling_median_best" in checkpoint_audit:
                result["checkpoint_selection"]["rolling_median_best"] = (
                    checkpoint_audit["rolling_median_best"]
                )
        fold_metrics.append(result)
        print(json.dumps(result, ensure_ascii=False))

    if np.isnan(oof_proba).any():
        raise ValueError("OOF 확률에 채워지지 않은 값이 있습니다.")
    if fold_feature_builder is not None:
        resolved_config["fold_train_features"] = fold_feature_records
    if fold_model_tuner is not None:
        resolved_config["fold_model_tuning"] = fold_tuning_records
    if fold_sample_weight_multiplier is not None:
        resolved_config["fold_sample_weight_multiplier"] = fold_sample_weight_records
    if (
        fold_feature_builder is not None
        or fold_model_tuner is not None
        or fold_sample_weight_multiplier is not None
    ):
        resolved_config_path.write_text(
            yaml.safe_dump(resolved_config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    oof_pred = oof_proba.argmax(axis=1)
    test_pred = test_proba.argmax(axis=1)
    oof_pred_evaluation = model_to_evaluation[oof_pred]
    report = classification_report(
        y_evaluation,
        oof_pred_evaluation,
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
            "SUBCLASS_TRUE_MERGED": model_targets,
            "SUBCLASS_PRED": label_encoder.inverse_transform(oof_pred),
            "FOLD": train["fold"].astype(int),
        }
    )
    oof_frame.loc[:, list(active_probability_columns)] = oof_proba
    oof_frame.to_csv(oof_path, index=False, lineterminator="\n")

    test_probability_frame = pd.DataFrame({"ID": test_meta["ID"]})
    test_probability_frame.loc[:, list(active_probability_columns)] = test_proba
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
            "macro_f1": float(
                f1_score(
                    y_evaluation,
                    oof_pred_evaluation,
                    labels=np.arange(len(CLASS_LABELS)),
                    average="macro",
                    zero_division=0,
                )
            ),
            "merged_24_macro_f1": float(
                f1_score(
                    y,
                    oof_pred,
                    labels=np.arange(len(active_class_labels)),
                    average="macro",
                    zero_division=0,
                )
            ),
            "fold_mean": float(fold_scores.mean()),
            "fold_std": float(fold_scores.std()),
            "accuracy": float(accuracy_score(y_evaluation, oof_pred_evaluation)),
            "merged_24_accuracy": float(accuracy_score(y, oof_pred)),
            "log_loss": float(
                log_loss(y, oof_proba, labels=np.arange(len(active_class_labels)))
            ),
            "per_class_f1": {
                label: float(report[label]["f1-score"]) for label in CLASS_LABELS
            },
            "confusion_matrix": confusion_matrix(
                y_evaluation,
                oof_pred_evaluation,
                labels=np.arange(len(CLASS_LABELS)),
            ).tolist(),
        },
        "target_space": {
            "training_class_count": len(active_class_labels),
            "training_class_order": list(active_class_labels),
            "aliases": aliases,
            "primary_evaluation_class_count": len(CLASS_LABELS),
            "primary_evaluation_class_order": list(CLASS_LABELS),
            "primary_metric_penalizes_unpredicted_original_classes": True,
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
    if training_metric_oof is not None:
        if np.isnan(training_metric_oof).any():
            raise ValueError("training-metric 기준 OOF 확률이 완성되지 않았습니다.")
        training_metric_pred = training_metric_oof.argmax(axis=1)
        training_metric_pred_evaluation = model_to_evaluation[training_metric_pred]
        training_metric_report = classification_report(
            y_evaluation,
            training_metric_pred_evaluation,
            labels=np.arange(len(CLASS_LABELS)),
            target_names=CLASS_LABELS,
            output_dict=True,
            zero_division=0,
        )
        training_fold_scores = np.asarray(
            [
                float(item["checkpoint_selection"]["training_metric_best"]["macro_f1"])
                for item in fold_metrics
            ]
        )
        metrics["checkpoint_comparison"] = {
            "selection_scope": "outer_fold_validation_only",
            "checkpoint_policy": checkpoint_selection,
            "training_metric": "mlogloss",
            "primary_metric": "macro_f1",
            "training_metric_best": {
                "oof_macro_f1": float(
                    f1_score(
                        y_evaluation,
                        training_metric_pred_evaluation,
                        labels=np.arange(len(CLASS_LABELS)),
                        average="macro",
                        zero_division=0,
                    )
                ),
                "fold_mean": float(training_fold_scores.mean()),
                "fold_std": float(training_fold_scores.std()),
                "accuracy": float(
                    accuracy_score(y_evaluation, training_metric_pred_evaluation)
                ),
                "log_loss": float(
                    log_loss(
                        y,
                        training_metric_oof,
                        labels=np.arange(len(active_class_labels)),
                    )
                ),
                "per_class_f1": {
                    label: float(training_metric_report[label]["f1-score"])
                    for label in CLASS_LABELS
                },
            },
            "selected_checkpoint": metrics["oof"],
            "oof_macro_f1_delta": float(metrics["oof"]["macro_f1"])
            - float(
                f1_score(
                    y_evaluation,
                    training_metric_pred_evaluation,
                    labels=np.arange(len(CLASS_LABELS)),
                    average="macro",
                    zero_division=0,
                )
            ),
            "test_or_public_used_for_selection": False,
        }
        if checkpoint_selection == "macro_f1_validation":
            # Preserve the historical EXP-219 output contract for downstream
            # reports while exposing the policy-neutral key above.
            metrics["checkpoint_comparison"]["macro_f1_best"] = metrics["oof"]
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
        extra_artifact_paths=[
            ("checkpoint_iteration_audit", path)
            for path in checkpoint_audit_paths
        ]
        + [("nested_optuna", path) for path in tuning_artifact_paths],
        class_labels=active_class_labels,
        probability_columns=active_probability_columns,
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


def finalize_saved_run(
    config_path: Path,
    *,
    runner_command: str,
    fold_feature_builder: Any | None = None,
    model_class_labels: tuple[str, ...] | None = None,
    target_aliases: dict[str, str] | None = None,
) -> None:
    """Validate and verify a completed run after post-processing interruption."""
    config_path = config_path.resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    active_class_labels = tuple(model_class_labels or CLASS_LABELS)
    active_probability_columns = tuple(
        f"PROBA_{label}" for label in active_class_labels
    )
    aliases = dict(target_aliases or {})
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    artifact_slug = f"exp{context.issue_number:03d}_{config['slug']}"
    report_dir = ROOT / "reports" / artifact_slug
    model_dir = ROOT / "models" / artifact_slug
    reproducibility_dir = ROOT / "reproducibility" / artifact_slug
    feature_dir = ROOT / "data" / "processed" / f"{artifact_slug}_features"
    metrics_path = report_dir / "metrics.json"
    resolved_config_path = reproducibility_dir / "config.resolved.yaml"
    oof_path = ROOT / "oof" / f"{artifact_slug}.csv"
    test_probability_path = ROOT / "preds" / f"{artifact_slug}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{artifact_slug}.csv"

    required = [
        metrics_path,
        resolved_config_path,
        oof_path,
        test_probability_path,
        submission_path,
        feature_dir / "test_features.npz",
    ]
    if fold_feature_builder is not None:
        required.extend(
            [
                feature_dir / "train_features.npz",
                feature_dir / "feature_names.json",
            ]
        )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"finalize에 필요한 기존 산출물이 없습니다: {missing}")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    validate_json_document(metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json")
    resolved_config = yaml.safe_load(resolved_config_path.read_text(encoding="utf-8"))
    resolved_config["training"]["command"] = runner_command
    resolved_config_path.write_text(
        yaml.safe_dump(resolved_config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    test_features = sparse.load_npz(feature_dir / "test_features.npz")
    test_ids = pd.read_csv(TEST_PATH, usecols=["ID"], dtype=str)["ID"]
    fold_test_features: list[sparse.csr_matrix] | None = None
    if fold_feature_builder is not None:
        train_features = sparse.load_npz(feature_dir / "train_features.npz")
        feature_names = tuple(
            json.loads(
                (feature_dir / "feature_names.json").read_text(encoding="utf-8")
            )
        )
        train_meta = pd.read_csv(
            TRAIN_PATH, usecols=["ID", "SUBCLASS"], dtype=str
        )
        folds = pd.read_csv(
            ROOT / config["split"]["path"], dtype={"ID": str, "fold": int}
        )
        train = train_meta.merge(
            folds, on="ID", how="left", validate="one_to_one", sort=False
        )
        if not train["ID"].equals(train_meta["ID"]) or train["fold"].isna().any():
            raise ValueError("finalize fold 병합 결과가 원본 train과 일치하지 않습니다.")
        label_encoder = LabelEncoder().fit(list(active_class_labels))
        target = label_encoder.transform(
            train["SUBCLASS"].replace(aliases)
        ).astype(np.int32)
        fold_test_features = rebuild_fold_test_features(
            fold_feature_builder=fold_feature_builder,
            fold_assignments=train["fold"].to_numpy(dtype=np.int32),
            target=target,
            train_features=train_features,
            test_features=test_features,
            feature_names=feature_names,
            n_splits=int(config["split"]["n_splits"]),
        )
    audit_paths = [
        model_dir / f"fold_{fold:02d}_checkpoint_audit.json"
        for fold in range(config["split"]["n_splits"])
    ]
    verify_saved_inference(
        context=context,
        source_commit=str(metrics["git_commit"]),
        owner=str(metrics["owner"]),
        artifact_slug=artifact_slug,
        config=config,
        resolved_config=resolved_config,
        resolved_config_path=resolved_config_path,
        metrics=metrics,
        metrics_path=metrics_path,
        model_dir=model_dir,
        oof_path=oof_path,
        reproducibility_dir=reproducibility_dir,
        test_features=test_features,
        test_ids=test_ids,
        test_probability_path=test_probability_path,
        submission_path=submission_path,
        fold_test_features=fold_test_features,
        extra_artifact_paths=[
            ("checkpoint_iteration_audit", path) for path in audit_paths
        ],
        class_labels=active_class_labels,
        probability_columns=active_probability_columns,
    )


def rebuild_fold_test_features(
    *,
    fold_feature_builder: Any,
    fold_assignments: np.ndarray,
    target: np.ndarray,
    train_features: sparse.spmatrix,
    test_features: sparse.spmatrix,
    feature_names: tuple[str, ...],
    n_splits: int,
) -> list[sparse.csr_matrix]:
    """Recreate each fold's test matrix without fitting a model.

    The builder receives the same outer-train indices, target slice and base
    matrices as the original run. Validation and test remain transform-only.
    """
    if train_features.shape[0] != len(fold_assignments) or len(target) != len(
        fold_assignments
    ):
        raise ValueError("finalize train feature/fold/target 행 수가 다릅니다.")
    if train_features.shape[1] != len(feature_names):
        raise ValueError("finalize base feature 이름 수와 열 수가 다릅니다.")
    rebuilt: list[sparse.csr_matrix] = []
    for fold in range(n_splits):
        valid_mask = fold_assignments == fold
        train_indices = np.flatnonzero(~valid_mask)
        valid_indices = np.flatnonzero(valid_mask)
        extra = fold_feature_builder(
            fold=fold,
            train_indices=train_indices,
            valid_indices=valid_indices,
            base_train=train_features[train_indices],
            base_validation=train_features[valid_indices],
            base_test=test_features,
            base_feature_names=feature_names,
            target=target[train_indices],
        )
        _, _, filtered_test, _ = drop_named_base_features(
            train_features[train_indices],
            train_features[valid_indices],
            test_features,
            feature_names,
            extra.base_feature_names_to_drop,
        )
        rebuilt.append(
            sparse.hstack(
                [filtered_test, extra.test], format="csr", dtype=np.float32
            )
        )
    return rebuilt


if __name__ == "__main__":
    main()
