#!/usr/bin/env python
"""Run EXP-620 regularized LightGBM on frozen EXP-571 Parser QC features."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml

import run_exp449_lightgbm_exp374 as runner
from exp571_data_centric_feature_builders import build_parser_qc_features


EXPECTED_EXPERIMENT_ID = "EXP-620"
EXPECTED_ISSUE_NUMBER = 620
CONFIG_PATH = runner.ROOT / "configs/exp620_lightgbm_regularization_multiseed.yaml"
BASE_SLUG = "exp620_lightgbm_regularization_multiseed"
RUNNER_COMMAND = (
    "uv run python -u scripts/run_exp620_lightgbm_regularization_multiseed.py "
    "--config configs/exp620_lightgbm_regularization_multiseed.yaml"
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
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact_record(kind: str, path: Path) -> dict[str, Any]:
    return {
        "kind": kind,
        "path": path.relative_to(runner.ROOT).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "storage_uri": None,
    }


def repair_reproducibility_manifest(slug: str) -> Path:
    """Upgrade the reused LightGBM runner output to the current schema."""

    reproducibility_dir = runner.ROOT / "reproducibility" / slug
    manifest_path = reproducibility_dir / "artifact_manifest.json"
    comparison_path = reproducibility_dir / "comparison.json"
    resolved_config_path = reproducibility_dir / "config.resolved.yaml"
    for path in (manifest_path, comparison_path, resolved_config_path):
        if not path.is_file():
            raise FileNotFoundError(f"재현 산출물이 없습니다: {path}")

    legacy_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
    resolved_config = yaml.safe_load(resolved_config_path.read_text(encoding="utf-8"))

    data_paths = (
        ("train", runner.ROOT / "data/raw/train.csv"),
        ("test", runner.ROOT / "data/raw/test.csv"),
        ("sample_submission", runner.ROOT / "data/raw/sample_submission.csv"),
        ("split", runner.ROOT / "data/splits/stratified_5fold_seed42.csv"),
    )
    for _kind, path in data_paths:
        if not path.is_file():
            raise FileNotFoundError(f"데이터 manifest 입력이 없습니다: {path}")

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

    environment = resolved_config.get("environment", {})
    environment_path = reproducibility_dir / "environment.json"
    runner.write_json(
        environment_path,
        {
            "python": str(environment.get("python", "unknown")),
            "platform": str(environment.get("platform", "unknown")),
        },
    )

    candidates: list[tuple[str, Path]] = []
    candidates.extend(
        ("checkpoint", path)
        for path in sorted((runner.ROOT / "models" / slug).glob("fold_*.txt"))
    )
    candidates.extend(
        (
            ("oof_probability", runner.ROOT / "oof" / f"{slug}.csv"),
            ("test_probability", runner.ROOT / "preds" / f"{slug}_test_proba.csv"),
            ("submission", runner.ROOT / "submissions" / f"{slug}.csv"),
            ("metrics", runner.ROOT / "reports" / slug / "metrics.json"),
            ("resolved_config", resolved_config_path),
        )
    )
    artifacts = [
        artifact_record(kind, path)
        for kind, path in candidates
        if path.is_file()
    ]
    required_kinds = {"submission", "metrics", "resolved_config"}
    observed_kinds = {item["kind"] for item in artifacts}
    if not required_kinds.issubset(observed_kinds):
        missing = sorted(required_kinds - observed_kinds)
        raise FileNotFoundError("필수 재현 산출물이 없습니다: " + ", ".join(missing))

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
    if not required_verification.issubset(verification):
        missing = sorted(required_verification - verification.keys())
        raise ValueError("comparison 필수 검증값이 없습니다: " + ", ".join(missing))

    manifest = {
        "experiment_id": EXPECTED_EXPERIMENT_ID,
        "issue_number": EXPECTED_ISSUE_NUMBER,
        "reproducibility_status": legacy_manifest["reproducibility_status"],
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


def load_metrics(slug: str) -> dict[str, Any]:
    path = runner.ROOT / "reports" / slug / "metrics.json"
    return json.loads(path.read_text(encoding="utf-8"))


def write_summary(
    config: dict[str, Any],
    results: dict[int, dict[str, Any]],
) -> Path:
    official_seed = int(config["training"]["official_seed"])
    parent = config["comparison"]
    official = results[official_seed]
    seed_scores = np.asarray(
        [result["oof"]["macro_f1"] for result in results.values()],
        dtype=np.float64,
    )
    parent_per_class = load_metrics(
        "exp571_data_centric_features_parser_v4_parser_qc"
    )["oof"]["per_class_f1"]
    official_per_class = official["oof"]["per_class_f1"]
    per_class_delta = {
        label: float(official_per_class[label] - parent_per_class[label])
        for label in parent_per_class
    }

    summary = {
        "experiment_id": EXPECTED_EXPERIMENT_ID,
        "parent_experiment": "EXP-571",
        "parent_arm": "parser_qc",
        "official_seed": official_seed,
        "official": {
            "oof_macro_f1": official["oof"]["macro_f1"],
            "accuracy": official["oof"]["accuracy"],
            "log_loss": official["oof"]["log_loss"],
            "fold_std": official["oof"]["fold_std"],
            "parent_macro_f1_delta": float(
                official["oof"]["macro_f1"] - parent["parent_oof_macro_f1"]
            ),
            "parent_log_loss_delta": float(
                official["oof"]["log_loss"] - parent["parent_log_loss"]
            ),
            "parent_fold_std_delta": float(
                official["oof"]["fold_std"] - parent["parent_fold_std"]
            ),
            "per_class_f1_delta": per_class_delta,
            "worst_class_f1_delta": min(per_class_delta.values()),
        },
        "seed_diagnostics": {
            str(seed): {
                "oof_macro_f1": result["oof"]["macro_f1"],
                "accuracy": result["oof"]["accuracy"],
                "log_loss": result["oof"]["log_loss"],
                "fold_std": result["oof"]["fold_std"],
            }
            for seed, result in results.items()
        },
        "seed_macro_f1_mean": float(seed_scores.mean()),
        "seed_macro_f1_std": float(seed_scores.std()),
        "preregistered_gates": {
            "recommended_macro_f1_gain": float(
                parent["minimum_recommended_macro_f1_gain"]
            ),
            "maximum_per_class_f1_drop": float(
                parent["maximum_per_class_f1_drop"]
            ),
        },
    }
    summary["decision_checks"] = {
        "official_macro_f1_not_lower": (
            summary["official"]["parent_macro_f1_delta"] >= 0.0
        ),
        "official_log_loss_improved": (
            summary["official"]["parent_log_loss_delta"] < 0.0
        ),
        "official_fold_std_improved": (
            summary["official"]["parent_fold_std_delta"] < 0.0
        ),
        "no_class_f1_collapse": (
            summary["official"]["worst_class_f1_delta"]
            >= -float(parent["maximum_per_class_f1_drop"])
        ),
    }

    report_dir = runner.ROOT / "reports" / BASE_SLUG
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "stability_summary.json"
    runner.write_json(path, summary)
    official_summary = summary["official"]
    diagnostic_rows = "\n".join(
        "| {seed} | {oof_macro_f1:.10f} | {accuracy:.10f} | "
        "{log_loss:.10f} | {fold_std:.10f} |".format(
            seed=seed,
            **values,
        )
        for seed, values in summary["seed_diagnostics"].items()
    )
    readme = f"""# EXP-620: LightGBM Regularization and Multi-Seed Stability

## Experiment contract

- Parent: EXP-571 Parser QC arm
- Canonical split: stratified 5-fold seed 42
- Feature change: none
- Official model seed: {official_seed}
- Diagnostic model seeds: {', '.join(str(seed) for seed in results if seed != official_seed)}
- Public LB/test distribution used for selection: no

## Official seed result

| Metric | Value | Delta from EXP-571 Parser QC |
|---|---:|---:|
| OOF Macro F1 | {official_summary['oof_macro_f1']:.10f} | {official_summary['parent_macro_f1_delta']:+.10f} |
| Log Loss | {official_summary['log_loss']:.10f} | {official_summary['parent_log_loss_delta']:+.10f} |
| Fold std | {official_summary['fold_std']:.10f} | {official_summary['parent_fold_std_delta']:+.10f} |
| Accuracy | {official_summary['accuracy']:.10f} | N/A |

## Multi-seed diagnostics

| Model seed | OOF Macro F1 | Accuracy | Log Loss | Fold std |
|---:|---:|---:|---:|---:|
{diagnostic_rows}

Seed 42 is the only official parent comparison. Seeds 142 and 242 are robustness
diagnostics on the same canonical folds and are not searched or selected by score.

## Decision checks

```json
{json.dumps(summary['decision_checks'], ensure_ascii=False, indent=2)}
```

The final adoption decision must consider Macro F1, Log Loss, fold variability,
seed stability, and the worst per-class F1 delta together. This experiment does
not use Public LB feedback to alter the preregistered preset.

## Artifacts

- `stability_summary.json`
- seed-specific metrics under `reports/{BASE_SLUG}_seed*/metrics.json`
- seed-specific reproducibility bundles under `reproducibility/{BASE_SLUG}_seed*/`
"""
    (report_dir / "README.md").write_text(readme, encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    return parser.parse_args()


def main(config_path: Path = CONFIG_PATH) -> None:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if config["experiment_id"] != EXPECTED_EXPERIMENT_ID:
        raise ValueError("EXP-620 config가 아닙니다.")
    if int(config["issue_number"]) != EXPECTED_ISSUE_NUMBER:
        raise ValueError("Issue 번호가 620이 아닙니다.")
    if config["features"]["event_span_enabled"]:
        raise ValueError("EXP-620은 event span을 사용하지 않습니다.")

    official_seed = int(config["training"]["official_seed"])
    diagnostic_seeds = tuple(int(v) for v in config["training"]["diagnostic_seeds"])
    seeds = (official_seed, *diagnostic_seeds)
    if len(set(seeds)) != len(seeds):
        raise ValueError("model seed가 중복되었습니다.")

    initial_dirty = runner.git("status", "--porcelain")
    if initial_dirty:
        raise RuntimeError(
            f"{EXPECTED_EXPERIMENT_ID}는 clean worktree에서만 실행해야 합니다.\n"
            + initial_dirty
        )

    original_git = runner.git
    original_safe_load = runner.yaml.safe_load

    def experiment_git(*args: str) -> str:
        if args == ("status", "--porcelain"):
            return initial_dirty
        return original_git(*args)

    runner.git = experiment_git
    results: dict[int, dict[str, Any]] = {}
    try:
        for model_seed in seeds:
            slug = f"{BASE_SLUG}_seed{model_seed}"

            def seed_aware_safe_load(stream: Any) -> Any:
                loaded = original_safe_load(stream)
                if (
                    isinstance(loaded, dict)
                    and loaded.get("experiment_id") == EXPECTED_EXPERIMENT_ID
                ):
                    loaded = dict(loaded)
                    loaded["seed"] = model_seed
                return loaded

            runner.yaml.safe_load = seed_aware_safe_load
            runner.CONFIG_PATH = config_path
            runner.SLUG = slug
            runner.FOLD_BUILDER_FACTORY = build_parser_qc_features
            runner.RUNNER_COMMAND = RUNNER_COMMAND
            print(
                json.dumps(
                    {
                        "experiment_id": EXPECTED_EXPERIMENT_ID,
                        "model_seed": model_seed,
                        "slug": slug,
                    },
                    ensure_ascii=False,
                )
            )
            runner.main()
            repair_reproducibility_manifest(slug)
            results[model_seed] = load_metrics(slug)
    finally:
        runner.git = original_git
        runner.yaml.safe_load = original_safe_load

    summary_path = write_summary(config, results)
    print(
        json.dumps(
            {
                "experiment_id": EXPECTED_EXPERIMENT_ID,
                "official_seed": official_seed,
                "summary": summary_path.relative_to(runner.ROOT).as_posix(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    arguments = parse_args()
    main(arguments.config)
