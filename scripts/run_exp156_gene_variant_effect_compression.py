#!/usr/bin/env python
"""Official independent runner for EXP-156.

This runner follows the current team contracts directly.  It does not import
or modify another experiment runner.
"""

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

from open_cancer.compact_effect_features import (
    materialize_compact_effect_ablation,
)
from open_cancer.constants import CLASS_LABELS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.hashing import sha256_file
from open_cancer.model_artifacts import write_model_run_records
from open_cancer.model_runner import (
    create_model_adapter,
    run_canonical_cv,
    write_cross_validation_artifacts,
)
from open_cancer.validation import (
    validate_competition_data,
    validate_json_document,
    validate_submission,
)


EXPECTED_EXPERIMENT_ID = "EXP-156"
EXPECTED_CONFIG_NAME = "exp156_gene_variant_effect_compression.yaml"
CANONICAL_SPLIT_SHA256 = (
    "1a99b82e758948fdf70c014b8270b73f0de805cd2450d119fcb20c08a9b169cf"
)


def find_project_root() -> Path:
    candidates = [Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents]
    for candidate in candidates:
        if (
            (candidate / "PROJECT_CONTEXT.md").is_file()
            and (candidate / "src" / "open_cancer").is_dir()
        ):
            return candidate.resolve()
    raise FileNotFoundError("open_cancer 저장소 루트를 찾지 못했습니다.")


ROOT = find_project_root()
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
SAMPLE_SUBMISSION_PATH = ROOT / "data" / "raw" / "sample_submission.csv"
SPLIT_PATH = ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def load_folds(train_ids: pd.Series) -> np.ndarray:
    if sha256_file(SPLIT_PATH) != CANONICAL_SPLIT_SHA256:
        raise ValueError("canonical split SHA-256이 다릅니다.")
    split = pd.read_csv(SPLIT_PATH, dtype={"ID": str, "fold": int})
    if split["ID"].duplicated().any():
        raise ValueError("canonical split ID가 중복됩니다.")
    if set(split["ID"]) != set(train_ids):
        raise ValueError("canonical split과 train의 ID 집합이 다릅니다.")
    folds = train_ids.map(split.set_index("ID")["fold"])
    if folds.isna().any():
        raise ValueError("fold를 찾을 수 없는 train ID가 있습니다.")
    values = folds.to_numpy(dtype=np.int8)
    counts = dict(pd.Series(values).value_counts().sort_index().astype(int))
    expected = {0: 1241, 1: 1240, 2: 1240, 3: 1240, 4: 1240}
    if counts != expected:
        raise ValueError(f"canonical fold 개수가 다릅니다: {counts}")
    return values


def validate_config(config: dict[str, Any], config_path: Path) -> None:
    if config_path.name != EXPECTED_CONFIG_NAME:
        raise ValueError(f"config 파일명은 {EXPECTED_CONFIG_NAME}이어야 합니다.")
    if config.get("experiment_id") != EXPECTED_EXPERIMENT_ID:
        raise ValueError("config experiment_id가 EXP-156이 아닙니다.")
    if config.get("run_mode") != "experiment":
        raise ValueError("공식 실행의 run_mode는 experiment여야 합니다.")
    if config.get("record_role") != "official":
        raise ValueError("공식 실행의 record_role은 official이어야 합니다.")
    if config.get("slug") != "gene_variant_effect_compression":
        raise ValueError("EXP-156 slug가 올바르지 않습니다.")
    if config.get("parent_experiment") != "EXP-094":
        raise ValueError("EXP-156 parent experiment는 EXP-094여야 합니다.")
    if config["feature_spec"].get("name") != "v1":
        raise ValueError("EXP-156 parent Feature Spec은 v1이어야 합니다.")
    if config["split"].get("path") != "data/splits/stratified_5fold_seed42.csv":
        raise ValueError("공식 비교 실험은 canonical split을 사용해야 합니다.")
    if int(config["split"].get("n_splits", 0)) != 5:
        raise ValueError("canonical split은 5-fold여야 합니다.")
    if config["split"].get("expected_sha256") != CANONICAL_SPLIT_SHA256:
        raise ValueError("config의 canonical split SHA-256이 다릅니다.")
    if config["model"].get("name") != "xgboost":
        raise ValueError("EXP-156 모델은 xgboost여야 합니다.")


def calculate_metrics(
    *,
    context: Any,
    owner: str,
    source_commit: str,
    started_at: str,
    elapsed_seconds: float,
    labels: pd.Series,
    output: Any,
    oof_path: Path,
    test_probability_path: Path,
    submission_path: Path,
    model_dir: Path,
    resolved_config_path: Path,
) -> dict[str, Any]:
    class_to_index = {label: index for index, label in enumerate(CLASS_LABELS)}
    target = labels.map(class_to_index)
    if target.isna().any():
        raise ValueError("고정 26개 클래스에 없는 SUBCLASS가 있습니다.")
    y = target.to_numpy(dtype=np.int32)
    prediction = output.oof_probabilities.argmax(axis=1)
    report = classification_report(
        y,
        prediction,
        labels=range(len(CLASS_LABELS)),
        target_names=CLASS_LABELS,
        output_dict=True,
        zero_division=0,
    )
    fold_scores = [float(row["macro_f1"]) for row in output.fold_metrics]
    return {
        "experiment_id": context.experiment_id,
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": context.issue_number,
        "parent_experiment": "EXP-094",
        "git_commit": source_commit,
        "started_at": started_at,
        "finished_at": utc_now(),
        "primary_metric": "macro_f1",
        "split_id": "data/splits/stratified_5fold_seed42.csv",
        "folds": list(output.fold_metrics),
        "oof": {
            "macro_f1": float(f1_score(y, prediction, average="macro")),
            "fold_mean": float(np.mean(fold_scores)),
            "fold_std": float(np.std(fold_scores)),
            "accuracy": float(accuracy_score(y, prediction)),
            "log_loss": float(
                log_loss(
                    y,
                    output.oof_probabilities,
                    labels=np.arange(len(CLASS_LABELS)),
                )
            ),
            "per_class_f1": {
                label: float(report[label]["f1-score"])
                for label in CLASS_LABELS
            },
            "confusion_matrix": confusion_matrix(
                y, prediction, labels=range(len(CLASS_LABELS))
            ).tolist(),
        },
        "leaderboard": None,
        "runtime": {
            "seconds": elapsed_seconds,
            "hardware": platform.platform(),
        },
        "artifacts": {
            "resolved_config": relative(resolved_config_path),
            "oof": relative(oof_path),
            "test_probability": relative(test_probability_path),
            "submission": relative(submission_path),
            "models": relative(model_dir),
            "submission_sha256": sha256_file(submission_path),
        },
        "notes": (
            "Feature Spec v1에서 유전자별 변이 유형 indicator만 compact effect "
            "representation으로 교체한 label-free ablation."
        ),
    }


def write_report(
    path: Path,
    metrics: dict[str, Any],
    feature_manifest: dict[str, Any],
) -> None:
    fold_rows = "\n".join(
        (
            f"| {row['fold']} | {row['macro_f1']:.6f} | "
            f"{row['accuracy']:.6f} | {row['log_loss']:.6f} | "
            f"{row['best_iteration']} |"
        )
        for row in metrics["folds"]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            "# EXP-156: 유전자별 변이 효과 압축 XGBoost\n\n"
            "## 실험 요약\n\n"
            "- Parent: EXP-094 / Feature Spec v1\n"
            "- 변경: 유전자별 변이 유형 indicator를 4개 compact descriptor로 교체\n"
            "- Split: canonical stratified 5-fold seed 42\n"
            "- Test 사용: 학습 완료 후 추론에만 사용\n"
            "- 데이콘 Public 점수: 미제출\n\n"
            "## 결과\n\n"
            f"- OOF Macro F1: {metrics['oof']['macro_f1']:.10f}\n"
            f"- Fold mean: {metrics['oof']['fold_mean']:.10f}\n"
            f"- Fold std: {metrics['oof']['fold_std']:.10f}\n"
            f"- Accuracy: {metrics['oof']['accuracy']:.10f}\n"
            f"- Log Loss: {metrics['oof']['log_loss']:.10f}\n"
            f"- 최종 특징 수: {feature_manifest['train_shape'][1]}\n\n"
            "| Fold | Macro F1 | Accuracy | Log Loss | Best iteration |\n"
            "|---:|---:|---:|---:|---:|\n"
            f"{fold_rows}\n"
        ),
        encoding="utf-8",
    )


def verify_saved_inference(
    *,
    model_paths: tuple[Path, ...],
    test_features: sparse.csr_matrix,
    original_probabilities: np.ndarray,
    test_ids: pd.Series,
    submission_path: Path,
    reproducibility_dir: Path,
    owner: str,
    source_commit: str,
) -> dict[str, Any]:
    import xgboost as xgb

    reproduced = np.zeros_like(original_probabilities, dtype=np.float64)
    for model_path in model_paths:
        model = xgb.XGBClassifier()
        model.load_model(model_path)
        reproduced += model.predict_proba(test_features) / len(model_paths)

    probability_match = bool(
        np.allclose(
            reproduced,
            original_probabilities,
            atol=1e-6,
            rtol=1e-6,
        )
    )
    maximum_difference = float(
        np.max(np.abs(reproduced - original_probabilities))
    )
    class_array = np.asarray(CLASS_LABELS)
    original_submission = pd.read_csv(
        submission_path, dtype=str, keep_default_na=False
    )
    reproduced_labels = class_array[reproduced.argmax(axis=1)]
    label_agreement = float(
        (reproduced_labels == original_submission["SUBCLASS"].to_numpy()).mean()
    )
    ids_match = original_submission["ID"].tolist() == test_ids.tolist()
    reproduced_submission = pd.DataFrame(
        {"ID": test_ids.tolist(), "SUBCLASS": reproduced_labels}
    )
    with tempfile.TemporaryDirectory(prefix="exp156_verify_") as temporary:
        reproduced_path = Path(temporary) / submission_path.name
        reproduced_submission.to_csv(
            reproduced_path, index=False, lineterminator="\n"
        )
        submission_sha_match = (
            sha256_file(reproduced_path) == sha256_file(submission_path)
        )
    passed = bool(
        probability_match
        and label_agreement == 1.0
        and ids_match
        and submission_sha_match
    )
    comparison = {
        "verified_at": utc_now(),
        "verifier": owner,
        "source_commit": source_commit,
        "data_hashes_match": True,
        "submission_sha256_match": submission_sha_match,
        "test_label_agreement": label_agreement,
        "test_probability_allclose": probability_match,
        "test_probability_max_abs_diff": maximum_difference,
        "probability_atol": 1e-6,
        "probability_rtol": 1e-6,
        "passed": passed,
    }
    if not passed:
        raise RuntimeError("저장 checkpoint 기반 추론 재현 검증에 실패했습니다.")
    write_json(reproducibility_dir / "comparison.json", comparison)
    return comparison


def run_experiment(config_path: Path) -> None:
    started_at = utc_now()
    start_time = time.perf_counter()
    config_path = (
        config_path if config_path.is_absolute() else ROOT / config_path
    ).resolve()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    validate_config(config, config_path)

    context = resolve_experiment_context("experiment", cwd=ROOT)
    if context.experiment_id != EXPECTED_EXPERIMENT_ID:
        raise ValueError(
            f"현재 브랜치는 {EXPECTED_EXPERIMENT_ID} Issue 브랜치여야 합니다: "
            f"{context.branch}"
        )
    dirty_status = run_git("status", "--porcelain")
    if dirty_status:
        raise RuntimeError(
            "공식 실험은 clean worktree에서만 실행합니다.\n" + dirty_status
        )
    source_commit = run_git("rev-parse", "HEAD")
    owner = (
        run_git("config", "user.name")
        or os.environ.get("USER")
        or os.environ.get("USERNAME")
        or "unknown"
    )

    validate_competition_data(
        TRAIN_PATH,
        TEST_PATH,
        SAMPLE_SUBMISSION_PATH,
        strict_shape=True,
    )
    if sha256_file(SPLIT_PATH) != CANONICAL_SPLIT_SHA256:
        raise ValueError("canonical split SHA-256 검증에 실패했습니다.")

    artifact_slug = "exp156_gene_variant_effect_compression"
    processed_dir = ROOT / "data" / "processed" / artifact_slug
    model_dir = ROOT / "models" / artifact_slug
    common_output_dir = processed_dir / "model_outputs"
    report_dir = ROOT / "reports" / artifact_slug
    reproducibility_dir = ROOT / "reproducibility" / artifact_slug
    oof_path = ROOT / "oof" / f"{artifact_slug}.csv"
    test_probability_path = ROOT / "preds" / f"{artifact_slug}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{artifact_slug}.csv"

    train_meta = pd.read_csv(
        TRAIN_PATH,
        usecols=["ID", "SUBCLASS"],
        dtype=str,
        keep_default_na=False,
    )
    test_meta = pd.read_csv(
        TEST_PATH,
        usecols=["ID"],
        dtype=str,
        keep_default_na=False,
    )
    folds = load_folds(train_meta["ID"])

    feature_manifest = materialize_compact_effect_ablation(
        root=ROOT,
        name=config["feature_spec"]["name"],
        output_dir=processed_dir,
        train_path=TRAIN_PATH,
        test_path=TEST_PATH,
    )
    train_features = sparse.load_npz(
        processed_dir / "train_features.npz"
    ).tocsr()
    test_features = sparse.load_npz(
        processed_dir / "test_features.npz"
    ).tocsr()
    feature_names = json.loads(
        (processed_dir / "feature_names.json").read_text(encoding="utf-8")
    )
    if train_features.shape[0] != len(train_meta):
        raise ValueError("train feature 행 수가 train.csv와 다릅니다.")
    if test_features.shape[0] != len(test_meta):
        raise ValueError("test feature 행 수가 test.csv와 다릅니다.")
    if (
        train_features.shape[1] != test_features.shape[1]
        or train_features.shape[1] != len(feature_names)
    ):
        raise ValueError("train/test/feature name 차원이 다릅니다.")

    class_to_index = {label: index for index, label in enumerate(CLASS_LABELS)}
    mapped_target = train_meta["SUBCLASS"].map(class_to_index)
    if mapped_target.isna().any():
        raise ValueError("고정 26개 클래스에 없는 SUBCLASS가 있습니다.")
    targets = mapped_target.to_numpy(dtype=np.int32)
    parameters = dict(config["model"]["parameters"])
    seed = int(config["seed"])

    output = run_canonical_cv(
        train_features=train_features,
        test_features=test_features,
        targets=targets,
        folds=folds,
        adapter_factory=lambda fold: create_model_adapter(
            "xgboost",
            parameters,
            seed + fold,
        ),
        model_dir=model_dir,
        balanced_sample_weight=bool(
            config["training"].get("balanced_sample_weight", True)
        ),
    )
    for row in output.fold_metrics:
        print(json.dumps(row, ensure_ascii=False))

    written = write_cross_validation_artifacts(
        output=output,
        train_ids=train_meta["ID"].tolist(),
        true_labels=train_meta["SUBCLASS"].tolist(),
        folds=folds.tolist(),
        test_ids=test_meta["ID"].tolist(),
        output_dir=common_output_dir,
    )
    oof_path.parent.mkdir(parents=True, exist_ok=True)
    test_probability_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(written.oof_probabilities, oof_path)
    shutil.copy2(written.test_probabilities, test_probability_path)

    sample_submission = pd.read_csv(
        SAMPLE_SUBMISSION_PATH, dtype=str, keep_default_na=False
    )
    if sample_submission["ID"].tolist() != test_meta["ID"].tolist():
        raise ValueError("sample_submission과 test의 ID 순서가 다릅니다.")
    sample_submission["SUBCLASS"] = np.asarray(CLASS_LABELS)[
        output.test_probabilities.argmax(axis=1)
    ]
    submission_path.parent.mkdir(parents=True, exist_ok=True)
    sample_submission.to_csv(submission_path, index=False, lineterminator="\n")
    validate_submission(submission_path, TEST_PATH)

    resolved_config_path = reproducibility_dir / "config.resolved.yaml"
    elapsed = time.perf_counter() - start_time
    metrics = calculate_metrics(
        context=context,
        owner=owner,
        source_commit=source_commit,
        started_at=started_at,
        elapsed_seconds=elapsed,
        labels=train_meta["SUBCLASS"],
        output=output,
        oof_path=oof_path,
        test_probability_path=test_probability_path,
        submission_path=submission_path,
        model_dir=model_dir,
        resolved_config_path=resolved_config_path,
    )
    resolved_config = {
        "experiment": {
            "experiment_id": context.experiment_id,
            "issue_number": context.issue_number,
            "branch": context.branch,
            "owner": owner,
            "source_commit": source_commit,
            "dirty_worktree": False,
            "started_at": started_at,
        },
        "data": {
            "train": {"path": relative(TRAIN_PATH), "sha256": sha256_file(TRAIN_PATH)},
            "test": {"path": relative(TEST_PATH), "sha256": sha256_file(TEST_PATH)},
            "sample_submission": {
                "path": relative(SAMPLE_SUBMISSION_PATH),
                "sha256": sha256_file(SAMPLE_SUBMISSION_PATH),
            },
            "class_order": list(CLASS_LABELS),
        },
        "split": {
            "path": relative(SPLIT_PATH),
            "sha256": sha256_file(SPLIT_PATH),
            "n_splits": 5,
            "seed": 42,
        },
        "feature_spec": feature_manifest,
        "feature_count": len(feature_names),
        "model": config["model"],
        "training": {
            **config["training"],
            "fold_seeds": [seed + fold for fold in range(5)],
            "best_iterations": [row["best_iteration"] for row in output.fold_metrics],
            "command": (
                "uv run python scripts/run_exp156_gene_variant_effect_compression.py "
                "--config configs/exp156_gene_variant_effect_compression.yaml"
            ),
        },
    }
    artifacts = {
        **{
            f"checkpoint_fold_{fold}": path
            for fold, path in enumerate(output.model_paths)
        },
        "oof_probabilities": oof_path,
        "test_probabilities": test_probability_path,
        "submission": submission_path,
    }
    record_paths = write_model_run_records(
        root=ROOT,
        output_dir=reproducibility_dir,
        experiment_id=context.experiment_id,
        issue_number=context.issue_number,
        source_commit=source_commit,
        resolved_config=resolved_config,
        metrics=metrics,
        data_files={
            "train": TRAIN_PATH,
            "test": TEST_PATH,
            "sample_submission": SAMPLE_SUBMISSION_PATH,
            "canonical_split": SPLIT_PATH,
        },
        artifacts=artifacts,
        environment={
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "xgboost": importlib.metadata.version("xgboost"),
        },
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    report_metrics_path = report_dir / "metrics.json"
    shutil.copy2(record_paths["metrics"], report_metrics_path)
    write_report(report_dir / "README.md", metrics, feature_manifest)

    comparison = verify_saved_inference(
        model_paths=output.model_paths,
        test_features=test_features,
        original_probabilities=output.test_probabilities,
        test_ids=test_meta["ID"],
        submission_path=submission_path,
        reproducibility_dir=reproducibility_dir,
        owner=owner,
        source_commit=source_commit,
    )
    manifest_path = record_paths["artifact_manifest"]
    artifact_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact_manifest.update(
        {
            "reproducibility_status": "INFERENCE_VERIFIED",
            "verifier": owner,
            "verified_at": comparison["verified_at"],
            "verification": {
                "data_hashes_match": True,
                "submission_sha256_match": comparison[
                    "submission_sha256_match"
                ],
                "test_label_agreement": comparison["test_label_agreement"],
                "probability_atol": comparison["probability_atol"],
                "probability_rtol": comparison["probability_rtol"],
                "passed": comparison["passed"],
            },
        }
    )
    write_json(manifest_path, artifact_manifest)
    write_json(reproducibility_dir / "original_metrics.json", metrics)
    write_json(
        reproducibility_dir / "reproduction_metrics.json",
        {
            "experiment_id": context.experiment_id,
            "verification_type": "checkpoint_inference",
            **comparison,
        },
    )
    (reproducibility_dir / "REPRODUCE.md").write_text(
        (
            "# EXP-156 재현 절차\n\n"
            "```bash\n"
            "uv sync --frozen\n"
            "uv run python scripts/run_exp156_gene_variant_effect_compression.py "
            "--config configs/exp156_gene_variant_effect_compression.yaml\n"
            "uv run python scripts/validate_experiment.py\n"
            "```\n"
        ),
        encoding="utf-8",
    )
    checksum_files = sorted(
        path
        for path in reproducibility_dir.iterdir()
        if path.is_file() and path.name != "checksums.sha256"
    )
    (reproducibility_dir / "checksums.sha256").write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in checksum_files),
        encoding="utf-8",
    )

    metrics_schema = ROOT / "schemas" / "metrics.schema.json"
    manifest_schema = ROOT / "schemas" / "reproducibility_manifest.schema.json"
    if metrics_schema.is_file():
        validate_json_document(report_metrics_path, metrics_schema)
    if manifest_schema.is_file():
        validate_json_document(manifest_path, manifest_schema)

    print(
        json.dumps(
            {
                "experiment_id": context.experiment_id,
                "artifact_slug": artifact_slug,
                "oof_macro_f1": metrics["oof"]["macro_f1"],
                "reproducibility_status": "INFERENCE_VERIFIED",
                "submission": relative(submission_path),
                "metrics": relative(report_metrics_path),
                "history_update_required": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / EXPECTED_CONFIG_NAME,
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_experiment(args.config)


if __name__ == "__main__":
    main()
