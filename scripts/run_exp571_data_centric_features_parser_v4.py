#!/usr/bin/env python
"""Run EXP-571 Base/A/B on the fixed EXP-567 LightGBM parent."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import run_exp449_lightgbm_exp374 as runner
import yaml
from exp527_lightgbm_ablation_builders import build_parser_plus_cosine_features
from exp571_data_centric_feature_builders import (
    build_event_span_features,
    build_parser_qc_features,
)


EXPECTED_EXPERIMENT_ID = "EXP-571"
CONFIG_PATH = runner.ROOT / "configs/exp571_data_centric_features_parser_v4.yaml"
RUNNER_COMMAND = (
    "uv run python scripts/run_exp571_data_centric_features_parser_v4.py"
)

ARMS = (
    ("base", build_parser_plus_cosine_features),
    ("parser_qc", build_parser_qc_features),
    ("event_span", build_event_span_features),
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


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest of a local artifact."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact_record(kind: str, path: Path) -> dict[str, Any]:
    """Build one current-schema artifact entry."""
    return {
        "kind": kind,
        "path": path.relative_to(runner.ROOT).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "storage_uri": None,
    }


def repair_reproducibility_manifest(slug: str) -> Path:
    """Upgrade the legacy LightGBM manifest without retraining the model."""
    reproducibility_dir = runner.ROOT / "reproducibility" / slug
    manifest_path = reproducibility_dir / "artifact_manifest.json"
    comparison_path = reproducibility_dir / "comparison.json"
    resolved_config_path = reproducibility_dir / "config.resolved.yaml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifest가 없습니다: {manifest_path}")
    if not comparison_path.is_file():
        raise FileNotFoundError(f"comparison이 없습니다: {comparison_path}")
    if not resolved_config_path.is_file():
        raise FileNotFoundError(
            f"resolved config가 없습니다: {resolved_config_path}"
        )

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
            raise FileNotFoundError(f"데이터 manifest 입력이 없습니다: {path}")

    data_manifest_path = reproducibility_dir / "data_manifest.json"
    data_manifest = {
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
    }
    runner.write_json(data_manifest_path, data_manifest)

    environment_path = reproducibility_dir / "environment.json"
    environment = resolved_config.get("environment", {})
    runner.write_json(
        environment_path,
        {
            "python": str(environment.get("python", "unknown")),
            "platform": str(environment.get("platform", "unknown")),
        },
    )

    artifact_candidates: list[tuple[str, Path]] = []
    artifact_candidates.extend(
        ("checkpoint", path)
        for path in sorted((runner.ROOT / "models" / slug).glob("fold_*.txt"))
    )
    artifact_candidates.extend(
        (
            ("oof_probability", runner.ROOT / "oof" / f"{slug}.csv"),
            (
                "test_probability",
                runner.ROOT / "preds" / f"{slug}_test_proba.csv",
            ),
            ("submission", runner.ROOT / "submissions" / f"{slug}.csv"),
            ("metrics", runner.ROOT / "reports" / slug / "metrics.json"),
            ("resolved_config", resolved_config_path),
        )
    )
    artifacts = [
        artifact_record(kind, path)
        for kind, path in artifact_candidates
        if path.is_file()
    ]
    required_kinds = {"submission", "metrics", "resolved_config"}
    observed_kinds = {artifact["kind"] for artifact in artifacts}
    missing_kinds = required_kinds - observed_kinds
    if missing_kinds:
        raise FileNotFoundError(
            "필수 재현 산출물이 없습니다: " + ", ".join(sorted(missing_kinds))
        )

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
    missing_verification = required_verification - verification.keys()
    if missing_verification:
        raise ValueError(
            "comparison 필수 검증값이 없습니다: "
            + ", ".join(sorted(missing_verification))
        )

    manifest = {
        "experiment_id": EXPECTED_EXPERIMENT_ID,
        "issue_number": 571,
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
    runner.validate_json_document(
        manifest_path,
        runner.ROOT / "schemas/reproducibility_manifest.schema.json",
    )
    return manifest_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repair-reproducibility-only",
        action="store_true",
        help="기존 EXP-571 산출물의 manifest만 최신 schema로 복구합니다.",
    )
    return parser.parse_args()


def main(*, repair_reproducibility_only: bool = False) -> None:
    if repair_reproducibility_only:
        repaired = []
        for arm_name, _factory in ARMS:
            slug = f"exp571_data_centric_features_parser_v4_{arm_name}"
            repaired.append(str(repair_reproducibility_manifest(slug)))
        print(json.dumps({"repaired_manifests": repaired}, ensure_ascii=False))
        return

    # Enforce the official clean-worktree rule once. Outputs produced by an earlier
    # arm are expected and must not invalidate later arms in the same process.
    initial_dirty = runner.git("status", "--porcelain")
    if initial_dirty:
        raise RuntimeError(
            f"{EXPECTED_EXPERIMENT_ID}는 clean worktree에서만 실행해야 합니다.\n"
            + initial_dirty
        )
    original_git = runner.git

    def experiment_git(*args: str) -> str:
        if args == ("status", "--porcelain"):
            return initial_dirty
        return original_git(*args)

    runner.git = experiment_git
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    control_gate = config["control_gate"]
    summaries: dict[str, dict] = {}
    for arm_name, factory in ARMS:
        slug = f"exp571_data_centric_features_parser_v4_{arm_name}"
        print(json.dumps({"experiment_id": EXPECTED_EXPERIMENT_ID, "arm": arm_name}))
        runner.CONFIG_PATH = CONFIG_PATH
        runner.SLUG = slug
        runner.FOLD_BUILDER_FACTORY = factory
        runner.RUNNER_COMMAND = RUNNER_COMMAND
        runner.main()
        repair_reproducibility_manifest(slug)
        metrics_path = runner.ROOT / "reports" / slug / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        summaries[arm_name] = {
            "metrics": str(metrics_path.relative_to(runner.ROOT)),
            "macro_f1": metrics["oof"]["macro_f1"],
            "fold_std": metrics["oof"]["fold_std"],
            "accuracy": metrics["oof"]["accuracy"],
            "log_loss": metrics["oof"]["log_loss"],
        }
        if arm_name == "base":
            difference = abs(
                summaries[arm_name]["macro_f1"]
                - float(control_gate["expected_base_oof_macro_f1"])
            )
            if (
                bool(control_gate["abort_before_ablation_on_failure"])
                and difference > float(control_gate["absolute_tolerance"])
            ):
                raise RuntimeError(
                    "EXP-571 Base가 EXP-567을 재현하지 못해 A/B를 중단합니다: "
                    f"absolute_difference={difference}"
                )

    summary_dir = runner.ROOT / "reports/exp571_data_centric_features_parser_v4"
    summary_dir.mkdir(parents=True, exist_ok=True)
    (summary_dir / "arm_summary.json").write_text(
        json.dumps(
            {
                "experiment_id": EXPECTED_EXPERIMENT_ID,
                "fixed_parent": "EXP-567",
                "arms": summaries,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    arguments = parse_args()
    main(
        repair_reproducibility_only=arguments.repair_reproducibility_only
    )
