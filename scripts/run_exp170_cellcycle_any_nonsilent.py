#!/usr/bin/env python
"""Run EXP-170: EXP-094 Feature Spec v1 + P_any_nonsilent_cellcycle.

First pathway-aggregation ablation built on the Issue #167/#168 TCGA
PanCanAtlas gene-pathway catalog. Adds one column: whether any of the 15
Cell Cycle pathway genes carries a nonsilent (non-WT, non-synonymous)
mutation. See src/open_cancer/pathway_aggregation_features.py for the gene
list provenance and Issue #170 for the pre-check confirming zero overlap
with the team's existing 34-position hotspot list.
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
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss

from open_cancer.constants import CLASS_LABELS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.feature_family import build_family_registry, transform_checked
from open_cancer.frozen_feature_specs import materialize_frozen_feature_spec
from open_cancer.hashing import sha256_file
from open_cancer.model_runner import create_model_adapter, run_canonical_cv
from open_cancer.pathway_aggregation_features import cell_cycle_any_nonsilent_family
from open_cancer.paths import relative_posix
from open_cancer.validation import validate_json_document, validate_submission

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "exp170_cellcycle_any_nonsilent.yaml"
TRAIN = ROOT / "data" / "raw" / "train.csv"
TEST = ROOT / "data" / "raw" / "test.csv"
SAMPLE = ROOT / "data" / "raw" / "sample_submission.csv"
SPLIT = ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"
KNOWLEDGE = ROOT / "knowledge" / "tcga_pancanatlas_table_s3_cell_cycle_v1.json"
SLUG = "exp170_cellcycle_any_nonsilent"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def build_resolved_config(
    *,
    context: Any,
    owner: str,
    source_commit: str,
    started_at: datetime,
    feature_spec_manifest: dict[str, Any],
    family_registry: dict[str, Any],
    model_params: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the single-source-of-truth resolved config for this experiment.

    Combines the frozen v1 base Feature Spec identity (already computed by
    `materialize_frozen_feature_spec`) with this experiment's own pathway
    family registry entry, so config/runner/metrics/report all resolve to
    one traceable document per PROJECT_CONTEXT.md's resolved-config contract.
    """

    return {
        "experiment": {
            "issue_number": context.issue_number,
            "experiment_id": context.experiment_id,
            "branch": context.branch,
            "owner": owner,
            "source_commit": source_commit,
            "started_at": started_at.isoformat(),
        },
        "data": {
            "train": {"path": "data/raw/train.csv", "sha256": sha256_file(TRAIN)},
            "test": {"path": "data/raw/test.csv", "sha256": sha256_file(TEST)},
            "class_order": list(CLASS_LABELS),
        },
        "split": {
            "path": relative_posix(SPLIT, ROOT),
            "sha256": sha256_file(SPLIT),
            "method": "StratifiedKFold",
            "n_splits": 5,
            "seed": 42,
        },
        "base_feature_spec": {
            "name": feature_spec_manifest["name"],
            "base_experiment": feature_spec_manifest["base_experiment"],
            "base_feature_spec_sha256": feature_spec_manifest["base_feature_spec_sha256"],
            "source_config": relative_posix(
                ROOT / "configs" / "exp094_feature_spec_v1.yaml", ROOT
            ),
            "source_config_sha256": feature_spec_manifest["source_config_sha256"],
            "train_shape": feature_spec_manifest["train_shape"],
            "test_shape": feature_spec_manifest["test_shape"],
            "feature_names_sha256": feature_spec_manifest["feature_names_sha256"],
        },
        "pathway_family": family_registry,
        "model": {"class": "xgboost.XGBClassifier", "parameters": model_params},
        "training": {"balanced_sample_weight": True},
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


def main() -> None:
    started = datetime.now(timezone.utc)
    clock = time.perf_counter()
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    dirty = git("status", "--porcelain")
    if context.experiment_id != "EXP-170" or dirty:
        raise RuntimeError(
            "EXP-170은 clean issue-170 브랜치에서만 실행해야 합니다.\n" + dirty
        )

    feature_dir = ROOT / "data" / "processed" / f"{SLUG}_features"
    model_dir = ROOT / "models" / SLUG
    out_dir = ROOT / "reports" / SLUG
    reproducibility_dir = ROOT / "reproducibility" / SLUG
    for path in (model_dir, out_dir, reproducibility_dir):
        path.mkdir(parents=True, exist_ok=True)

    feature_spec_manifest = materialize_frozen_feature_spec(
        root=ROOT, name="v1", output_dir=feature_dir, train_path=TRAIN, test_path=TEST
    )
    x_train = sparse.load_npz(feature_dir / "train_features.npz").tocsr()
    x_test = sparse.load_npz(feature_dir / "test_features.npz").tocsr()

    train_raw = pd.read_csv(TRAIN, dtype=str, keep_default_na=False)
    test_raw = pd.read_csv(TEST, dtype=str, keep_default_na=False)
    fitted_family = cell_cycle_any_nonsilent_family(KNOWLEDGE).fit(train_raw)
    train_flag_matrix = transform_checked(fitted_family, train_raw)
    test_flag_matrix = transform_checked(fitted_family, test_raw)
    positive_rate_train = float(train_flag_matrix.toarray().mean())
    positive_rate_test = float(test_flag_matrix.toarray().mean())
    family_registry = build_family_registry([fitted_family])

    x_train = sparse.hstack([x_train, train_flag_matrix], format="csr")
    x_test = sparse.hstack([x_test, test_flag_matrix], format="csr")

    train = train_raw[["ID", "SUBCLASS"]]
    test = test_raw[["ID"]]
    split_path = ROOT / config["split"]["path"]
    split = train[["ID"]].merge(
        pd.read_csv(split_path, dtype={"ID": str, "fold": int}),
        on="ID",
        how="left",
        validate="one_to_one",
        sort=False,
    )
    folds = split["fold"].to_numpy(dtype=np.int32)
    targets = (
        train["SUBCLASS"]
        .map({label: i for i, label in enumerate(CLASS_LABELS)})
        .to_numpy(dtype=np.int32)
    )
    params = dict(config["model"])
    owner = git("config", "user.name") or "unknown"
    source_commit = git("rev-parse", "HEAD")
    resolved_config = build_resolved_config(
        context=context,
        owner=owner,
        source_commit=source_commit,
        started_at=started,
        feature_spec_manifest=feature_spec_manifest,
        family_registry=family_registry,
        model_params={**params, "num_class": len(CLASS_LABELS)},
    )
    resolved_config_path = reproducibility_dir / "config.resolved.yaml"
    resolved_config_path.write_text(
        yaml.safe_dump(resolved_config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    result = run_canonical_cv(
        train_features=x_train,
        test_features=x_test,
        targets=targets,
        folds=folds,
        adapter_factory=lambda fold: create_model_adapter("xgboost", params, 42 + fold),
        model_dir=model_dir,
        balanced_sample_weight=True,
    )
    pred = result.oof_probabilities.argmax(axis=1)
    f1 = f1_score(targets, pred, average="macro")
    fold_scores = np.asarray([row["macro_f1"] for row in result.fold_metrics])

    baseline = json.loads((ROOT / config["baseline"]["metrics_path"]).read_text(encoding="utf-8"))
    baseline_oof = baseline["oof"]
    per_class_f1 = {
        label: float(value)
        for label, value in zip(
            CLASS_LABELS,
            f1_score(targets, pred, average=None, labels=np.arange(len(CLASS_LABELS)), zero_division=0),
            strict=True,
        )
    }
    per_class_delta = {
        label: per_class_f1[label] - baseline_oof["per_class_f1"][label] for label in CLASS_LABELS
    }
    acceptance = config["acceptance"]
    macro_f1_delta = float(f1) - baseline_oof["macro_f1"]
    fold_std_delta = float(fold_scores.std()) - baseline_oof["fold_std"]
    log_loss_value = float(
        log_loss(targets, result.oof_probabilities, labels=np.arange(len(CLASS_LABELS)))
    )
    log_loss_delta = log_loss_value - baseline_oof["log_loss"]
    verdict = {
        "macro_f1_delta": macro_f1_delta,
        "macro_f1_gate_passed": macro_f1_delta >= acceptance["min_macro_f1_delta"],
        "fold_std_delta": fold_std_delta,
        "fold_std_gate_passed": fold_std_delta < acceptance["max_fold_std_delta"],
        "log_loss_delta": log_loss_delta,
        "log_loss_gate_passed": log_loss_delta <= 0,
        "worst_per_class_f1_delta": min(per_class_delta.values()),
        "per_class_f1_gate_passed": min(per_class_delta.values()) >= 0,
    }
    verdict["adopted"] = all(
        verdict[key]
        for key in (
            "macro_f1_gate_passed",
            "fold_std_gate_passed",
            "log_loss_gate_passed",
            "per_class_f1_gate_passed",
        )
    )

    metrics = {
        "experiment_id": "EXP-170",
        "record_role": "official",
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": 170,
        "parent_experiment": "EXP-094",
        "git_commit": source_commit,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "primary_metric": "macro_f1",
        "split_id": str(config["split"]["path"]),
        "folds": list(result.fold_metrics),
        "oof": {
            "macro_f1": float(f1),
            "fold_mean": float(fold_scores.mean()),
            "fold_std": float(fold_scores.std()),
            "accuracy": float(accuracy_score(targets, pred)),
            "log_loss": log_loss_value,
            "per_class_f1": per_class_f1,
            "confusion_matrix": confusion_matrix(
                targets, pred, labels=np.arange(len(CLASS_LABELS))
            ).tolist(),
        },
        "artifacts": {
            "resolved_config": relative_posix(resolved_config_path, ROOT),
            "feature_spec_manifest": relative_posix(
                feature_dir / "feature_spec_manifest.json", ROOT
            ),
            "models": relative_posix(model_dir, ROOT),
        },
        "runtime": {"seconds": time.perf_counter() - clock},
        "notes": (
            "EXP-094 frozen Feature Spec v1 + pathway__cellcycle_any_nonsilent, "
            "registered as a Feature Factory family (see resolved_config for "
            "the KnowledgeProvenance-backed registry entry; Cell Cycle "
            "pathway, 15 genes, Issue #167 catalog, zero overlap with "
            "EXTENDED_HOTSPOTS). "
            f"Train positive rate {positive_rate_train:.6f}, test positive "
            f"rate {positive_rate_test:.6f}. Baseline EXP-094 OOF macro_f1 "
            f"{baseline_oof['macro_f1']:.10f}, delta {macro_f1_delta:+.10f}, "
            f"fold_std delta {fold_std_delta:+.10f}, log_loss delta "
            f"{log_loss_delta:+.10f}, worst per-class F1 delta "
            f"{verdict['worst_per_class_f1_delta']:+.10f}. Verdict: "
            f"{'ADOPTED' if verdict['adopted'] else 'NOT ADOPTED'}."
        ),
    }
    metrics_path = out_dir / "metrics.json"
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    validate_json_document(metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json")

    verdict_path = out_dir / "verdict.json"
    verdict_path.write_text(
        json.dumps(
            {
                **verdict,
                "acceptance_criteria": acceptance,
                "baseline_experiment_id": baseline["experiment_id"],
                "baseline_oof_macro_f1": baseline_oof["macro_f1"],
                "positive_rate_train": positive_rate_train,
                "positive_rate_test": positive_rate_test,
                "per_class_f1_delta": per_class_delta,
                "cellcycle_hotspot_overlap_with_extended_34": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    submission = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
    submission["SUBCLASS"] = np.asarray(CLASS_LABELS)[result.test_probabilities.argmax(axis=1)]
    submission_path = ROOT / "submissions" / f"{SLUG}.csv"
    submission.to_csv(submission_path, index=False, lineterminator="\n")
    validate_submission(submission_path, TEST)
    pd.DataFrame(result.oof_probabilities, columns=CLASS_LABELS).assign(ID=train.ID).to_csv(
        ROOT / "oof" / f"{SLUG}.csv", index=False
    )
    pd.DataFrame(result.test_probabilities, columns=CLASS_LABELS).assign(ID=test.ID).to_csv(
        ROOT / "preds" / f"{SLUG}_test_proba.csv", index=False
    )
    print(
        json.dumps(
            {
                "metrics": str(metrics_path),
                "verdict": str(verdict_path),
                "oof_macro_f1": float(f1),
                "adopted": verdict["adopted"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
