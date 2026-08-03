#!/usr/bin/env python
"""Official independent runner for EXP-235 OncoNPC-style analysis."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from scipy import sparse
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
)

from open_cancer.confidence_analysis import evaluate_pmax_thresholds
from open_cancer.constants import CLASS_LABELS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.frozen_feature_specs import materialize_frozen_feature_spec
from open_cancer.hashing import sha256_file
from open_cancer.model_artifacts import write_model_run_records
from open_cancer.model_runner import (
    create_model_adapter,
    run_canonical_cv,
    write_cross_validation_artifacts,
)
from open_cancer.nested_xgb_search import run_nested_xgb_search
from open_cancer.validation import (
    validate_competition_data,
    validate_json_document,
    validate_submission,
)


EXPECTED_EXPERIMENT_ID = "EXP-235"
CONFIG_NAME = "exp235_onconpc_xgb_confidence.yaml"
ARTIFACT_SLUG = "exp235_onconpc_xgb_confidence"
SPLIT_SHA256 = "1a99b82e758948fdf70c014b8270b73f0de805cd2450d119fcb20c08a9b169cf"


def find_root() -> Path:
    for candidate in [Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents]:
        if (candidate / "PROJECT_CONTEXT.md").is_file() and (
            candidate / "src" / "open_cancer"
        ).is_dir():
            return candidate.resolve()
    raise FileNotFoundError("open_cancer 저장소 루트를 찾지 못했습니다.")


ROOT = find_root()
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
SAMPLE_PATH = ROOT / "data" / "raw" / "sample_submission.csv"
SPLIT_PATH = ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_config(config: dict[str, Any], path: Path) -> None:
    checks = [
        (path.name == CONFIG_NAME, f"config 파일명은 {CONFIG_NAME}이어야 합니다."),
        (config.get("experiment_id") == EXPECTED_EXPERIMENT_ID, "experiment_id 불일치"),
        (config.get("run_mode") == "experiment", "run_mode는 experiment여야 합니다."),
        (config.get("record_role") == "official", "record_role은 official이어야 합니다."),
        (config.get("parent_experiment") == "EXP-094", "parent는 EXP-094여야 합니다."),
        (config["split"].get("n_splits") == 5, "canonical 5-fold가 필요합니다."),
        (config["split"].get("expected_sha256") == SPLIT_SHA256, "split SHA 불일치"),
        (config["search"].get("primary_metric") == "macro_f1", "1차 지표는 Macro F1입니다."),
        (config["confidence_analysis"].get("model_selection_use") is False, "pmax를 모델 선택에 사용할 수 없습니다."),
        (config["confidence_analysis"].get("submission_filtering") is False, "pmax로 submission을 필터링할 수 없습니다."),
    ]
    for condition, message in checks:
        if not condition:
            raise ValueError(message)


def load_folds(ids: pd.Series) -> np.ndarray:
    if sha256_file(SPLIT_PATH) != SPLIT_SHA256:
        raise ValueError("canonical split SHA-256 검증 실패")
    frame = pd.read_csv(SPLIT_PATH, dtype={"ID": str, "fold": int})
    if frame["ID"].duplicated().any() or set(frame["ID"]) != set(ids):
        raise ValueError("canonical split ID 계약 불일치")
    mapped = ids.map(frame.set_index("ID")["fold"])
    if mapped.isna().any():
        raise ValueError("fold가 없는 train ID가 있습니다.")
    folds = mapped.to_numpy(dtype=np.int8)
    counts = dict(pd.Series(folds).value_counts().sort_index().astype(int))
    if counts != {0: 1241, 1: 1240, 2: 1240, 3: 1240, 4: 1240}:
        raise ValueError(f"canonical fold 개수 불일치: {counts}")
    return folds


def build_metrics(
    *,
    context: Any,
    owner: str,
    commit: str,
    started_at: str,
    elapsed: float,
    labels: pd.Series,
    output: Any,
    paths: dict[str, Path],
) -> dict[str, Any]:
    mapping = {label: index for index, label in enumerate(CLASS_LABELS)}
    encoded = labels.map(mapping)
    if encoded.isna().any():
        raise ValueError("고정 클래스에 없는 SUBCLASS가 있습니다.")
    y = encoded.to_numpy(dtype=np.int32)
    prediction = output.oof_probabilities.argmax(axis=1)
    report = classification_report(
        y,
        prediction,
        labels=range(len(CLASS_LABELS)),
        target_names=CLASS_LABELS,
        output_dict=True,
        zero_division=0,
    )
    scores = [float(row["macro_f1"]) for row in output.fold_metrics]
    return {
        "experiment_id": context.experiment_id,
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": context.issue_number,
        "parent_experiment": "EXP-094",
        "git_commit": commit,
        "started_at": started_at,
        "finished_at": now(),
        "primary_metric": "macro_f1",
        "split_id": "data/splits/stratified_5fold_seed42.csv",
        "folds": list(output.fold_metrics),
        "oof": {
            "macro_f1": float(f1_score(y, prediction, average="macro")),
            "fold_mean": float(np.mean(scores)),
            "fold_std": float(np.std(scores)),
            "accuracy": float(accuracy_score(y, prediction)),
            "log_loss": float(log_loss(y, output.oof_probabilities, labels=np.arange(26))),
            "per_class_f1": {
                label: float(report[label]["f1-score"]) for label in CLASS_LABELS
            },
            "confusion_matrix": confusion_matrix(y, prediction, labels=range(26)).tolist(),
        },
        "leaderboard": None,
        "runtime": {"seconds": elapsed, "hardware": platform.platform()},
        "artifacts": {
            "resolved_config": relative(paths["resolved"]),
            "oof": relative(paths["oof"]),
            "test_probability": relative(paths["test_probability"]),
            "submission": relative(paths["submission"]),
            "models": relative(paths["models"]),
            "submission_sha256": sha256_file(paths["submission"]),
        },
        "notes": "Nested inner CV uses Macro F1; pmax is OOF analysis only.",
    }


def verify_checkpoints(
    model_paths: tuple[Path, ...],
    test_features: sparse.csr_matrix,
    original: np.ndarray,
    test_ids: pd.Series,
    submission_path: Path,
) -> dict[str, Any]:
    import xgboost as xgb

    reproduced = np.zeros_like(original, dtype=np.float64)
    for path in model_paths:
        model = xgb.XGBClassifier()
        model.load_model(path)
        reproduced += model.predict_proba(test_features) / len(model_paths)
    probability_match = bool(np.allclose(reproduced, original, atol=1e-6, rtol=1e-6))
    labels = np.asarray(CLASS_LABELS)[reproduced.argmax(axis=1)]
    reproduced_frame = pd.DataFrame({"ID": test_ids.tolist(), "SUBCLASS": labels})
    original_frame = pd.read_csv(submission_path, dtype=str, keep_default_na=False)
    agreement = float((labels == original_frame["SUBCLASS"].to_numpy()).mean())
    with tempfile.TemporaryDirectory(prefix="exp235_verify_") as directory:
        path = Path(directory) / submission_path.name
        reproduced_frame.to_csv(path, index=False, lineterminator="\n")
        sha_match = sha256_file(path) == sha256_file(submission_path)
    result = {
        "verified_at": now(),
        "data_hashes_match": True,
        "submission_sha256_match": sha_match,
        "test_label_agreement": agreement,
        "test_probability_allclose": probability_match,
        "test_probability_max_abs_diff": float(np.max(np.abs(reproduced - original))),
        "probability_atol": 1e-6,
        "probability_rtol": 1e-6,
        "passed": bool(probability_match and sha_match and agreement == 1.0),
    }
    if not result["passed"]:
        raise RuntimeError("checkpoint 추론 재현 검증 실패")
    return result


def write_report(
    path: Path,
    metrics: dict[str, Any],
    confidence: dict[str, Any],
) -> None:
    fold_rows = "\n".join(
        f"| {row['fold']} | {row['macro_f1']:.6f} | {row['accuracy']:.6f} | {row['log_loss']:.6f} | {row['best_iteration']} |"
        for row in metrics["folds"]
    )
    confidence_rows = "\n".join(
        f"| {row['threshold']:.1f} | {row['sample_count']} | {row['coverage']:.4f} | {row['macro_f1']} | {row['weighted_f1']} | {row['macro_precision']} |"
        for row in confidence["thresholds"]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# EXP-235: OncoNPC 스타일 nested-CV XGBoost 및 pmax 분석\n\n"
        "- Parent: EXP-094 / frozen Feature Spec v1\n"
        "- 모델 선택: outer-train 내부 Stratified CV의 Macro F1\n"
        "- pmax: OOF 분석 전용, submission 필터링 없음\n"
        "- 데이콘 Public 점수: 미제출\n\n"
        f"- OOF Macro F1: {metrics['oof']['macro_f1']:.10f}\n"
        f"- Fold std: {metrics['oof']['fold_std']:.10f}\n\n"
        "| Fold | Macro F1 | Accuracy | Log Loss | Best iteration |\n"
        "|---:|---:|---:|---:|---:|\n"
        f"{fold_rows}\n\n"
        "| pmax | Samples | Coverage | Macro F1 | Weighted F1 | Macro precision |\n"
        "|---:|---:|---:|---:|---:|---:|\n"
        f"{confidence_rows}\n",
        encoding="utf-8",
    )


def run(config_path: Path) -> None:
    started_at = now()
    timer = time.perf_counter()
    config_path = (config_path if config_path.is_absolute() else ROOT / config_path).resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    validate_config(config, config_path)
    context = resolve_experiment_context("experiment", cwd=ROOT)
    if context.experiment_id != EXPECTED_EXPERIMENT_ID:
        raise ValueError(f"Issue #235 브랜치가 아닙니다: {context.branch}")
    dirty = git("status", "--porcelain")
    if dirty:
        raise RuntimeError("공식 실행은 clean worktree에서만 가능합니다.\n" + dirty)
    commit = git("rev-parse", "HEAD")
    owner = git("config", "user.name") or os.environ.get("USER", "unknown")

    validate_competition_data(TRAIN_PATH, TEST_PATH, SAMPLE_PATH, strict_shape=True)
    train_meta = pd.read_csv(
        TRAIN_PATH, usecols=["ID", "SUBCLASS"], dtype=str, keep_default_na=False
    )
    test_meta = pd.read_csv(TEST_PATH, usecols=["ID"], dtype=str, keep_default_na=False)
    folds = load_folds(train_meta["ID"])
    mapping = {label: index for index, label in enumerate(CLASS_LABELS)}
    target_series = train_meta["SUBCLASS"].map(mapping)
    if target_series.isna().any():
        raise ValueError("고정 클래스에 없는 SUBCLASS가 있습니다.")
    targets = target_series.to_numpy(dtype=np.int32)

    processed = ROOT / "data" / "processed" / ARTIFACT_SLUG
    models = ROOT / "models" / ARTIFACT_SLUG
    reports = ROOT / "reports" / ARTIFACT_SLUG
    reproducibility = ROOT / "reproducibility" / ARTIFACT_SLUG
    paths = {
        "models": models,
        "oof": ROOT / "oof" / f"{ARTIFACT_SLUG}.csv",
        "test_probability": ROOT / "preds" / f"{ARTIFACT_SLUG}_test_proba.csv",
        "submission": ROOT / "submissions" / f"{ARTIFACT_SLUG}.csv",
        "resolved": reproducibility / "config.resolved.yaml",
    }
    feature_manifest = materialize_frozen_feature_spec(
        root=ROOT,
        name=config["feature_spec"]["name"],
        output_dir=processed,
        train_path=TRAIN_PATH,
        test_path=TEST_PATH,
    )
    train_features = sparse.load_npz(processed / "train_features.npz").tocsr()
    test_features = sparse.load_npz(processed / "test_features.npz").tocsr()
    feature_names = json.loads((processed / "feature_names.json").read_text(encoding="utf-8"))
    if train_features.shape != tuple(feature_manifest["train_shape"]):
        raise ValueError("train feature manifest 불일치")
    if test_features.shape != tuple(feature_manifest["test_shape"]):
        raise ValueError("test feature manifest 불일치")
    if train_features.shape[1] != len(feature_names):
        raise ValueError("feature 이름 수 불일치")

    selected_by_fold, search_document = run_nested_xgb_search(
        train_features=train_features,
        targets=targets,
        outer_folds=folds,
        base_parameters=config["search"]["base_parameters"],
        parameter_space=config["search"]["parameter_space"],
        n_iter=int(config["search"]["n_iter"]),
        inner_splits=int(config["search"]["inner_splits"]),
        seed=int(config["seed"]),
        balanced_sample_weight=bool(config["training"]["balanced_sample_weight"]),
    )
    reports.mkdir(parents=True, exist_ok=True)
    search_path = reports / "nested_search.json"
    write_json(search_path, search_document)

    seed = int(config["seed"])
    output = run_canonical_cv(
        train_features=train_features,
        test_features=test_features,
        targets=targets,
        folds=folds,
        adapter_factory=lambda fold: create_model_adapter(
            "xgboost", selected_by_fold[fold], seed + fold
        ),
        model_dir=models,
        balanced_sample_weight=bool(config["training"]["balanced_sample_weight"]),
    )
    for row in output.fold_metrics:
        print(json.dumps(row, ensure_ascii=False))

    common = write_cross_validation_artifacts(
        output=output,
        train_ids=train_meta["ID"].tolist(),
        true_labels=train_meta["SUBCLASS"].tolist(),
        folds=folds.tolist(),
        test_ids=test_meta["ID"].tolist(),
        output_dir=processed / "model_outputs",
    )
    paths["oof"].parent.mkdir(parents=True, exist_ok=True)
    paths["test_probability"].parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(common.oof_probabilities, paths["oof"])
    shutil.copy2(common.test_probabilities, paths["test_probability"])

    sample = pd.read_csv(SAMPLE_PATH, dtype=str, keep_default_na=False)
    if sample["ID"].tolist() != test_meta["ID"].tolist():
        raise ValueError("sample_submission ID 순서 불일치")
    sample["SUBCLASS"] = np.asarray(CLASS_LABELS)[output.test_probabilities.argmax(axis=1)]
    paths["submission"].parent.mkdir(parents=True, exist_ok=True)
    sample.to_csv(paths["submission"], index=False, lineterminator="\n")
    validate_submission(paths["submission"], TEST_PATH)

    confidence = evaluate_pmax_thresholds(
        targets=targets,
        probabilities=output.oof_probabilities,
        class_labels=CLASS_LABELS,
        thresholds=config["confidence_analysis"]["thresholds"],
    )
    confidence_path = reports / "pmax_confidence.json"
    write_json(confidence_path, confidence)
    metrics = build_metrics(
        context=context,
        owner=owner,
        commit=commit,
        started_at=started_at,
        elapsed=time.perf_counter() - timer,
        labels=train_meta["SUBCLASS"],
        output=output,
        paths=paths,
    )
    resolved = {
        "experiment": {
            "experiment_id": context.experiment_id,
            "issue_number": context.issue_number,
            "branch": context.branch,
            "owner": owner,
            "source_commit": commit,
            "dirty_worktree": False,
            "started_at": started_at,
        },
        "data": {
            "train": {"path": relative(TRAIN_PATH), "sha256": sha256_file(TRAIN_PATH)},
            "test": {"path": relative(TEST_PATH), "sha256": sha256_file(TEST_PATH)},
            "sample_submission": {"path": relative(SAMPLE_PATH), "sha256": sha256_file(SAMPLE_PATH)},
            "class_order": list(CLASS_LABELS),
        },
        "split": {"path": relative(SPLIT_PATH), "sha256": sha256_file(SPLIT_PATH)},
        "feature_spec": feature_manifest,
        "feature_count": len(feature_names),
        "nested_search": {
            "path": relative(search_path),
            "sha256": sha256_file(search_path),
            "selected_parameters_by_fold": list(selected_by_fold),
        },
        "confidence_analysis": {
            "path": relative(confidence_path),
            "sha256": sha256_file(confidence_path),
            **config["confidence_analysis"],
        },
        "training": {
            **config["training"],
            "command": (
                "uv run python scripts/run_exp235_onconpc_xgb_confidence.py "
                "--config configs/exp235_onconpc_xgb_confidence.yaml"
            ),
        },
    }
    artifacts = {
        **{f"checkpoint_fold_{fold}": path for fold, path in enumerate(output.model_paths)},
        "oof_probabilities": paths["oof"],
        "test_probabilities": paths["test_probability"],
        "submission": paths["submission"],
    }
    records = write_model_run_records(
        root=ROOT,
        output_dir=reproducibility,
        experiment_id=context.experiment_id,
        issue_number=context.issue_number,
        source_commit=commit,
        resolved_config=resolved,
        metrics=metrics,
        data_files={
            "train": TRAIN_PATH,
            "test": TEST_PATH,
            "sample_submission": SAMPLE_PATH,
            "canonical_split": SPLIT_PATH,
        },
        artifacts=artifacts,
        environment={
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "xgboost": importlib.metadata.version("xgboost"),
        },
    )
    shutil.copy2(records["metrics"], reports / "metrics.json")
    write_report(reports / "README.md", metrics, confidence)

    comparison = verify_checkpoints(
        output.model_paths,
        test_features,
        output.test_probabilities,
        test_meta["ID"],
        paths["submission"],
    )
    write_json(reproducibility / "comparison.json", comparison)
    write_json(reproducibility / "original_metrics.json", metrics)
    write_json(
        reproducibility / "reproduction_metrics.json",
        {"experiment_id": context.experiment_id, "verification_type": "checkpoint_inference", **comparison},
    )
    manifest = json.loads(records["artifact_manifest"].read_text(encoding="utf-8"))
    manifest.update(
        {
            "reproducibility_status": "INFERENCE_VERIFIED",
            "verifier": owner,
            "verified_at": comparison["verified_at"],
            "verification": {
                "data_hashes_match": True,
                "submission_sha256_match": comparison["submission_sha256_match"],
                "test_label_agreement": comparison["test_label_agreement"],
                "probability_atol": comparison["probability_atol"],
                "probability_rtol": comparison["probability_rtol"],
                "passed": comparison["passed"],
            },
        }
    )
    write_json(records["artifact_manifest"], manifest)
    (reproducibility / "REPRODUCE.md").write_text(
        "# EXP-235 재현 절차\n\n```bash\nuv sync --frozen\n"
        "uv run python scripts/run_exp235_onconpc_xgb_confidence.py "
        "--config configs/exp235_onconpc_xgb_confidence.yaml\n"
        "uv run python scripts/validate_experiment.py\n```\n",
        encoding="utf-8",
    )
    checksum_files = sorted(
        path for path in reproducibility.iterdir() if path.is_file() and path.name != "checksums.sha256"
    )
    (reproducibility / "checksums.sha256").write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in checksum_files),
        encoding="utf-8",
    )
    for document, schema_name in [
        (reports / "metrics.json", "metrics.schema.json"),
        (records["artifact_manifest"], "reproducibility_manifest.schema.json"),
    ]:
        schema = ROOT / "schemas" / schema_name
        if schema.is_file():
            validate_json_document(document, schema)
    print(
        json.dumps(
            {
                "experiment_id": context.experiment_id,
                "artifact_slug": ARTIFACT_SLUG,
                "oof_macro_f1": metrics["oof"]["macro_f1"],
                "reproducibility_status": "INFERENCE_VERIFIED",
                "submission": relative(paths["submission"]),
                "metrics": relative(reports / "metrics.json"),
                "pmax_analysis": relative(confidence_path),
                "history_update_required": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / CONFIG_NAME)
    args = parser.parse_args()
    run(args.config)


if __name__ == "__main__":
    main()
