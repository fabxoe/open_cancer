#!/usr/bin/env python
"""Run Issue #306 fold-0 sparse denoising-autoencoder smoke gate."""

from __future__ import annotations

import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
import yaml
from scipy import sparse
from sklearn.metrics import accuracy_score, classification_report, f1_score, log_loss
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.checkpoint_selection import (
    audit_xgboost_validation_iterations,
    predict_xgboost_at_iteration,
    save_xgboost_iteration_checkpoint,
)
from open_cancer.constants import CLASS_LABELS
from open_cancer.hashing import sha256_file
from open_cancer.hotspot_features import build_hotspot_augmented_features, resolve_hotspot_config
from open_cancer.mutation_features import (
    resolve_position_features_from_config,
    resolve_position_options_from_config,
)
from open_cancer.sparse_denoising_autoencoder import (
    AutoencoderConfig,
    deterministic_holdout,
    latent_audit,
    load_gene_presence_csv,
    prevalence_baseline_bce,
    train_autoencoder,
    transform_autoencoder,
    write_json,
)
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder


ROOT = Path(__file__).resolve().parents[1]
TASK_CONFIG = ROOT / "configs" / "task306_sparse_denoising_autoencoder_fold0.yaml"
PARENT_CONFIG = ROOT / "configs" / "exp229_pathway_mutation_types.yaml"
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
REPORT_DIR = ROOT / "reports" / "analysis" / "task306_sparse_denoising_autoencoder"
ARTIFACT_DIR = ROOT / "models" / "task306_sparse_denoising_autoencoder"
FEATURE_DIR = ROOT / "data" / "processed" / "task306_parent_exp229_features"


def main() -> None:
    started = time.perf_counter()
    task = yaml.safe_load(TASK_CONFIG.read_text(encoding="utf-8"))
    parent = yaml.safe_load(PARENT_CONFIG.read_text(encoding="utf-8"))
    fold = int(task["split"]["outer_fold"])
    seed = int(task["seed"])
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    presence_train, train_ids, genes, labels = load_gene_presence_csv(
        TRAIN_PATH, has_labels=True
    )
    presence_test, test_ids, test_genes, _ = load_gene_presence_csv(
        TEST_PATH, has_labels=False
    )
    if genes != test_genes:
        raise ValueError("train/test gene order mismatch")
    train_meta = pd.DataFrame({"ID": train_ids, "SUBCLASS": labels})
    folds = pd.read_csv(ROOT / task["split"]["path"], dtype={"ID": str, "fold": int})
    merged = train_meta.merge(folds, on="ID", how="left", validate="one_to_one", sort=False)
    if not merged["ID"].equals(train_meta["ID"]) or merged["fold"].isna().any():
        raise ValueError("canonical split ID/order contract failed")
    valid_mask = merged["fold"].eq(fold).to_numpy()
    outer_train = np.flatnonzero(~valid_mask)
    outer_valid = np.flatnonzero(valid_mask)
    ae_train, ae_holdout = deterministic_holdout(
        outer_train,
        fraction=float(task["autoencoder"].pop("internal_holdout_fraction")),
        seed=seed,
    )
    ae_config = AutoencoderConfig(seed=seed, **task["autoencoder"])
    checkpoint = ARTIFACT_DIR / "fold_00_autoencoder.pt"
    training = train_autoencoder(
        presence_train,
        ae_train,
        ae_holdout,
        config=ae_config,
        checkpoint_path=checkpoint,
    )
    baseline_bce = prevalence_baseline_bce(presence_train, ae_train, ae_holdout)

    latent_outer_train = transform_autoencoder(
        presence_train, outer_train, checkpoint_path=checkpoint
    )
    latent_valid = transform_autoencoder(
        presence_train, outer_valid, checkpoint_path=checkpoint
    )
    latent_test = transform_autoencoder(
        presence_test, np.arange(presence_test.shape[0]), checkpoint_path=checkpoint
    )
    latent_valid_repeated = transform_autoencoder(
        presence_train, outer_valid, checkpoint_path=checkpoint
    )
    inference_equal = bool(np.array_equal(latent_valid, latent_valid_repeated))
    latent_statistics = latent_audit(
        latent_outer_train,
        np.asarray(presence_train[outer_train].sum(axis=1)).ravel(),
    )
    np.savez_compressed(
        ARTIFACT_DIR / "fold_00_latent.npz",
        train_indices=outer_train,
        valid_indices=outer_valid,
        train=latent_outer_train,
        validation=latent_valid,
        test=latent_test,
    )

    hotspots, _, _ = resolve_hotspot_config(parent.get("hotspots", {}))
    feature_report = build_hotspot_augmented_features(
        TRAIN_PATH,
        TEST_PATH,
        FEATURE_DIR,
        hotspots=hotspots,
        base_feature_options={
            "selected_robust_aggregates": tuple(
                parent.get("features", {}).get("robust_aggregates", [])
            ),
            "selected_position_features": resolve_position_features_from_config(parent),
            "position_token_filter": None,
            "position_token_transformer": None,
            "position_semantic_contract": None,
            **resolve_position_options_from_config(parent),
        },
    )
    base_train = sparse.load_npz(FEATURE_DIR / "train_features.npz")
    base_test = sparse.load_npz(FEATURE_DIR / "test_features.npz")
    feature_names = tuple(
        json.loads((FEATURE_DIR / "feature_names.json").read_text(encoding="utf-8"))
    )
    builder = PathwayMutationTypeFoldBuilder(
        membership_path=REPORT_DIR / "pathway_membership.json"
    )
    y_encoder = LabelEncoder().fit(list(CLASS_LABELS))
    y = y_encoder.transform(merged["SUBCLASS"]).astype(np.int32)
    extra = builder(
        fold=fold,
        train_indices=outer_train,
        valid_indices=outer_valid,
        base_train=base_train[outer_train],
        base_validation=base_train[outer_valid],
        base_test=base_test,
        base_feature_names=feature_names,
        target=y[outer_train],
    )
    x_train = sparse.hstack(
        [base_train[outer_train], extra.train, sparse.csr_matrix(latent_outer_train)],
        format="csr",
        dtype=np.float32,
    )
    x_valid = sparse.hstack(
        [base_train[outer_valid], extra.validation, sparse.csr_matrix(latent_valid)],
        format="csr",
        dtype=np.float32,
    )
    x_test = sparse.hstack(
        [base_test, extra.test, sparse.csr_matrix(latent_test)],
        format="csr",
        dtype=np.float32,
    )
    del x_test  # Transform contract is audited; no test prediction is selected in smoke mode.

    model_parameters = {**parent["model"], "num_class": len(CLASS_LABELS)}
    model = xgb.XGBClassifier(**model_parameters, random_state=seed + fold)
    model.fit(
        x_train,
        y[outer_train],
        sample_weight=compute_sample_weight(class_weight="balanced", y=y[outer_train]),
        eval_set=[(x_valid, y[outer_valid])],
        verbose=False,
    )
    checkpoint_audit = audit_xgboost_validation_iterations(
        model, x_valid, y[outer_valid], selection_policy="macro_f1_validation"
    )
    selected_iteration = int(checkpoint_audit["selected_checkpoint"]["iteration"])
    probability = predict_xgboost_at_iteration(model, x_valid, selected_iteration)
    probability_repeated = predict_xgboost_at_iteration(model, x_valid, selected_iteration)
    downstream_equal = bool(np.array_equal(probability, probability_repeated))
    prediction = probability.argmax(axis=1)
    report = classification_report(
        y[outer_valid],
        prediction,
        labels=np.arange(len(CLASS_LABELS)),
        target_names=CLASS_LABELS,
        output_dict=True,
        zero_division=0,
    )
    candidate = {
        "macro_f1": float(f1_score(y[outer_valid], prediction, average="macro")),
        "accuracy": float(accuracy_score(y[outer_valid], prediction)),
        "log_loss": float(
            log_loss(y[outer_valid], probability, labels=np.arange(len(CLASS_LABELS)))
        ),
        "selected_iteration": selected_iteration,
        "per_class_f1": {label: float(report[label]["f1-score"]) for label in CLASS_LABELS},
    }
    save_xgboost_iteration_checkpoint(
        model, ARTIFACT_DIR / "fold_00_xgboost.json", selected_iteration
    )
    parent_metrics = json.loads(
        (ROOT / "reports" / "exp229_pathway_mutation_types" / "metrics.json").read_text(
            encoding="utf-8"
        )
    )["folds"][fold]
    runtime_seconds = float(time.perf_counter() - started)
    raw_peak_memory = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    peak_memory_gib = (
        raw_peak_memory / 1024**3 if sys.platform == "darwin" else raw_peak_memory / 1024**2
    )
    gate_config = task["gate"]
    checks = {
        "reconstruction_beats_prevalence_baseline": bool(
            training["validation_audit"]["unweighted_bce"] < baseline_bce
        ),
        "no_zero_collapse": not bool(training["validation_audit"]["zero_collapse"]),
        "latent_constant_dimension_limit": bool(
            latent_statistics["near_constant_dimensions"]
            <= int(gate_config["maximum_near_constant_dimensions"])
        ),
        "latent_not_burden_copy": bool(
            latent_statistics["max_abs_burden_correlation"]
            < float(gate_config["maximum_abs_burden_correlation"])
        ),
        "fold0_macro_f1_drop_limit": bool(
            candidate["macro_f1"] - float(parent_metrics["macro_f1"])
            >= -float(gate_config["maximum_fold0_macro_f1_drop"])
        ),
        "autoencoder_checkpoint_inference_exact": inference_equal,
        "downstream_inference_exact": downstream_equal,
        "runtime_limit": runtime_seconds <= float(gate_config["maximum_runtime_seconds"]),
        "peak_memory_limit": peak_memory_gib <= float(gate_config["maximum_peak_memory_gib"]),
    }
    result = {
        "task_id": task["task_id"],
        "status": "PASS" if all(checks.values()) else "STOP",
        "parent_experiment": task["parent_experiment"],
        "outer_fold": fold,
        "data": {
            "train_sha256": sha256_file(TRAIN_PATH),
            "test_sha256": sha256_file(TEST_PATH),
            "split_sha256": sha256_file(ROOT / task["split"]["path"]),
            "gene_count": len(genes),
            "outer_train_rows": int(outer_train.size),
            "outer_validation_rows": int(outer_valid.size),
            "test_rows": len(test_ids),
        },
        "autoencoder": {
            "training": training,
            "prevalence_baseline_unweighted_bce": baseline_bce,
            "latent_audit": latent_statistics,
            "latent_shape": {
                "outer_train": list(latent_outer_train.shape),
                "outer_validation": list(latent_valid.shape),
                "test": list(latent_test.shape),
            },
        },
        "downstream": {
            "parent_fold0": {
                key: parent_metrics[key] for key in ("macro_f1", "accuracy", "log_loss")
            },
            "candidate_fold0": candidate,
            "macro_f1_delta": candidate["macro_f1"] - float(parent_metrics["macro_f1"]),
            "feature_dimension": int(x_train.shape[1]),
            "checkpoint_audit": checkpoint_audit,
        },
        "resources": {
            "runtime_seconds": runtime_seconds,
            "peak_memory_gib": peak_memory_gib,
        },
        "gate_checks": checks,
        "selection_uses_test_or_public": False,
    }
    write_json(REPORT_DIR / "smoke_metrics.json", result)
    print(json.dumps({"status": result["status"], "checks": checks, "candidate": candidate}, indent=2))


if __name__ == "__main__":
    main()
