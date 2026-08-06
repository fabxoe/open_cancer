#!/usr/bin/env python
"""Run EXP-621: pairwise probability redistribution with stronger regularization.

Issue #621, follow-up to EXP-604 (rejected: same
`apply_pairwise_redistribution` mechanism, but the found deltas
clustered near the [-1,1] grid edge under a weak regularization_lambda
=0.001, causing Log Loss (+0.0169) and fold-std (+0.0014) to regress and
leaving non-eligible-class collateral at 0.0223 -- well above a
near-zero bar). This experiment reuses the exact same mechanism
(`open_cancer.nested_decision_offset.apply_pairwise_redistribution` /
`search_pairwise_delta`, unmodified) and only raises
regularization_lambda to 0.02 so the inner-cross-fit search itself
favors smaller, less extreme deltas -- a fresh search under the new
penalty, not a post-hoc rescaling of EXP-604's already-found deltas.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
import xgboost as xgb
import yaml
from scipy import sparse
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.constants import CLASS_LABELS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.feature_family import drop_named_base_features
from open_cancer.hashing import sha256_file
from open_cancer.hotspot_features import build_hotspot_augmented_features, resolve_hotspot_config
from open_cancer.isoform_position_mask import resolve_isoform_position_mask_from_config
from open_cancer.isoform_relative_position import resolve_isoform_relative_position_from_config
from open_cancer.model_runner import create_model_adapter
from open_cancer.mutation_features import (
    resolve_position_features_from_config,
    resolve_position_options_from_config,
)
from open_cancer.nested_decision_offset import (
    CANDIDATE_OFFSET_GRID,
    apply_pairwise_redistribution,
    fit_inner_cross_fitted_probabilities,
    search_pairwise_delta,
)
from open_cancer.paths import relative_posix
from open_cancer.validation import validate_json_document
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from open_cancer.abc_c_features import fixed_pathway_burden_family, pathway_mutation_type_family
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
    parse_stop_notation_invariant_token,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "exp621_pairwise_redistribution_regularized.yaml"
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
EXP374_CONFIG_PATH = ROOT / "configs" / "exp374_stop_isoform_residue_mask.yaml"
ISSUE = 621
EXP_ID = "EXP-621"
SLUG = "pairwise_redistribution_regularized"
ARTIFACT_SLUG = f"exp621_{SLUG}"
PARENT_EXPERIMENT = "EXP-374"
RUNNER_COMMAND = "uv run python scripts/run_exp621_pairwise_redistribution_regularized.py"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_exp374_train_matrix() -> tuple[sparse.csr_matrix, pd.Series]:
    """Reconstruct EXP-374's actual train feature matrix (not a frozen v1 proxy).

    EXP-233/276 used the frozen Feature Spec v1 as a fast inner-cross-fit
    proxy because their baseline (EXP-219) was itself trained on v1. EXP-374
    uses a materially different feature space (stop-notation-invariant
    parser, pathway-20 + hotspot-34 + Ensembl isoform residue mask), so this
    experiment rebuilds that exact feature space instead of reusing v1 --
    the inner-cross-fit proxy should match the baseline model's actual
    decision surface, not an older, unrelated one.
    """
    exp374_config = yaml.safe_load(EXP374_CONFIG_PATH.read_text(encoding="utf-8"))
    hotspot_config = exp374_config.get("hotspots", {})
    hotspots, _, _ = resolve_hotspot_config(hotspot_config)
    selected_position_features = resolve_position_features_from_config(exp374_config)
    position_options = resolve_position_options_from_config(exp374_config)
    position_token_filter, mask_semantic_contract = resolve_isoform_position_mask_from_config(
        exp374_config, root=ROOT
    )
    position_token_transformer, relative_semantic_contract = (
        resolve_isoform_relative_position_from_config(exp374_config, root=ROOT)
    )
    position_semantic_contract = relative_semantic_contract or mask_semantic_contract
    selected_robust_aggregates = tuple(
        exp374_config.get("features", {}).get("robust_aggregates", [])
    )
    # Shared cache dir with EXP-515 -- both reconstruct the identical EXP-374
    # feature space with identical options, so this safely cache-hits
    # (build_hotspot_augmented_features verifies input/feature-spec hashes
    # before reusing data/processed/ cache per PROJECT_CONTEXT.md).
    feature_dir = ROOT / "data" / "processed" / "exp515_exp374_base_features"
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
            "mutation_cell_parser": parse_stop_notation_invariant_cell,
            "mutation_parser_contract": STOP_NOTATION_PARSER_CONTRACT,
            **position_options,
        },
        hotspot_token_normalizer=normalize_stop_notation_token,
    )
    base_dir = Path(feature_report["base_dir"])
    x_base = sparse.load_npz(feature_dir / "train_features.npz").tocsr()
    all_feature_names = tuple(
        json.loads((feature_dir / "feature_names.json").read_text(encoding="utf-8"))
    )
    feature_train_ids = pd.read_csv(base_dir / "train_ids.csv", dtype=str)["ID"]

    # Own membership_path -- EXP-374's run_exp374_stop_isoform_residue_mask's
    # build_fold_features() hardcodes MEMBERSHIP to EXP-374's own committed
    # report path; reusing it here would overwrite that file as a side
    # effect. Point this proxy reconstruction at its own path instead.
    membership_path = ROOT / "reports" / ARTIFACT_SLUG / "exp374_pathway_membership_proxy.json"
    burden = partial(
        fixed_pathway_burden_family,
        token_parser=parse_stop_notation_invariant_token,
        version="2.1.0",
    )
    composition = partial(
        pathway_mutation_type_family,
        token_parser=parse_stop_notation_invariant_token,
        version="2.1.0",
    )
    builder = PathwayMutationTypeFoldBuilder(
        membership_path=membership_path,
        burden_factory=burden,
        composition_factory=composition,
    )
    n = x_base.shape[0]
    all_idx = np.arange(n)
    empty_idx = np.array([], dtype=np.int64)
    bundle = builder(
        fold=0,
        train_indices=all_idx,
        valid_indices=empty_idx,
        base_train=x_base,
        base_validation=x_base[:0],
        base_test=sparse.csr_matrix((0, x_base.shape[1])),
        base_feature_names=all_feature_names,
        target=np.zeros(n, dtype=np.int64),
    )
    x_train_full, _, _, _ = drop_named_base_features(
        x_base,
        x_base[:0],
        sparse.csr_matrix((0, x_base.shape[1])),
        all_feature_names,
        bundle.base_feature_names_to_drop,
    )
    x_full = sparse.hstack([x_train_full, bundle.train], format="csr", dtype=np.float32)
    return x_full.tocsr(), feature_train_ids


def main() -> None:
    started = datetime.now(timezone.utc)
    clock = time.perf_counter()
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    dirty = git("status", "--porcelain")
    if context.experiment_id != EXP_ID or dirty:
        raise RuntimeError(f"EXP-621은 clean issue-621 브랜치에서만 실행해야 합니다.\n{dirty}")

    out_report = ROOT / "reports" / ARTIFACT_SLUG
    out_repro = ROOT / "reproducibility" / ARTIFACT_SLUG
    for path in (out_report, out_repro):
        path.mkdir(parents=True, exist_ok=True)

    baseline_oof_path = ROOT / config["baseline"]["oof_path"]
    if not baseline_oof_path.is_file():
        raise FileNotFoundError(f"EXP-374 baseline OOF가 없습니다: {baseline_oof_path}.")

    x_all, feature_train_ids = build_exp374_train_matrix()

    train_raw = pd.read_csv(TRAIN_PATH, usecols=["ID", "SUBCLASS"], dtype=str)
    split = pd.read_csv(ROOT / config["split"]["path"], dtype={"ID": str, "fold": int})
    train = train_raw.merge(split, on="ID", how="left", validate="one_to_one", sort=False)
    if not train["ID"].equals(train_raw["ID"]) or train["fold"].isna().any():
        raise ValueError("split 병합 후 train 순서 또는 커버리지가 어긋났습니다.")
    if not feature_train_ids.equals(train["ID"]):
        raise ValueError("재구성한 EXP-374 feature 행렬의 ID 순서가 train과 다릅니다.")
    label_index = {label: index for index, label in enumerate(CLASS_LABELS)}
    y = train["SUBCLASS"].map(label_index).to_numpy(dtype=np.int64)
    folds = train["fold"].to_numpy(dtype=np.int32)

    baseline_oof = pd.read_csv(baseline_oof_path, dtype={"ID": str})
    if not baseline_oof["ID"].equals(train["ID"]):
        raise ValueError("EXP-374 baseline OOF의 ID 순서가 v1 feature matrix와 다릅니다.")
    proba_columns = [f"PROBA_{label}" for label in CLASS_LABELS]
    baseline_probabilities = baseline_oof.loc[:, proba_columns].to_numpy(dtype=np.float64)
    baseline_argmax = baseline_probabilities.argmax(axis=1)
    n_classes = len(CLASS_LABELS)
    baseline_oof_macro_f1 = float(
        f1_score(y, baseline_argmax, labels=np.arange(n_classes), average="macro", zero_division=0)
    )
    baseline_log_loss = float(log_loss(y, baseline_probabilities, labels=np.arange(n_classes)))
    baseline_per_class_f1 = {
        label: float(f1_score(y == index, baseline_argmax == index, zero_division=0))
        for index, label in enumerate(CLASS_LABELS)
    }

    pairwise_cfg = config["pairwise_redistribution"]
    eligible_pairs = pairwise_cfg["eligible_class_pairs"]
    eligible_labels = {label for pair in eligible_pairs for label in pair}
    eligible_pair_indices = [
        tuple(label_index[label] for label in pair) for pair in eligible_pairs
    ]

    model_params = dict(config["model"])
    inner_cfg = config["inner_cross_fitting"]
    offset_cfg = config["offset_search"]
    candidate_grid = tuple(
        round(float(v), 1)
        for v in np.arange(
            offset_cfg["candidate_grid_min"],
            offset_cfg["candidate_grid_max"] + offset_cfg["candidate_grid_step"] / 2,
            offset_cfg["candidate_grid_step"],
        )
    )
    if candidate_grid != CANDIDATE_OFFSET_GRID:
        raise ValueError("config의 candidate grid가 nested_decision_offset.py 상수와 다릅니다.")

    n_splits = config["split"]["n_splits"]

    adjusted_probabilities = baseline_probabilities.copy()
    fold_records: list[dict[str, Any]] = []
    for outer_fold in range(n_splits):
        outer_valid_mask = folds == outer_fold
        outer_train_indices = np.flatnonzero(~outer_valid_mask)
        outer_valid_indices = np.flatnonzero(outer_valid_mask)

        x_outer_train = x_all[outer_train_indices]
        y_outer_train = y[outer_train_indices]

        def train_fn(inner_train_pos: np.ndarray, inner_holdout_pos: np.ndarray) -> np.ndarray:
            x_inner_train = x_outer_train[inner_train_pos]
            y_inner_train = y_outer_train[inner_train_pos]
            x_inner_holdout = x_outer_train[inner_holdout_pos]
            y_inner_holdout = y_outer_train[inner_holdout_pos]
            sample_weight = (
                compute_sample_weight(class_weight="balanced", y=y_inner_train)
                if config["training"]["balanced_sample_weight"]
                else None
            )
            adapter = create_model_adapter(
                "xgboost", model_params, inner_cfg["seed_base"] + outer_fold
            )
            adapter.fit(x_inner_train, y_inner_train, x_inner_holdout, y_inner_holdout, sample_weight)
            return adapter.predict_proba(x_inner_holdout)

        inner_result = fit_inner_cross_fitted_probabilities(
            features=x_outer_train,
            targets=y_outer_train,
            train_fn=train_fn,
            n_splits=inner_cfg["n_splits"],
            seed=inner_cfg["seed_base"] + outer_fold,
        )

        outer_before = baseline_probabilities[outer_valid_indices]
        outer_after = outer_before.copy()
        pair_deltas: dict[str, float] = {}
        for pair_labels, pair_idx in zip(eligible_pairs, eligible_pair_indices):
            # Each pair's delta is searched independently against the SAME
            # inner-cross-fit probabilities (not chained), since pairs touch
            # disjoint columns and never interact. Applied to outer_after
            # sequentially -- safe because apply_pairwise_redistribution
            # never reads or writes any column outside its own pair.
            search_result = search_pairwise_delta(
                inner_result.probabilities,
                y_outer_train,
                pair_idx,
                candidate_grid=candidate_grid,
                regularization_lambda=offset_cfg["regularization_lambda"],
            )
            delta = search_result["delta"]
            pair_deltas["/".join(pair_labels)] = delta
            outer_after = apply_pairwise_redistribution(outer_after, pair_idx, delta)
        adjusted_probabilities[outer_valid_indices] = outer_after

        y_outer_valid = y[outer_valid_indices]
        outer_macro_f1_before = float(
            f1_score(
                y_outer_valid, outer_before.argmax(axis=1),
                labels=np.arange(n_classes), average="macro", zero_division=0,
            )
        )
        outer_macro_f1_after = float(
            f1_score(
                y_outer_valid, outer_after.argmax(axis=1),
                labels=np.arange(n_classes), average="macro", zero_division=0,
            )
        )
        fold_records.append(
            {
                "outer_fold": outer_fold,
                "eligible_class_pairs": eligible_pairs,
                "pair_deltas": pair_deltas,
                "outer_validation_macro_f1_before_offset": outer_macro_f1_before,
                "outer_validation_macro_f1_after_offset": outer_macro_f1_after,
                "outer_validation_macro_f1_delta": outer_macro_f1_after - outer_macro_f1_before,
            }
        )
        print(json.dumps(fold_records[-1], ensure_ascii=False))

    adjusted_argmax = adjusted_probabilities.argmax(axis=1)
    adjusted_oof_macro_f1 = float(
        f1_score(y, adjusted_argmax, labels=np.arange(n_classes), average="macro", zero_division=0)
    )
    fold_macro_f1_after = np.array(
        [r["outer_validation_macro_f1_after_offset"] for r in fold_records]
    )
    fold_macro_f1_before = np.array(
        [r["outer_validation_macro_f1_before_offset"] for r in fold_records]
    )
    log_loss_after = float(log_loss(y, adjusted_probabilities, labels=np.arange(n_classes)))
    per_class_f1_after = {
        label: float(f1_score(y == index, adjusted_argmax == index, zero_division=0))
        for index, label in enumerate(CLASS_LABELS)
    }
    per_class_f1_delta = {
        label: per_class_f1_after[label] - baseline_per_class_f1[label] for label in CLASS_LABELS
    }
    non_eligible_labels = [label for label in CLASS_LABELS if label not in eligible_labels]
    non_eligible_abs_delta_sum = float(
        sum(abs(per_class_f1_delta[label]) for label in non_eligible_labels)
    )

    baseline_fold_std = float(fold_macro_f1_before.std())
    adjusted_fold_std = float(fold_macro_f1_after.std())

    qualifies = (
        adjusted_oof_macro_f1 > baseline_oof_macro_f1
        and log_loss_after <= baseline_log_loss
        and adjusted_fold_std <= baseline_fold_std
        and non_eligible_abs_delta_sum <= config["official_selection"]["max_non_eligible_class_abs_f1_delta_sum"]
    )
    verdict = "ADOPT" if qualifies else "ARCHIVE"

    source_commit = git("rev-parse", "HEAD")
    owner = git("config", "user.name") or os.environ.get("USER", "unknown")
    finished = datetime.now(timezone.utc)

    resolved_config = {
        "experiment": {
            "record_role": config["record_role"],
            "issue_number": context.issue_number,
            "experiment_id": context.experiment_id,
            "component_experiments": config.get("component_experiments", []),
            "branch": context.branch,
            "owner": owner,
            "source_commit": source_commit,
            "dirty_worktree": bool(dirty),
            "started_at": started.isoformat(),
        },
        "baseline": {
            **config["baseline"],
            "oof_sha256": sha256_file(baseline_oof_path),
            "oof_macro_f1": baseline_oof_macro_f1,
            "log_loss": baseline_log_loss,
            "fold_std": baseline_fold_std,
            "per_class_f1": baseline_per_class_f1,
        },
        "base_feature_spec": {
            "name": "exp374_reconstructed",
            "note": (
                "Inner-cross-fit proxy uses EXP-374's own feature pipeline "
                "(stop-notation parser, pathway-20, hotspot-34, Ensembl "
                "isoform residue mask), rebuilt via build_exp374_train_matrix() "
                "in this script -- not the frozen Feature Spec v1 used by "
                "EXP-233/276, since EXP-374's baseline is not a v1 model."
            ),
            "train_shape": list(x_all.shape),
        },
        "split": {**config["split"], "sha256": sha256_file(ROOT / config["split"]["path"])},
        "inner_cross_fitting": inner_cfg,
        "pairwise_redistribution": pairwise_cfg,
        "offset_search": {**offset_cfg, "candidate_grid": list(candidate_grid)},
        "official_selection": config["official_selection"],
        "verdict": verdict,
        "non_eligible_class_abs_f1_delta_sum": non_eligible_abs_delta_sum,
        "model": {"class": "xgboost.XGBClassifier", "parameters": {**model_params, "num_class": n_classes}},
        "training": config["training"],
        "optimism_bias_disclosure": config["optimism_bias_disclosure"],
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "xgboost": xgb.__version__,
            "uv_lock_sha256": sha256_file(ROOT / "uv.lock"),
        },
        "command": RUNNER_COMMAND,
    }
    resolved_config_path = out_repro / "config.resolved.yaml"
    resolved_config_path.write_text(
        yaml.safe_dump(resolved_config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )

    metrics = {
        "experiment_id": EXP_ID,
        "record_role": "official",
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": ISSUE,
        "parent_experiment": PARENT_EXPERIMENT,
        "git_commit": source_commit,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "primary_metric": "macro_f1",
        "split_id": config["split"]["path"],
        "folds": [
            {
                "fold": r["outer_fold"],
                "macro_f1": r["outer_validation_macro_f1_after_offset"],
                "accuracy": None,
                "log_loss": None,
                "best_iteration": None,
            }
            for r in fold_records
        ],
        "oof": {
            "macro_f1": adjusted_oof_macro_f1,
            "fold_mean": float(fold_macro_f1_after.mean()),
            "fold_std": adjusted_fold_std,
            "accuracy": float(accuracy_score(y, adjusted_argmax)),
            "log_loss": log_loss_after,
            "per_class_f1": per_class_f1_after,
            "confusion_matrix": confusion_matrix(
                y, adjusted_argmax, labels=np.arange(n_classes)
            ).tolist(),
        },
        "artifacts": {"resolved_config": relative_posix(resolved_config_path, ROOT)},
        "runtime": {"seconds": time.perf_counter() - clock},
        "notes": (
            f"Verdict {verdict}. Baseline EXP-374 OOF macro_f1 {baseline_oof_macro_f1:.10f}, "
            f"delta {adjusted_oof_macro_f1 - baseline_oof_macro_f1:+.10f}. "
            f"Log Loss delta {log_loss_after - baseline_log_loss:+.10f}. "
            f"Fold-std delta {adjusted_fold_std - baseline_fold_std:+.10f}. "
            f"Non-eligible (22-class) summed abs F1 delta: {non_eligible_abs_delta_sum:.10f} "
            f"(gate <= {config['official_selection']['max_non_eligible_class_abs_f1_delta_sum']})."
        ),
    }
    metrics_path = out_report / "metrics.json"
    write_json(metrics_path, metrics)
    validate_json_document(metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json")

    pair_detail = {
        "baseline_oof_macro_f1": baseline_oof_macro_f1,
        "baseline_log_loss": baseline_log_loss,
        "baseline_fold_std": baseline_fold_std,
        "adjusted_oof_macro_f1": adjusted_oof_macro_f1,
        "adjusted_log_loss": log_loss_after,
        "adjusted_fold_std": adjusted_fold_std,
        "verdict": verdict,
        "eligible_class_pairs": eligible_pairs,
        "per_class_f1_before": baseline_per_class_f1,
        "per_class_f1_after": per_class_f1_after,
        "per_class_f1_delta": per_class_f1_delta,
        "non_eligible_class_abs_f1_delta_sum": non_eligible_abs_delta_sum,
        "fold_records": fold_records,
    }
    write_json(out_report / "pair_offset_detail.json", pair_detail)

    print(
        json.dumps(
            {
                "metrics": str(metrics_path),
                "baseline_oof_macro_f1": baseline_oof_macro_f1,
                "adjusted_oof_macro_f1": adjusted_oof_macro_f1,
                "non_eligible_class_abs_f1_delta_sum": non_eligible_abs_delta_sum,
                "verdict": verdict,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
