#!/usr/bin/env python
"""Run EXP-045 with outer-fold-safe nested permutation feature selection."""

from open_cancer.mutation_features import (
    LOG_BURDEN_FEATURES,
    SAMPLE_DISTRIBUTION_FEATURES,
)
from open_cancer.nested_feature_selection import (
    EXP043_CANDIDATE_GROUPS,
    select_nested_features,
)
from run_exp005_xgb_mutation_features import ROOT, run_experiment


if __name__ == "__main__":
    run_experiment(
        config_path=ROOT / "configs" / "exp045_xgb_nested_feature_selection.yaml",
        expected_issue_number=45,
        artifact_slug="exp045_xgb_nested_feature_selection",
        feature_dir=ROOT / "data" / "processed" / "exp045_nested_feature_selection",
        include_robust_aggregates=False,
        selected_robust_aggregates=(
            *LOG_BURDEN_FEATURES,
            *SAMPLE_DISTRIBUTION_FEATURES,
        ),
        parent_experiment="EXP-043",
        comparison_metrics_path=(
            ROOT / "reports" / "exp043_xgb_sample_distribution" / "metrics.json"
        ),
        notes=(
            "EXP-043 candidates selected group-first then feature-level using only "
            "inner folds of each outer-train partition."
        ),
        fold_feature_selector=select_nested_features,
        candidate_feature_groups=EXP043_CANDIDATE_GROUPS,
    )
