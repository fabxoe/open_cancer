#!/usr/bin/env python3
"""Verify EXP-476 checkpoints and write leaderboard reproducibility records."""

from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
import xgboost
import yaml
from xgboost import XGBClassifier


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_exp476_config_feature_pipeline import (  # noqa: E402
    build_stateless_features,
    combine_features,
    load_canonical_folds,
)
from open_cancer.constants import CLASS_LABELS  # noqa: E402


SLUG = "exp476_config_feature_pipeline"
REPRO_DIR = ROOT / "reproducibility" / SLUG


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def artifact(kind: str, path: Path) -> dict[str, Any]:
    return {
        "kind": kind,
        "path": path.relative_to(ROOT).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "storage_uri": None,
    }


def main() -> None:
    resolved_path = REPRO_DIR / "config.resolved.yaml"
    resolved = yaml.safe_load(resolved_path.read_text(encoding="utf-8"))
    data = resolved["data"]
    train_path = ROOT / data["train_path"]
    test_path = ROOT / data["test_path"]
    sample_path = ROOT / data["sample_submission_path"]
    split_path = ROOT / data["canonical_split_path"]

    expected_hashes = resolved["data_hashes"]
    actual_hashes = {
        "train_sha256": sha256_file(train_path),
        "test_sha256": sha256_file(test_path),
        "canonical_split_sha256": sha256_file(split_path),
    }
    data_hashes_match = actual_hashes == expected_hashes
    if not data_hashes_match:
        raise RuntimeError("EXP-476 입력 데이터 또는 canonical split 해시가 다릅니다.")

    train = pd.read_csv(train_path, dtype=str, keep_default_na=False)
    test = pd.read_csv(test_path, dtype=str, keep_default_na=False)
    id_column = data["id_column"]
    target_column = data["target_column"]
    genes = [column for column in train.columns if column not in {id_column, target_column}]
    target_map = {label: index for index, label in enumerate(CLASS_LABELS)}
    target = train[target_column].map(target_map).to_numpy(dtype=np.int32)
    folds = load_canonical_folds(resolved, train[id_column])
    gene_train, engineered_train, _ = build_stateless_features(train, genes)
    gene_test, engineered_test, _ = build_stateless_features(test, genes)

    reproduced_oof = np.zeros((len(train), len(CLASS_LABELS)), dtype=np.float32)
    reproduced_test_folds: list[np.ndarray] = []
    model_paths: list[Path] = []
    for record in resolved["runtime_folds"]:
        fold = int(record["fold"])
        selected = np.asarray(record["selected_gene_indices"], dtype=np.int32)
        panels = tuple(
            np.asarray(panel, dtype=np.int32)
            for panel in record["class_panel_gene_indices"]
        )
        valid_rows = np.flatnonzero(folds == fold)
        x_valid = combine_features(
            gene_train, engineered_train, valid_rows, selected, panels
        )
        x_test = combine_features(
            gene_test,
            engineered_test,
            np.arange(len(test), dtype=np.int32),
            selected,
            panels,
        )
        model_path = ROOT / record["model_path"]
        if sha256_file(model_path) != record["model_sha256"]:
            raise RuntimeError(f"checkpoint SHA-256 불일치: {model_path}")
        model = XGBClassifier()
        model.load_model(model_path)
        reproduced_oof[valid_rows] = model.predict_proba(x_valid).astype(np.float32)
        reproduced_test_folds.append(model.predict_proba(x_test).astype(np.float32))
        model_paths.append(model_path)

    reproduced_test = np.mean(reproduced_test_folds, axis=0)
    oof_path = ROOT / "oof" / f"{SLUG}.csv"
    test_probability_path = ROOT / "preds" / f"{SLUG}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{SLUG}.csv"
    metrics_path = ROOT / "reports" / SLUG / "metrics.json"
    original_oof = pd.read_csv(oof_path).loc[:, list(CLASS_LABELS)].to_numpy()
    original_test = (
        pd.read_csv(test_probability_path).loc[:, list(CLASS_LABELS)].to_numpy()
    )
    original_submission = pd.read_csv(submission_path, dtype=str)
    reproduced_labels = np.asarray(CLASS_LABELS)[reproduced_test.argmax(axis=1)]
    reproduced_submission = pd.DataFrame(
        {id_column: test[id_column], target_column: reproduced_labels}
    )
    reproduced_bytes = reproduced_submission.to_csv(index=False).encode("utf-8")
    reproduced_submission_sha256 = sha256(reproduced_bytes).hexdigest()

    oof_allclose = bool(
        np.allclose(original_oof, reproduced_oof, atol=1e-6, rtol=1e-6)
    )
    test_allclose = bool(
        np.allclose(original_test, reproduced_test, atol=1e-6, rtol=1e-6)
    )
    oof_label_agreement = float(
        np.mean(original_oof.argmax(axis=1) == reproduced_oof.argmax(axis=1))
    )
    test_label_agreement = float(
        np.mean(original_submission[target_column].to_numpy() == reproduced_labels)
    )
    max_abs_difference = float(
        max(
            np.max(np.abs(original_oof - reproduced_oof)),
            np.max(np.abs(original_test - reproduced_test)),
        )
    )
    submission_sha256 = sha256_file(submission_path)
    submission_sha256_match = submission_sha256 == reproduced_submission_sha256
    passed = bool(
        oof_allclose
        and test_allclose
        and oof_label_agreement == 1.0
        and test_label_agreement == 1.0
        and submission_sha256_match
    )
    if not passed:
        raise RuntimeError("EXP-476 checkpoint 추론 재현 검증에 실패했습니다.")

    verified_at = utc_now()
    source_commit = str(resolved["source"]["commit"])
    comparison = {
        "experiment_id": "EXP-476",
        "verification_type": "checkpoint_inference",
        "verified_at": verified_at,
        "data_hashes_match": data_hashes_match,
        "original_submission_sha256": submission_sha256,
        "reproduced_submission_sha256": reproduced_submission_sha256,
        "submission_sha256_match": submission_sha256_match,
        "oof_label_agreement": oof_label_agreement,
        "test_label_agreement": test_label_agreement,
        "oof_probability_allclose": oof_allclose,
        "test_probability_allclose": test_allclose,
        "probability_max_abs_difference": max_abs_difference,
        "probability_atol": 1e-6,
        "probability_rtol": 1e-6,
        "passed": passed,
    }
    comparison_path = REPRO_DIR / "comparison.json"
    write_json(comparison_path, comparison)
    reproduction_metrics_path = REPRO_DIR / "reproduction_metrics.json"
    write_json(reproduction_metrics_path, comparison)
    original_metrics_path = REPRO_DIR / "original_metrics.json"
    original_metrics_path.write_text(metrics_path.read_text(encoding="utf-8"), encoding="utf-8")
    environment_path = REPRO_DIR / "environment.json"
    write_json(
        environment_path,
        {
            "verified_at": verified_at,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "xgboost": xgboost.__version__,
        },
    )
    data_manifest_path = REPRO_DIR / "data_manifest.json"
    write_json(
        data_manifest_path,
        {
            "experiment_id": "EXP-476",
            "inputs": [
                artifact("train", train_path),
                artifact("test", test_path),
                artifact("sample_submission", sample_path),
                artifact("canonical_split", split_path),
            ],
        },
    )

    artifacts = [artifact("checkpoint", path) for path in model_paths]
    artifacts.extend(
        [
            artifact("oof_probability", oof_path),
            artifact("test_probability", test_probability_path),
            artifact("submission", submission_path),
            artifact("resolved_config", resolved_path),
            artifact("metrics", metrics_path),
        ]
    )
    artifact_manifest_path = REPRO_DIR / "artifact_manifest.json"
    write_json(
        artifact_manifest_path,
        {
            "experiment_id": "EXP-476",
            "issue_number": 476,
            "reproducibility_status": "INFERENCE_VERIFIED",
            "source_commit": source_commit,
            "source_tag": None,
            "dirty_worktree": False,
            "data_manifest": data_manifest_path.relative_to(ROOT).as_posix(),
            "environment": environment_path.relative_to(ROOT).as_posix(),
            "release_url": None,
            "verifier": "Gomin-art",
            "verified_at": verified_at,
            "verification": {
                "data_hashes_match": data_hashes_match,
                "submission_sha256_match": submission_sha256_match,
                "oof_label_agreement": oof_label_agreement,
                "test_label_agreement": test_label_agreement,
                "probability_atol": 1e-6,
                "probability_rtol": 1e-6,
                "passed": passed,
            },
            "artifacts": artifacts,
        },
    )
    reproduce_path = REPRO_DIR / "REPRODUCE.md"
    reproduce_path.write_text(
        "# EXP-476 재현 절차\n\n"
        "```bash\n"
        "uv sync --frozen\n"
        "uv run python scripts/verify_exp476_inference.py\n"
        "```\n\n"
        "원본 CSV 해시와 canonical split을 확인한 뒤 저장된 fold checkpoint로 "
        "OOF/test 추론을 재생성해 확률·라벨·제출 SHA-256을 비교합니다.\n",
        encoding="utf-8",
    )
    checksum_paths = [
        comparison_path,
        reproduction_metrics_path,
        original_metrics_path,
        environment_path,
        data_manifest_path,
        resolved_path,
        reproduce_path,
    ]
    (REPRO_DIR / "checksums.sha256").write_text(
        "".join(
            f"{sha256_file(path)}  {path.relative_to(REPRO_DIR).as_posix()}\n"
            for path in checksum_paths
        ),
        encoding="utf-8",
    )
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
