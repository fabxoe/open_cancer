#!/usr/bin/env python
"""Run EXP-043 with expanded target-independent sample mutation statistics."""

from open_cancer.mutation_features import EXPANDED_DISTRIBUTION_FEATURES
from run_exp005_xgb_mutation_features import ROOT, run_experiment


if __name__ == "__main__":
    run_experiment(
        config_path=ROOT / "configs" / "exp043_xgb_sample_distribution.yaml",
        expected_issue_number=43,
        artifact_slug="exp043_xgb_sample_distribution",
        feature_dir=ROOT / "data" / "processed" / "exp043_sample_distribution",
        include_robust_aggregates=False,
        selected_robust_aggregates=EXPANDED_DISTRIBUTION_FEATURES,
        parent_experiment="EXP-005",
        comparison_metrics_path=(
            ROOT / "reports" / "exp033_xgb_log_burden_ablation" / "metrics.json"
        ),
        notes=(
            "EXP-005 features plus target-independent sample mutation-distribution "
            "statistics. Model parameters, sample weighting and shared split are "
            "unchanged; feature selection, external data and model tuning are excluded."
        ),
    )
