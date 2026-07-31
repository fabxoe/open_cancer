#!/usr/bin/env python
"""Run EXP-029 with EXP-005 features plus robust aggregate features."""

from pathlib import Path

from run_exp005_xgb_mutation_features import ROOT, run_experiment


if __name__ == "__main__":
    run_experiment(
        config_path=ROOT / "configs" / "exp029_xgb_log_burden_ratios.yaml",
        expected_issue_number=29,
        artifact_slug="exp029_xgb_log_burden_ratios",
        feature_dir=ROOT / "data" / "processed" / "exp029_log_burden_ratios",
        include_robust_aggregates=True,
        parent_experiment="EXP-005",
        notes=(
            "EXP-005 features plus predefined log-burden and mutation-type ratio "
            "aggregates; no target-derived features or feature selection."
        ),
    )
