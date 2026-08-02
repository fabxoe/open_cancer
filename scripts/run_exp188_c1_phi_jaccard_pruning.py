#!/usr/bin/env python
"""Run EXP-188: fold-safe conservative Phi/Jaccard pruning on Feature Spec v1."""

from __future__ import annotations

import argparse
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
from open_cancer.fold_feature_selection import (
    BorutaMutationPresenceSelector,
    ElasticNetStabilitySelector,
    MrmrMutationPresenceSelector,
    PhiJaccardGreedyPruner,
    RareMutationPresencePruner,
)
from open_cancer.frozen_feature_specs import materialize_frozen_feature_spec
from open_cancer.hashing import sha256_file
from open_cancer.model_artifacts import (
    build_oof_probability_frame,
    build_test_probability_frame,
    write_model_run_records,
)
from open_cancer.model_runner import create_model_adapter, run_canonical_cv
from open_cancer.validation import validate_json_document, validate_submission


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "exp188_c1_phi_jaccard_pruning.yaml"
TRAIN = ROOT / "data" / "raw" / "train.csv"
TEST = ROOT / "data" / "raw" / "test.csv"
SAMPLE = ROOT / "data" / "raw" / "sample_submission.csv"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def resolved_config(
    *,
    config: dict[str, Any],
    context: Any,
    owner: str,
    source_commit: str,
    started_at: datetime,
    feature_spec: dict[str, Any],
) -> dict[str, Any]:
    return {
        "experiment": {
            "experiment_id": context.experiment_id,
            "issue_number": context.issue_number,
            "branch": context.branch,
            "owner": owner,
            "parent_experiment": config["parent_experiment"],
            "source_commit": source_commit,
            "started_at": started_at.isoformat(),
        },
        "data": {
            "train": {"path": "data/raw/train.csv", "sha256": sha256_file(TRAIN)},
            "test": {"path": "data/raw/test.csv", "sha256": sha256_file(TEST)},
            "sample_submission": {"path": "data/raw/sample_submission.csv", "sha256": sha256_file(SAMPLE)},
            "class_order": list(CLASS_LABELS),
        },
        "split": {**config["split"], "sha256": sha256_file(ROOT / config["split"]["path"]), "method": "StratifiedKFold"},
        "base_feature_spec": feature_spec,
        "feature_selection": config["feature_selection"],
        "training": config["training"],
        "model": {"class": "xgboost.XGBClassifier", "parameters": config["model"]},
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


def verdict(*, delta: dict[str, float], acceptance: dict[str, float]) -> str:
    performance = (
        delta["macro_f1"] >= acceptance["min_macro_f1_delta"]
        and delta["fold_std"] < acceptance["max_fold_std_delta"]
        and delta["log_loss"] <= 0
    )
    if performance:
        return "ADOPT"
    simplification = (
        delta["macro_f1"] >= -acceptance["max_simplification_macro_f1_drop"]
        and delta["fold_std"] < acceptance["max_fold_std_delta"]
        and delta["log_loss"] <= acceptance["max_simplification_log_loss_increase"]
        and delta["worst_per_class_f1"] >= -acceptance["max_per_class_f1_drop"]
    )
    return "SIMPLIFICATION_CANDIDATE" if simplification else "ARCHIVE"


def compact_fold_metrics(
    fold_metrics: tuple[dict[str, Any], ...] | list[dict[str, Any]],
    *,
    model_dir: Path,
) -> list[dict[str, Any]]:
    """Keep committed metrics concise while preserving full pairs in fold masks."""
    compact: list[dict[str, Any]] = []
    for fold_metric in fold_metrics:
        record = dict(fold_metric)
        selection = record.get("feature_selection")
        if isinstance(selection, dict):
            selection = dict(selection)
            selection.pop("candidate_pairs", None)
            selection.pop("matched_pairs", None)
            dropped_feature_names = selection.pop("dropped_feature_names", [])
            dropped_gene_names = selection.pop("dropped_gene_names", [])
            dropped_prevalence = selection.pop("dropped_prevalence", None)
            selected_gene_names = selection.pop("selected_gene_names", [])
            confirmed_gene_names = selection.pop("confirmed_gene_names", [])
            selection_frequency = selection.pop("selection_frequency", None)
            hit_count_by_gene = selection.pop("hit_count_by_gene", None)
            max_shadow_importance_by_iteration = selection.pop("max_shadow_importance_by_iteration", None)
            if dropped_feature_names:
                selection["dropped_feature_count"] = len(dropped_feature_names)
            if dropped_gene_names:
                selection["dropped_gene_count"] = len(dropped_gene_names)
            if dropped_prevalence is not None:
                selection["dropped_prevalence_artifact"] = "fold feature selection artifact"
            if selected_gene_names:
                selection["selected_gene_count"] = len(selected_gene_names)
            if confirmed_gene_names:
                selection["confirmed_gene_count"] = len(confirmed_gene_names)
            if selection_frequency is not None:
                selection["selection_frequency_artifact"] = "fold feature selection artifact"
            if hit_count_by_gene is not None:
                selection["hit_count_artifact"] = "fold feature selection artifact"
            if max_shadow_importance_by_iteration is not None:
                selection["shadow_importance_artifact"] = "fold feature selection artifact"
            fold = int(record["fold"])
            selection_artifact = str(selection.get("candidate_pairs_artifact") or (
                model_dir / f"fold_{fold:02d}_feature_selection.json"
            ).relative_to(ROOT))
            selection["candidate_pairs_artifact"] = selection_artifact
            selection["matched_pairs_artifact"] = selection_artifact
            record["feature_selection"] = selection
        compact.append(record)
    return compact


def main(*, config_path: Path = DEFAULT_CONFIG) -> None:
    started_at = datetime.now(timezone.utc)
    timer = time.perf_counter()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    if context.experiment_id != config["experiment_id"] or context.issue_number != config["issue_number"]:
        raise RuntimeError("config와 현재 Issue 브랜치의 EXP-ID가 일치하지 않습니다.")
    if git("status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("공식 실험은 tracked worktree가 clean한 상태에서만 실행합니다.")
    slug = str(config["slug"])
    feature_dir = ROOT / "data" / "processed" / f"{slug}_features"
    model_dir = ROOT / "models" / slug
    report_dir = ROOT / "reports" / slug
    repro_dir = ROOT / "reproducibility" / slug
    for directory in (model_dir, report_dir, repro_dir):
        directory.mkdir(parents=True, exist_ok=True)

    spec_manifest = materialize_frozen_feature_spec(
        root=ROOT, name="v1", output_dir=feature_dir, train_path=TRAIN, test_path=TEST
    )
    train_features = sparse.load_npz(feature_dir / "train_features.npz").tocsr()
    test_features = sparse.load_npz(feature_dir / "test_features.npz").tocsr()
    feature_names = tuple(json.loads((feature_dir / "feature_names.json").read_text(encoding="utf-8")))
    train = pd.read_csv(TRAIN, usecols=["ID", "SUBCLASS"], dtype=str)
    test = pd.read_csv(TEST, usecols=["ID"], dtype=str)
    split_path = ROOT / config["split"]["path"]
    folds = train[["ID"]].merge(
        pd.read_csv(split_path, dtype={"ID": str, "fold": int}),
        on="ID", how="left", validate="one_to_one", sort=False,
    )["fold"].to_numpy(dtype=np.int32)
    targets = train["SUBCLASS"].map({label: index for index, label in enumerate(CLASS_LABELS)}).to_numpy(dtype=np.int32)
    if pd.isna(targets).any() or set(np.unique(folds)) != set(range(5)):
        raise RuntimeError("고정 class order 또는 canonical split 계약이 깨졌습니다.")
    selection_config = config["feature_selection"]
    if selection_config["method"] == "phi_jaccard_greedy_mutation_presence_pruner":
        selector = PhiJaccardGreedyPruner(
            phi_min=float(selection_config["phi_min"]),
            jaccard_min=float(selection_config["jaccard_min"]),
            min_joint_count=int(selection_config["min_joint_count"]),
        )
    elif selection_config["method"] == "rare_mutation_presence_pruner":
        selector = RareMutationPresencePruner(
            min_positive_count=int(selection_config["min_positive_count"]),
        )
    elif selection_config["method"] == "elastic_net_stability_selection":
        selector = ElasticNetStabilitySelector(
            c_values=tuple(float(value) for value in selection_config["c_values"]),
            l1_ratio=float(selection_config["l1_ratio"]),
            inner_splits=int(selection_config["inner_splits"]),
            subsample_fraction=float(selection_config["subsample_fraction"]),
            repetitions=int(selection_config["repetitions"]),
            min_frequency=int(selection_config["min_frequency"]),
            min_genes=int(selection_config["min_genes"]),
            max_genes=int(selection_config["max_genes"]),
            seed=int(config["seed"]),
            max_iter=int(selection_config.get("max_iter", 500)),
            n_jobs=int(selection_config.get("n_jobs", 1)),
        )
    elif selection_config["method"] == "mrmr_mutation_presence_selector":
        selector = MrmrMutationPresenceSelector(
            min_positive_count=int(selection_config["min_positive_count"]),
            selected_gene_count=int(selection_config["selected_gene_count"]),
        )
    elif selection_config["method"] == "boruta_mutation_presence_selector":
        selector = BorutaMutationPresenceSelector(
            n_estimators=int(selection_config["n_estimators"]),
            max_iter=int(selection_config["max_iter"]),
            perc=float(selection_config["perc"]),
            seed=int(config["seed"]),
            alpha=float(selection_config.get("alpha", 0.05)),
            n_jobs=int(selection_config.get("n_jobs", 1)),
        )
    else:
        raise RuntimeError(f"지원하지 않는 feature selection method: {selection_config['method']}")
    result = run_canonical_cv(
        train_features=train_features,
        test_features=test_features,
        targets=targets,
        folds=folds,
        adapter_factory=lambda fold: create_model_adapter("xgboost", dict(config["model"]), int(config["seed"]) + fold),
        model_dir=model_dir,
        balanced_sample_weight=bool(config["training"]["balanced_sample_weight"]),
        feature_names=feature_names,
        fold_feature_selector=selector,
    )
    predictions = result.oof_probabilities.argmax(axis=1)
    fold_scores = np.asarray([fold["macro_f1"] for fold in result.fold_metrics])
    per_class = {
        label: float(value)
        for label, value in zip(
            CLASS_LABELS,
            f1_score(targets, predictions, average=None, labels=np.arange(len(CLASS_LABELS)), zero_division=0),
            strict=True,
        )
    }
    baseline = json.loads((ROOT / config["baseline"]["metrics_path"]).read_text(encoding="utf-8"))["oof"]
    macro_f1 = float(f1_score(targets, predictions, average="macro"))
    log_loss_value = float(log_loss(targets, result.oof_probabilities, labels=np.arange(len(CLASS_LABELS))))
    delta = {
        "macro_f1": macro_f1 - float(baseline["macro_f1"]),
        "fold_std": float(fold_scores.std()) - float(baseline["fold_std"]),
        "log_loss": log_loss_value - float(baseline["log_loss"]),
        "worst_per_class_f1": min(per_class[label] - float(baseline["per_class_f1"][label]) for label in CLASS_LABELS),
    }
    decision = verdict(delta=delta, acceptance=config["acceptance"])
    owner = git("config", "user.name") or "unknown"
    source_commit = git("rev-parse", "HEAD")
    resolved = resolved_config(
        config=config, context=context, owner=owner, source_commit=source_commit,
        started_at=started_at, feature_spec=spec_manifest,
    )
    metrics = {
        "experiment_id": context.experiment_id,
        "record_role": "official",
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": context.issue_number,
        "parent_experiment": config["parent_experiment"],
        "git_commit": source_commit,
        "started_at": started_at.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "primary_metric": "macro_f1",
        "split_id": config["split"]["path"],
        "folds": compact_fold_metrics(result.fold_metrics, model_dir=model_dir),
        "oof": {
            "macro_f1": macro_f1,
            "fold_mean": float(fold_scores.mean()),
            "fold_std": float(fold_scores.std()),
            "accuracy": float(accuracy_score(targets, predictions)),
            "log_loss": log_loss_value,
            "per_class_f1": per_class,
            "confusion_matrix": confusion_matrix(targets, predictions, labels=np.arange(len(CLASS_LABELS))).tolist(),
        },
        "baseline_delta": delta,
        "decision": decision,
        "leaderboard": None,
        "runtime": {"seconds": time.perf_counter() - timer},
        "artifacts": {"feature_spec_manifest": str((feature_dir / "feature_spec_manifest.json").relative_to(ROOT)), "models": str(model_dir.relative_to(ROOT))},
        "notes": "Feature selection is fit only on outer-train; validation/test reuse each saved fold mask.",
    }
    metrics_path = report_dir / "metrics.json"
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validate_json_document(metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json")
    oof_path = ROOT / "oof" / f"{slug}.csv"
    test_path = ROOT / "preds" / f"{slug}_test_proba.csv"
    build_oof_probability_frame(ids=train["ID"].tolist(), true_labels=train["SUBCLASS"].tolist(), folds=folds, probabilities=result.oof_probabilities).to_csv(oof_path, index=False)
    build_test_probability_frame(ids=test["ID"].tolist(), probabilities=result.test_probabilities).to_csv(test_path, index=False)
    submission = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
    submission["SUBCLASS"] = np.asarray(CLASS_LABELS)[result.test_probabilities.argmax(axis=1)]
    submission_path = ROOT / "submissions" / f"{slug}.csv"
    submission.to_csv(submission_path, index=False, lineterminator="\n")
    validate_submission(submission_path, TEST)
    write_model_run_records(
        root=ROOT, output_dir=repro_dir, experiment_id=context.experiment_id or "", issue_number=context.issue_number or 0,
        source_commit=source_commit, resolved_config=resolved, metrics=metrics,
        data_files={"train": TRAIN, "test": TEST, "sample_submission": SAMPLE, "split": split_path},
        artifacts={
            "feature_spec_manifest": feature_dir / "feature_spec_manifest.json",
            "oof_probabilities": oof_path,
            "test_probabilities": test_path,
            "submission": submission_path,
            **{f"checkpoint_fold_{fold}": path for fold, path in enumerate(result.model_paths)},
            **{
                f"feature_selection_fold_{fold}": path
                for fold, path in enumerate(result.feature_selection_paths)
                if path is not None
            },
        },
        environment=resolved["environment"],
    )
    print(json.dumps({"experiment_id": context.experiment_id, "oof_macro_f1": macro_f1, "delta": delta, "decision": decision, "metrics": str(metrics_path)}, ensure_ascii=False, indent=2))


def replay_checkpoints(*, config_path: Path = DEFAULT_CONFIG) -> None:
    """Finish one experiment's artifacts from saved fold masks and checkpoints only."""
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    if context.experiment_id != config["experiment_id"]:
        raise RuntimeError("checkpoint replay config와 현재 Issue 브랜치의 EXP-ID가 일치하지 않습니다.")
    slug = str(config["slug"])
    report_dir = ROOT / "reports" / slug
    metrics_path = report_dir / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    feature_dir = ROOT / "data" / "processed" / f"{slug}_features"
    train_features = sparse.load_npz(feature_dir / "train_features.npz").tocsr()
    test_features = sparse.load_npz(feature_dir / "test_features.npz").tocsr()
    train = pd.read_csv(TRAIN, usecols=["ID", "SUBCLASS"], dtype=str)
    test = pd.read_csv(TEST, usecols=["ID"], dtype=str)
    split_path = ROOT / config["split"]["path"]
    folds = train[["ID"]].merge(
        pd.read_csv(split_path, dtype={"ID": str, "fold": int}),
        on="ID", how="left", validate="one_to_one", sort=False,
    )["fold"].to_numpy(dtype=np.int32)
    targets = train["SUBCLASS"].map({label: index for index, label in enumerate(CLASS_LABELS)}).to_numpy(dtype=np.int32)
    model_dir = ROOT / "models" / slug
    oof = np.full((len(train), len(CLASS_LABELS)), np.nan, dtype=np.float64)
    test_probabilities = np.zeros((len(test), len(CLASS_LABELS)), dtype=np.float64)
    model_paths: list[Path] = []
    selection_paths: list[Path] = []
    for fold in range(5):
        selection_path = model_dir / f"fold_{fold:02d}_feature_selection.json"
        document = json.loads(selection_path.read_text(encoding="utf-8"))
        indices = np.asarray(document["selected_indices"], dtype=np.int64)
        model_path = model_dir / f"fold_{fold:02d}.json"
        model = xgb.XGBClassifier()
        model.load_model(model_path)
        valid = folds == fold
        oof[valid] = model.predict_proba(train_features[valid][:, indices])
        test_probabilities += model.predict_proba(test_features[:, indices]) / 5
        model_paths.append(model_path)
        selection_paths.append(selection_path)
    if np.isnan(oof).any():
        raise RuntimeError("checkpoint replay OOF가 완성되지 않았습니다.")
    replay_macro_f1 = float(f1_score(targets, oof.argmax(axis=1), average="macro"))
    if not np.isclose(replay_macro_f1, float(metrics["oof"]["macro_f1"]), atol=1e-12, rtol=0):
        raise RuntimeError("checkpoint replay OOF Macro F1이 원 기록과 다릅니다.")
    oof_path = ROOT / "oof" / f"{slug}.csv"
    test_path = ROOT / "preds" / f"{slug}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{slug}.csv"
    build_oof_probability_frame(ids=train["ID"].tolist(), true_labels=train["SUBCLASS"].tolist(), folds=folds, probabilities=oof).to_csv(oof_path, index=False)
    build_test_probability_frame(ids=test["ID"].tolist(), probabilities=test_probabilities).to_csv(test_path, index=False)
    submission = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
    submission["SUBCLASS"] = np.asarray(CLASS_LABELS)[test_probabilities.argmax(axis=1)]
    submission.to_csv(submission_path, index=False, lineterminator="\n")
    validate_submission(submission_path, TEST)
    metrics["artifacts"].update({
        "oof_probabilities": str(oof_path.relative_to(ROOT)),
        "test_probabilities": str(test_path.relative_to(ROOT)),
        "submission": str(submission_path.relative_to(ROOT)),
    })
    metrics["notes"] += " Checkpoint replay completed the post-training artifact write without retraining."
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    spec_manifest = json.loads((feature_dir / "feature_spec_manifest.json").read_text(encoding="utf-8"))
    source_commit = str(metrics["git_commit"])
    resolved = resolved_config(
        config=config, context=context, owner=str(metrics["owner"]), source_commit=source_commit,
        started_at=datetime.fromisoformat(metrics["started_at"]), feature_spec=spec_manifest,
    )
    write_model_run_records(
        root=ROOT, output_dir=ROOT / "reproducibility" / slug,
        experiment_id=str(config["experiment_id"]), issue_number=int(config["issue_number"]),
        source_commit=source_commit, resolved_config=resolved, metrics=metrics,
        data_files={"train": TRAIN, "test": TEST, "sample_submission": SAMPLE, "split": split_path},
        artifacts={
            "feature_spec_manifest": feature_dir / "feature_spec_manifest.json",
            "oof_probabilities": oof_path,
            "test_probabilities": test_path,
            "submission": submission_path,
            **{f"checkpoint_fold_{fold}": path for fold, path in enumerate(model_paths)},
            **{f"feature_selection_fold_{fold}": path for fold, path in enumerate(selection_paths)},
        },
        environment=resolved["environment"],
    )
    print(json.dumps({"experiment_id": config["experiment_id"], "mode": "checkpoint_replay", "oof_macro_f1": replay_macro_f1, "submission": str(submission_path)}, ensure_ascii=False, indent=2))


def compact_existing_metrics(*, config_path: Path = DEFAULT_CONFIG) -> None:
    """Compact a pre-existing metrics record, then refresh its manifest by replay."""
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    slug = str(config["slug"])
    metrics_path = ROOT / "reports" / slug / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["folds"] = compact_fold_metrics(
        list(metrics["folds"]), model_dir=ROOT / "models" / slug
    )
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    replay_checkpoints(config_path=config_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--replay-checkpoints", action="store_true")
    parser.add_argument("--compact-record", action="store_true")
    args = parser.parse_args()
    if args.replay_checkpoints and args.compact_record:
        parser.error("--replay-checkpoints와 --compact-record는 함께 사용할 수 없습니다.")
    if args.compact_record:
        compact_existing_metrics(config_path=args.config)
    elif args.replay_checkpoints:
        replay_checkpoints(config_path=args.config)
    else:
        main(config_path=args.config)
