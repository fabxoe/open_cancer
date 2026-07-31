#!/usr/bin/env python
"""Run EXP-063: EXP-047 plus an explicit residue-position observed indicator."""

from open_cancer.mutation_features import LOG_BURDEN_FEATURES
from run_exp005_xgb_mutation_features import ROOT, run_experiment


if __name__ == "__main__":
    run_experiment(
        config_path=ROOT / "configs" / "exp063_xgb_residue_indicator.yaml",
        expected_issue_number=63,
        artifact_slug="exp063_xgb_residue_indicator",
        feature_dir=(
            ROOT
            / "data"
            / "processed"
            / "feature_factory"
            / "v1"
            / "exp063_residue_indicator"
        ),
        include_robust_aggregates=False,
        selected_robust_aggregates=LOG_BURDEN_FEATURES,
        parent_experiment="EXP-047",
        comparison_metrics_path=(
            ROOT / "reports" / "exp047_xgb_min_residue_position" / "metrics.json"
        ),
        notes=(
            "EXP-047 min-residue configuration with the sole change "
            "missing_policy=indicator. Complex positions remain included and "
            "the position transform remains raw."
        ),
    )
