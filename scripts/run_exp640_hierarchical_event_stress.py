#!/usr/bin/env python
"""Run EXP-640 Base/A/B/C on the fixed EXP-567 LightGBM parent."""

from __future__ import annotations

import json

import run_exp449_lightgbm_exp374 as runner
import yaml
from exp527_lightgbm_ablation_builders import build_parser_plus_cosine_features
from exp640_hierarchical_event_builders import (
    build_combined_features,
    build_event_family_features,
    build_parser_qc_features,
)


EXPECTED_EXPERIMENT_ID = "EXP-640"
CONFIG_PATH = runner.ROOT / "configs/exp640_hierarchical_event_stress.yaml"
RUNNER_COMMAND = "uv run python scripts/run_exp640_hierarchical_event_stress.py"

ARMS = (
    ("base", build_parser_plus_cosine_features),
    ("event_family", build_event_family_features),
    ("parser_qc", build_parser_qc_features),
    ("combined", build_combined_features),
)


def main() -> None:
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
        slug = f"exp640_hierarchical_event_stress_{arm_name}"
        print(json.dumps({"experiment_id": EXPECTED_EXPERIMENT_ID, "arm": arm_name}))
        runner.CONFIG_PATH = CONFIG_PATH
        runner.SLUG = slug
        runner.FOLD_BUILDER_FACTORY = factory
        runner.RUNNER_COMMAND = RUNNER_COMMAND
        runner.main()
        metrics_path = runner.ROOT / "reports" / slug / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        summaries[arm_name] = {
            "metrics": str(metrics_path.relative_to(runner.ROOT)),
            "macro_f1": metrics["oof"]["macro_f1"],
            "fold_std": metrics["oof"]["fold_std"],
            "accuracy": metrics["oof"]["accuracy"],
            "log_loss": metrics["oof"]["log_loss"],
            "per_class_f1": metrics["oof"]["per_class_f1"],
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
                    "EXP-640 Base가 EXP-567을 재현하지 못해 ablation을 중단합니다: "
                    f"absolute_difference={difference}"
                )

    summary_dir = runner.ROOT / "reports/exp640_hierarchical_event_stress"
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
    main()
