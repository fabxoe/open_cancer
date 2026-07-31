#!/usr/bin/env python
"""Run EXP-033: EXP-005 features plus three log-burden aggregates only."""

from open_cancer.mutation_features import LOG_BURDEN_FEATURES
from run_exp005_xgb_mutation_features import ROOT, run_experiment


if __name__ == "__main__":
    run_experiment(
        config_path=ROOT / "configs" / "exp033_xgb_log_burden_ablation.yaml",
        expected_issue_number=33,
        artifact_slug="exp033_xgb_log_burden_ablation",
        feature_dir=ROOT / "data" / "processed" / "exp033_log_burden_ablation",
        include_robust_aggregates=False,
        selected_robust_aggregates=LOG_BURDEN_FEATURES,
        parent_experiment="EXP-005",
        comparison_metrics_path=(
            ROOT / "reports" / "exp005_xgb_mutation_features" / "metrics.json"
        ),
        notes=(
            "EXP-005 features plus three log1p burden features only; "
            "mutation-type ratios, multi-variant ratio, missing ratio, "
            "target-derived features and feature selection are excluded."
        ),
    )
