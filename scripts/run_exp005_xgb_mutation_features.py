#!/usr/bin/env python
"""Run EXP-005: XGBoost with sparse gene-by-mutation-type features."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from html import escape
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
    CO_MUTATION_PAIRS,
    build_mutation_features,
    co_mutation_feature_names,
    resolve_position_features_from_config,
    resolve_position_options_from_config,
)
from open_cancer.paths import relative_posix
from open_cancer.validation import validate_json_document, validate_submission


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "exp005_xgb_mutation_features.yaml"
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
SAMPLE_SUBMISSION_PATH = ROOT / "data" / "raw" / "sample_submission.csv"
FEATURE_DIR = ROOT / "data" / "processed" / "mutation_type_features"


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


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": relative_posix(path, ROOT),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def resolve_position_features(config: dict[str, Any]) -> tuple[str, ...]:
    """Resolve the config-facing aggregate names to factory feature names."""
    return resolve_position_features_from_config(config)


def resolve_position_options(config: dict[str, Any]) -> dict[str, Any]:
    """Return validated Feature Factory options while preserving EXP-047 defaults."""
    return resolve_position_options_from_config(config)


def resolve_co_mutation_pairs(config: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """Resolve the config-facing pair list to validated factory gene pairs."""

    families = config.get("features", {})
    co_mutation = families.get("co_mutation", {"enabled": False})
    if not co_mutation.get("enabled", False):
        return ()

    pairs = tuple(tuple(pair) for pair in co_mutation.get("pairs", []))
    if not pairs:
        raise ValueError("co_mutation을 활성화하면 pairs를 하나 이상 지정해야 합니다.")
    if len(set(pairs)) != len(pairs):
        raise ValueError("co_mutation pair가 중복됐습니다.")
    invalid = sorted(set(pairs) - set(CO_MUTATION_PAIRS))
    if invalid:
        raise ValueError(f"Feature Factory가 지원하지 않는 co-mutation pair입니다: {invalid}")
    return pairs


def write_local_dashboard(
    *,
    artifact_slug: str,
    metrics: dict[str, Any],
    feature_dir: Path,
    highlighted_features: tuple[str, ...],
    comparison_metrics_path: Path | None,
) -> Path:
    """Write a local-only HTML summary for people who do not use notebooks."""
    output_path = ROOT / "reports" / "local" / artifact_slug / "dashboard.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    comparison = None
    if comparison_metrics_path is not None and comparison_metrics_path.is_file():
        comparison = json.loads(comparison_metrics_path.read_text(encoding="utf-8"))

    names = json.loads(
        (feature_dir / "feature_names.json").read_text(encoding="utf-8")
    )
    train_features = sparse.load_npz(feature_dir / "train_features.npz")
    test_features = sparse.load_npz(feature_dir / "test_features.npz")
    feature_rows: list[dict[str, Any]] = []
    for name in highlighted_features:
        index = names.index(name)
        train_values = train_features[:, index].toarray().ravel()
        test_values = test_features[:, index].toarray().ravel()
        feature_rows.append(
            {
                "피처": name,
                "train 평균": float(train_values.mean()),
                "train 중앙값": float(np.median(train_values)),
                "train 표준편차": float(train_values.std()),
                "test 평균": float(test_values.mean()),
                "test 중앙값": float(np.median(test_values)),
                "test 표준편차": float(test_values.std()),
            }
        )

    fold_rows = "".join(
        (
            "<tr>"
            f"<td>{fold['fold']}</td>"
            f"<td>{fold['macro_f1']:.6f}</td>"
            "<td><div class='bar-wrap'>"
            f"<div class='bar' style='width:{fold['macro_f1'] * 100:.2f}%'></div>"
            "</div></td>"
            f"<td>{fold['accuracy']:.6f}</td>"
            f"<td>{fold['log_loss']:.6f}</td>"
            "</tr>"
        )
        for fold in metrics["folds"]
    )
    comparison_html = "<p>비교 실험 metrics를 찾지 못했습니다.</p>"
    if comparison is not None:
        current = metrics["oof"]["macro_f1"]
        parent = comparison["oof"]["macro_f1"]
        comparison_html = (
            "<table><thead><tr><th>실험</th><th>OOF Macro F1</th>"
            "<th>fold 표준편차</th></tr></thead><tbody>"
            f"<tr><td>{escape(comparison['experiment_id'])}</td>"
            f"<td>{parent:.10f}</td>"
            f"<td>{comparison['oof']['fold_std']:.10f}</td></tr>"
            f"<tr><td>{escape(metrics['experiment_id'])}</td>"
            f"<td>{current:.10f}</td>"
            f"<td>{metrics['oof']['fold_std']:.10f}</td></tr>"
            f"<tr><td>차이</td><td>{current - parent:+.10f}</td>"
            f"<td>{metrics['oof']['fold_std'] - comparison['oof']['fold_std']:+.10f}</td></tr>"
            "</tbody></table>"
        )

    feature_table = pd.DataFrame(feature_rows).to_html(
        index=False, float_format=lambda value: f"{value:.6f}", border=0
    )
    class_table = (
        pd.Series(metrics["oof"]["per_class_f1"], name="F1")
        .sort_values(ascending=False)
        .rename_axis("암종")
        .reset_index()
        .to_html(index=False, float_format=lambda value: f"{value:.6f}", border=0)
    )
    html = f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(metrics["experiment_id"])} 내부 검증</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  max-width: 1100px; margin: 36px auto; padding: 0 20px; color: #17212b; }}
h1, h2 {{ color: #183b56; }} .cards {{ display: flex; gap: 14px; flex-wrap: wrap; }}
.card {{ background: #f4f7fa; border-radius: 10px; padding: 16px 20px; min-width: 190px; }}
.value {{ font-size: 1.5rem; font-weight: 700; margin-top: 6px; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0 28px; }}
th, td {{ border-bottom: 1px solid #dde4ea; padding: 9px; text-align: right; }}
th:first-child, td:first-child {{ text-align: left; }}
.bar-wrap {{ width: 100%; min-width: 220px; background: #e7edf2; border-radius: 4px; }}
.bar {{ height: 14px; background: #2a7de1; border-radius: 4px; }}
.note {{ background: #fff7df; padding: 12px 16px; border-radius: 8px; }}
</style>
</head>
<body>
<h1>{escape(metrics["experiment_id"])} 내부 검증 대시보드</h1>
<p class="note">이 파일은 로컬 확인용이며 Git에 커밋되지 않습니다.
Public leaderboard 점수는 포함하지 않습니다.</p>
<div class="cards">
  <div class="card">OOF Macro F1<div class="value">{metrics["oof"]["macro_f1"]:.6f}</div></div>
  <div class="card">fold 평균<div class="value">{metrics["oof"]["fold_mean"]:.6f}</div></div>
  <div class="card">fold 표준편차<div class="value">{metrics["oof"]["fold_std"]:.6f}</div></div>
  <div class="card">Accuracy<div class="value">{metrics["oof"]["accuracy"]:.6f}</div></div>
</div>
<h2>부모 실험 비교</h2>
{comparison_html}
<h2>fold별 성능</h2>
<table><thead><tr><th>fold</th><th>Macro F1</th><th>시각화</th>
<th>Accuracy</th><th>Log Loss</th></tr></thead><tbody>{fold_rows}</tbody></table>
<h2>추가 피처 train/test 분포</h2>
{feature_table}
<h2>암종별 F1</h2>
{class_table}
</body></html>
"""
    output_path.write_text(html, encoding="utf-8")
    return output_path


def verify_saved_inference(
    *,
    context: Any,
    source_commit: str,
    owner: str,
    artifact_slug: str,
    config: dict[str, Any],
    resolved_config: dict[str, Any],
    resolved_config_path: Path,
    metrics: dict[str, Any],
    metrics_path: Path,
    model_dir: Path,
    oof_path: Path,
    reproducibility_dir: Path,
    test_features: sparse.csr_matrix,
    test_ids: pd.Series,
    test_probability_path: Path,
    submission_path: Path,
    fold_feature_indices: list[list[int]] | None = None,
) -> None:
    """Reload checkpoints and automatically create inference reproducibility evidence."""
    fold_count = config["split"]["n_splits"]
    reproduced_proba = np.zeros(
        (len(test_ids), len(CLASS_LABELS)), dtype=np.float32
    )
    model_paths = [
        model_dir / f"fold_{fold:02d}.json" for fold in range(fold_count)
    ]
    for fold, model_path in enumerate(model_paths):
        if not model_path.is_file():
            raise FileNotFoundError(f"체크포인트가 없습니다: {model_path}")
        model = xgb.XGBClassifier()
        model.load_model(model_path)
        fold_test_features = (
            test_features[:, fold_feature_indices[fold]]
            if fold_feature_indices is not None
            else test_features
        )
        reproduced_proba += model.predict_proba(fold_test_features).astype(
            np.float32
        ) / fold_count

    original_probability = pd.read_csv(test_probability_path)
    original_proba = original_probability[list(PROBABILITY_COLUMNS)].to_numpy()
    probability_match = bool(
        np.allclose(reproduced_proba, original_proba, atol=1e-6, rtol=1e-6)
    )
    probability_max_abs_diff = float(
        np.max(np.abs(reproduced_proba - original_proba))
    )

    sample_submission = pd.read_csv(
        SAMPLE_SUBMISSION_PATH, dtype=str, keep_default_na=False
    )
    reproduced_submission = sample_submission.copy()
    reproduced_submission["SUBCLASS"] = np.asarray(CLASS_LABELS)[
        reproduced_proba.argmax(axis=1)
    ]
    with tempfile.TemporaryDirectory(
        prefix=f"{artifact_slug}_inference_"
    ) as temporary:
        reproduced_path = Path(temporary) / submission_path.name
        reproduced_submission.to_csv(
            reproduced_path, index=False, lineterminator="\n"
        )
        validate_submission(reproduced_path, TEST_PATH)
        reproduced_sha = sha256_file(reproduced_path)

    original_submission = pd.read_csv(submission_path, dtype=str)
    original_sha = sha256_file(submission_path)
    submission_sha_match = bool(
        reproduced_sha
        == original_sha
        == metrics["artifacts"]["submission_sha256"]
    )
    test_label_agreement = float(
        (
            reproduced_submission["SUBCLASS"]
            == original_submission["SUBCLASS"]
        ).mean()
    )

    hash_records = [
        (
            ROOT / resolved_config["data"]["train"]["path"],
            resolved_config["data"]["train"]["sha256"],
        ),
        (
            ROOT / resolved_config["data"]["test"]["path"],
            resolved_config["data"]["test"]["sha256"],
        ),
        (
            ROOT / resolved_config["data"]["sample_submission"]["path"],
            resolved_config["data"]["sample_submission"]["sha256"],
        ),
        (
            ROOT / resolved_config["split"]["path"],
            resolved_config["split"]["sha256"],
        ),
        *[
            (ROOT / metadata["path"], metadata["sha256"])
            for metadata in resolved_config["feature_outputs"].values()
        ],
    ]
    data_hashes_match = all(
        path.is_file() and sha256_file(path) == expected
        for path, expected in hash_records
    )
    passed = bool(
        data_hashes_match
        and probability_match
        and submission_sha_match
        and test_label_agreement == 1.0
    )
    if not passed:
        raise ValueError(
            "저장 체크포인트 추론이 원본 확률 또는 제출 파일과 일치하지 않습니다."
        )

    verified_at = datetime.now(timezone.utc).isoformat()
    environment_path = reproducibility_dir / "environment.json"
    data_manifest_path = reproducibility_dir / "data_manifest.json"
    original_metrics_path = reproducibility_dir / "original_metrics.json"
    reproduction_metrics_path = reproducibility_dir / "reproduction_metrics.json"
    comparison_path = reproducibility_dir / "comparison.json"
    manifest_path = reproducibility_dir / "artifact_manifest.json"
    reproduce_path = reproducibility_dir / "REPRODUCE.md"

    write_json(
        environment_path,
        {
            "verified_at": verified_at,
            **resolved_config["environment"],
        },
    )
    write_json(
        data_manifest_path,
        {
            "verified_at": verified_at,
            "files": [
                {**file_record(path), "expected_sha256": expected}
                for path, expected in hash_records
            ],
        },
    )
    write_json(original_metrics_path, metrics)
    comparison = {
        "verified_at": verified_at,
        "data_hashes_match": data_hashes_match,
        "original_submission_sha256": original_sha,
        "reproduced_submission_sha256": reproduced_sha,
        "submission_sha256_match": submission_sha_match,
        "test_label_agreement": test_label_agreement,
        "test_probability_allclose": probability_match,
        "test_probability_max_abs_diff": probability_max_abs_diff,
        "probability_atol": 1e-6,
        "probability_rtol": 1e-6,
        "passed": passed,
    }
    write_json(comparison_path, comparison)
    write_json(
        reproduction_metrics_path,
        {
            "experiment_id": context.experiment_id,
            "verification_type": "checkpoint_inference",
            **comparison,
        },
    )
    reproduce_path.write_text(
        (
            f"# {context.experiment_id} 재현 절차\n\n"
            "원본 CSV를 `data/raw/`에 배치하고 다음 명령을 실행합니다.\n\n"
            "```bash\n"
            "uv sync --frozen\n"
            f"uv run python scripts/run_{artifact_slug}.py\n"
            "uv run python scripts/validate_experiment.py\n"
            "```\n\n"
            "실험 실행 마지막 단계에서 저장 checkpoint 추론과 제출 SHA-256 "
            "일치 검증이 자동 수행됩니다.\n"
        ),
        encoding="utf-8",
    )

    artifacts = [
        {"kind": "checkpoint", **file_record(path), "storage_uri": None}
        for path in model_paths
    ]
    artifacts.extend(
        [
            {"kind": "submission", **file_record(submission_path), "storage_uri": None},
            {
                "kind": "oof_probability",
                **file_record(oof_path),
                "storage_uri": None,
            },
            {
                "kind": "test_probability",
                **file_record(test_probability_path),
                "storage_uri": None,
            },
            {"kind": "metrics", **file_record(metrics_path), "storage_uri": None},
            {
                "kind": "resolved_config",
                **file_record(resolved_config_path),
                "storage_uri": None,
            },
        ]
    )
    manifest = {
        "experiment_id": context.experiment_id,
        "issue_number": context.issue_number,
        "reproducibility_status": "INFERENCE_VERIFIED",
        "source_commit": source_commit,
        "source_tag": None,
        "dirty_worktree": False,
        "data_manifest": relative_posix(data_manifest_path, ROOT),
        "environment": relative_posix(environment_path, ROOT),
        "release_url": None,
        "verifier": owner,
        "verified_at": verified_at,
        "artifacts": artifacts,
        "verification": {
            "data_hashes_match": data_hashes_match,
            "submission_sha256_match": submission_sha_match,
            "test_label_agreement": test_label_agreement,
            "probability_atol": 1e-6,
            "probability_rtol": 1e-6,
            "passed": passed,
        },
    }
    write_json(manifest_path, manifest)
    validate_json_document(
        manifest_path, ROOT / "schemas" / "reproducibility_manifest.schema.json"
    )

    checksum_paths = [
        resolved_config_path,
        environment_path,
        data_manifest_path,
        original_metrics_path,
        reproduction_metrics_path,
        comparison_path,
        reproduce_path,
    ]
    (reproducibility_dir / "checksums.sha256").write_text(
        "".join(
            f"{sha256_file(path)}  {path.name}\n" for path in checksum_paths
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "reproducibility_status": "INFERENCE_VERIFIED",
                "comparison": comparison,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def run_experiment(
    *,
    config_path: Path,
    expected_issue_number: int,
    artifact_slug: str,
    feature_dir: Path,
    include_robust_aggregates: bool,
    parent_experiment: str | None,
    notes: str,
    selected_robust_aggregates: tuple[str, ...] | None = None,
    comparison_metrics_path: Path | None = None,
    fold_feature_selector: Any | None = None,
    candidate_feature_groups: dict[str, tuple[str, ...]] | None = None,
) -> None:
    started_at = datetime.now(timezone.utc)
    start_time = time.perf_counter()
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    selected_position_features = resolve_position_features(config)
    position_options = resolve_position_options(config)
    selected_co_mutation_pairs = resolve_co_mutation_pairs(config)
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    expected_experiment_id = f"EXP-{expected_issue_number:03d}"
    if (
        context.experiment_id != expected_experiment_id
        or context.issue_number != expected_issue_number
    ):
        raise ValueError(
            f"이 script는 Issue #{expected_issue_number} 브랜치의 "
            f"{expected_experiment_id} 전용입니다."
        )

    split_path = ROOT / config["split"]["path"]
    report_dir = ROOT / "reports" / artifact_slug
    model_dir = ROOT / "models" / artifact_slug
    oof_path = ROOT / "oof" / f"{artifact_slug}.csv"
    test_probability_path = ROOT / "preds" / f"{artifact_slug}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{artifact_slug}.csv"
    reproducibility_dir = ROOT / "reproducibility" / artifact_slug
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
    dirty_status = run_git("status", "--porcelain")
    dirty_worktree = bool(dirty_status)
    if dirty_worktree:
        raise RuntimeError(
            "공식 실험은 clean worktree에서만 실행할 수 있습니다. "
            "변경을 commit/stash한 뒤 다시 실행하세요.\n"
            f"{dirty_status}"
        )
    owner = run_git("config", "user.name") or os.environ.get("USER", "unknown")
    feature_report = build_mutation_features(
        TRAIN_PATH,
        TEST_PATH,
        feature_dir,
        include_robust_aggregates=include_robust_aggregates,
        selected_robust_aggregates=selected_robust_aggregates,
        selected_position_features=selected_position_features,
        selected_co_mutation_pairs=selected_co_mutation_pairs,
        **position_options,
    )

    train_meta = pd.read_csv(TRAIN_PATH, usecols=["ID", "SUBCLASS"], dtype=str)
    test_meta = pd.read_csv(TEST_PATH, usecols=["ID"], dtype=str)
    sample_submission = pd.read_csv(SAMPLE_SUBMISSION_PATH, dtype=str, keep_default_na=False)
    folds = pd.read_csv(split_path, dtype={"ID": str, "fold": int})
    train = train_meta.merge(folds, on="ID", how="left", validate="one_to_one", sort=False)
    if not train["ID"].equals(train_meta["ID"]):
        raise ValueError("fold 병합 과정에서 train 순서가 변경됐습니다.")

    x_all = sparse.load_npz(feature_dir / "train_features.npz")
    x_test = sparse.load_npz(feature_dir / "test_features.npz")
    all_feature_names = json.loads(
        (feature_dir / "feature_names.json").read_text(encoding="utf-8")
    )
    feature_train_ids = pd.read_csv(feature_dir / "train_ids.csv", dtype=str)["ID"]
    feature_test_ids = pd.read_csv(feature_dir / "test_ids.csv", dtype=str)["ID"]
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
            "issue_number": context.issue_number,
            "experiment_id": context.experiment_id,
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
            "requested_families": config.get(
                "features",
                {
                    "mutation_type": {"enabled": True},
                    "residue_position": {"enabled": False},
                },
            ),
        },
        "feature_registry": feature_report["feature_registry"],
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
            "feature_selection": config.get("selection"),
            "fold_seeds": [config["seed"] + fold for fold in range(config["split"]["n_splits"])],
            "command": f"uv run python scripts/run_{artifact_slug}.py",
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
    fold_feature_indices: list[list[int]] = []
    selection_results: list[dict[str, Any]] = []

    for fold in range(n_splits):
        valid_mask = train["fold"].eq(fold).to_numpy()
        train_indices = np.flatnonzero(~valid_mask)
        valid_indices = np.flatnonzero(valid_mask)
        y_train = y[train_indices]
        y_valid = y[valid_indices]
        if fold_feature_selector is not None:
            if not candidate_feature_groups or "selection" not in config:
                raise ValueError(
                    "fold feature selector에는 candidate groups와 selection config가 필요합니다."
                )
            selected_indices, selection_result = fold_feature_selector(
                matrix=x_all,
                labels=y,
                outer_train_indices=train_indices,
                feature_names=all_feature_names,
                candidate_groups=candidate_feature_groups,
                model_params=model_params,
                seed=config["seed"] + fold * 100,
                inner_splits=config["selection"]["inner_splits"],
                minimum_positive_folds=config["selection"][
                    "minimum_positive_folds"
                ],
                balanced_sample_weight=config["training"][
                    "balanced_sample_weight"
                ],
            )
        else:
            selected_indices = list(range(x_all.shape[1]))
            selection_result = {
                "selected_groups": [],
                "selected_features": [],
            }
        fold_feature_indices.append(selected_indices)
        selection_results.append({"outer_fold": fold, **selection_result})
        x_train_fold = x_all[train_indices][:, selected_indices]
        x_valid_fold = x_all[valid_indices][:, selected_indices]
        x_test_fold = x_test[:, selected_indices]
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

    selection_path = report_dir / "feature_selection.json"
    if fold_feature_selector is not None:
        write_json(
            selection_path,
            {
                "method": config["selection"]["method"],
                "candidate_groups": {
                    group: list(names)
                    for group, names in (candidate_feature_groups or {}).items()
                },
                "outer_folds": selection_results,
            },
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
        "status": "COMPLETED",
        "owner": owner,
        "issue_number": context.issue_number,
        "parent_experiment": parent_experiment,
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
            "feature_selection": (
                relative_posix(selection_path, ROOT)
                if fold_feature_selector is not None
                else None
            ),
        },
        "notes": notes,
    }
    write_json(metrics_path, metrics)
    validate_json_document(metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json")
    try:
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
            fold_feature_indices=(
                fold_feature_indices if fold_feature_selector is not None else None
            ),
        )
    except Exception as error:
        metrics["status"] = "FAILED"
        metrics["notes"] = (
            f"{notes} Automatic checkpoint inference verification failed: {error}"
        )
        write_json(metrics_path, metrics)
        validate_json_document(
            metrics_path, ROOT / "schemas" / "experiment_metrics.schema.json"
        )
        raise
    local_dashboard_path = write_local_dashboard(
        artifact_slug=artifact_slug,
        metrics=metrics,
        feature_dir=feature_dir,
        highlighted_features=(
            *(selected_robust_aggregates or ()),
            *co_mutation_feature_names(selected_co_mutation_pairs),
        ),
        comparison_metrics_path=comparison_metrics_path,
    )
    print(
        json.dumps(
            {
                "local_dashboard": str(local_dashboard_path),
                "open_command": f"open {local_dashboard_path}",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(json.dumps({"metrics": str(metrics_path), "oof": metrics["oof"]}, ensure_ascii=False, indent=2))


def main() -> None:
    run_experiment(
        config_path=CONFIG_PATH,
        expected_issue_number=5,
        artifact_slug="exp005_xgb_mutation_features",
        feature_dir=FEATURE_DIR,
        include_robust_aggregates=False,
        parent_experiment=None,
        notes="Sparse gene-by-mutation-type features; no target-derived features.",
    )


if __name__ == "__main__":
    main()
