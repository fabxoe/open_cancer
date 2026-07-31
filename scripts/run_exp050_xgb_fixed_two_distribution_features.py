#!/usr/bin/env python
"""Run EXP-050 with two EXP-045-derived features fixed before evaluation."""

from open_cancer.mutation_features import EXP050_FIXED_DISTRIBUTION_FEATURES
from run_exp005_xgb_mutation_features import ROOT, run_experiment


if __name__ == "__main__":
    run_experiment(
        config_path=(
            ROOT / "configs" / "exp050_xgb_fixed_two_distribution_features.yaml"
        ),
        expected_issue_number=50,
        artifact_slug="exp050_xgb_fixed_two_distribution_features",
        feature_dir=(
            ROOT / "data" / "processed" / "exp050_fixed_two_distribution_features"
        ),
        include_robust_aggregates=False,
        selected_robust_aggregates=EXP050_FIXED_DISTRIBUTION_FEATURES,
        parent_experiment="EXP-005",
        comparison_metrics_path=(
            ROOT / "reports" / "exp005_xgb_mutation_features" / "metrics.json"
        ),
        notes=(
            "EXP-005 features plus exactly two candidates fixed before execution "
            "from EXP-045: synonymous affected-gene count and mean variants per "
            "mutated gene. Shared split, model parameters and sample weighting are "
            "unchanged; no further feature selection is applied."
        ),
    )
