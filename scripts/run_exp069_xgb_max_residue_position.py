#!/usr/bin/env python
"""Run EXP-069: EXP-047 with maximum instead of minimum residue position."""

from open_cancer.mutation_features import LOG_BURDEN_FEATURES
from run_exp005_xgb_mutation_features import ROOT, run_experiment


if __name__ == "__main__":
    run_experiment(
        config_path=ROOT / "configs" / "exp069_xgb_max_residue_position.yaml",
        expected_issue_number=69,
        artifact_slug="exp069_xgb_max_residue_position",
        feature_dir=(
            ROOT
            / "data"
            / "processed"
            / "feature_factory"
            / "v1"
            / "exp069_max_residue_position"
        ),
        include_robust_aggregates=False,
        selected_robust_aggregates=LOG_BURDEN_FEATURES,
        parent_experiment="EXP-047",
        comparison_metrics_path=(
            ROOT / "reports" / "exp047_xgb_min_residue_position" / "metrics.json"
        ),
        notes=(
            "EXP-047 configuration with the sole residue aggregate change "
            "min to max. Missing positions remain zero, complex-token positions "
            "remain included, and the position transform remains raw."
        ),
    )
