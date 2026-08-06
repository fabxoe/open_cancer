#!/usr/bin/env python
"""Run EXP-611: EXP-571 Parser QC plus event-span combined ablation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import run_exp449_lightgbm_exp374 as runner
import yaml
from exp611_parser_v4_qc_event_span_combined_features import (
    build_combined_features,
)
from open_cancer.hashing import sha256_file
from open_cancer.validation import validate_json_document


EXPECTED_EXPERIMENT_ID = "EXP-611"
ISSUE_NUMBER = 611
SLUG = "exp611_parser_v4_qc_event_span_combined"
CONFIG_PATH = runner.ROOT / "configs/exp611_parser_v4_qc_event_span_combined.yaml"
RUNNER_COMMAND = (
    "uv run python scripts/run_exp611_parser_v4_qc_event_span_combined.py"
)
ALLOWED_VERIFICATION_FIELDS = (
    "data_hashes_match",
    "submission_sha256_match",
    "oof_label_agreement",
    "test_label_agreement",
    "probability_atol",
    "probability_rtol",
    "oof_macro_f1_delta",
    "passed",
)


def artifact_record(kind: str, path: Path) -> dict[str, Any]:
    return {
        "kind": kind,
        "path": path.relative_to(runner.ROOT).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "storage_uri": None,
    }


def repair_reproducibility_manifest() -> Path:
    """Convert the inherited legacy LightGBM manifest to the current schema."""
    reproducibility_dir = runner.ROOT / "reproducibility" / SLUG
    manifest_path = reproducibility_dir / "artifact_manifest.json"
    comparison_path = reproducibility_dir / "comparison.json"
    resolved_config_path = reproducibility_dir / "config.resolved.yaml"
    required_paths = (manifest_path, comparison_path, resolved_config_path)
    for path in required_paths:
        if not path.is_file():
            raise FileNotFoundError(f"재현성 입력 파일이 없습니다: {path}")

    legacy_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    resolved_config = yaml.safe_load(
        resolved_config_path.read_text(encoding="utf-8")
    )
    data_paths = (
        ("train", runner.ROOT / "data/raw/train.csv"),
        ("test", runner.ROOT / "data/raw/test.csv"),
        (
            "sample_submission",
            runner.ROOT / "data/raw/sample_submission.csv",
        ),
        (
            "split",
            runner.ROOT / "data/splits/stratified_5fold_seed42.csv",
        ),
    )
    for _kind, path in data_paths:
        if not path.is_file():
            raise FileNotFoundError(f"데이터 입력 파일이 없습니다: {path}")

    data_manifest_path = reproducibility_dir / "data_manifest.json"
    runner.write_json(
        data_manifest_path,
        {
            "experiment_id": EXPECTED_EXPERIMENT_ID,
            "files": [
                {
                    "kind": kind,
                    "path": path.relative_to(runner.ROOT).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
                for kind, path in data_paths
            ],
        },
    )
    environment_path = reproducibility_dir / "environment.json"
    environment = resolved_config.get("environment", {})
    runner.write_json(
        environment_path,
        {
            "python": str(environment.get("python", "unknown")),
            "platform": str(environment.get("platform", "unknown")),
        },
    )

    candidates: list[tuple[str, Path]] = [
        ("checkpoint", path)
        for path in sorted((runner.ROOT / "models" / SLUG).glob("fold_*.txt"))
    ]
    candidates.extend(
        (
            ("oof_probability", runner.ROOT / "oof" / f"{SLUG}.csv"),
            (
                "test_probability",
                runner.ROOT / "preds" / f"{SLUG}_test_proba.csv",
            ),
            ("submission", runner.ROOT / "submissions" / f"{SLUG}.csv"),
            ("metrics", runner.ROOT / "reports" / SLUG / "metrics.json"),
            ("resolved_config", resolved_config_path),
        )
    )
    artifacts = [
        artifact_record(kind, path)
        for kind, path in candidates
        if path.is_file()
    ]
    observed_kinds = {artifact["kind"] for artifact in artifacts}
    required_kinds = {"submission", "metrics", "resolved_config"}
    if not required_kinds <= observed_kinds:
        missing = sorted(required_kinds - observed_kinds)
        raise FileNotFoundError("필수 재현 산출물 누락: " + ", ".join(missing))

    verification = {
        field: comparison[field]
        for field in ALLOWED_VERIFICATION_FIELDS
        if field in comparison
    }
    required_verification = {
        "data_hashes_match",
        "submission_sha256_match",
        "passed",
    }
    if not required_verification <= verification.keys():
        missing = sorted(required_verification - verification.keys())
        raise ValueError("필수 재현 검증값 누락: " + ", ".join(missing))

    manifest = {
        "experiment_id": EXPECTED_EXPERIMENT_ID,
        "issue_number": ISSUE_NUMBER,
        "reproducibility_status": legacy_manifest[
            "reproducibility_status"
        ],
        "source_commit": legacy_manifest["source_commit"],
        "source_tag": None,
        "dirty_worktree": False,
        "data_manifest": data_manifest_path.relative_to(runner.ROOT).as_posix(),
        "environment": environment_path.relative_to(runner.ROOT).as_posix(),
        "release_url": None,
        "verifier": str(legacy_manifest.get("verifier", "Gomin-art")),
        "verified_at": legacy_manifest.get("verified_at"),
        "artifacts": artifacts,
        "verification": verification,
    }
    runner.write_json(manifest_path, manifest)
    validate_json_document(
        manifest_path,
        runner.ROOT / "schemas/reproducibility_manifest.schema.json",
    )
    return manifest_path


def write_parent_comparison(config: dict[str, Any]) -> Path:
    metrics_path = runner.ROOT / "reports" / SLUG / "metrics.json"
    parent_path = runner.ROOT / str(config["comparison_metrics_path"])
    if not metrics_path.is_file() or not parent_path.is_file():
        raise FileNotFoundError("EXP-611 또는 EXP-571 비교 metrics가 없습니다.")
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    current_oof = metrics["oof"]
    parent_oof = parent["oof"]
    per_class_delta = {
        label: float(current_oof["per_class_f1"][label])
        - float(parent_oof["per_class_f1"][label])
        for label in sorted(parent_oof["per_class_f1"])
    }
    deltas = {
        "macro_f1": float(current_oof["macro_f1"])
        - float(parent_oof["macro_f1"]),
        "accuracy": float(current_oof["accuracy"])
        - float(parent_oof["accuracy"]),
        "log_loss": float(current_oof["log_loss"])
        - float(parent_oof["log_loss"]),
        "fold_std": float(current_oof["fold_std"])
        - float(parent_oof["fold_std"]),
    }
    acceptance = config["acceptance"]
    gates = {
        "macro_f1_non_decreasing": deltas["macro_f1"]
        >= float(acceptance["minimum_macro_f1_delta"]),
        "macro_f1_recommended_gain": deltas["macro_f1"]
        >= float(acceptance["recommended_macro_f1_delta"]),
        "accuracy_gate": deltas["accuracy"]
        >= float(acceptance["minimum_accuracy_delta"]),
        "log_loss_gate": deltas["log_loss"]
        <= float(acceptance["maximum_log_loss_delta"]),
        "fold_std_gate": deltas["fold_std"]
        <= float(acceptance["maximum_fold_std_delta"]),
        "per_class_f1_gate": min(per_class_delta.values())
        >= float(acceptance["minimum_per_class_f1_delta"]),
    }
    adopted = all(
        value
        for key, value in gates.items()
        if key != "macro_f1_recommended_gain"
    )
    output = {
        "experiment_id": EXPECTED_EXPERIMENT_ID,
        "parent_experiment": "EXP-571",
        "parent_arm": "parser_qc",
        "parent_metrics": str(parent_path.relative_to(runner.ROOT)),
        "current_metrics": str(metrics_path.relative_to(runner.ROOT)),
        "deltas": deltas,
        "per_class_f1_delta": per_class_delta,
        "worst_class": min(per_class_delta, key=per_class_delta.get),
        "worst_class_f1_delta": min(per_class_delta.values()),
        "gates": gates,
        "decision": "ADOPT" if adopted else "REJECT",
    }
    output_path = runner.ROOT / "reports" / SLUG / "parent_comparison.json"
    runner.write_json(output_path, output)
    return output_path


def main() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    runner.CONFIG_PATH = CONFIG_PATH
    runner.SLUG = SLUG
    runner.FOLD_BUILDER_FACTORY = build_combined_features
    runner.RUNNER_COMMAND = RUNNER_COMMAND
    runner.main()
    manifest_path = repair_reproducibility_manifest()
    comparison_path = write_parent_comparison(config)
    print(
        json.dumps(
            {
                "experiment_id": EXPECTED_EXPERIMENT_ID,
                "manifest": str(manifest_path.relative_to(runner.ROOT)),
                "parent_comparison": str(
                    comparison_path.relative_to(runner.ROOT)
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
