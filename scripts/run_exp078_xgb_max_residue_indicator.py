#!/usr/bin/env python
"""Run EXP-078: EXP-069 maximum residue position plus observed indicator."""

from open_cancer.mutation_features import LOG_BURDEN_FEATURES
from run_exp005_xgb_mutation_features import ROOT, run_experiment


if __name__ == "__main__":
    run_experiment(
        config_path=ROOT / "configs" / "exp078_xgb_max_residue_indicator.yaml",
        expected_issue_number=78,
        artifact_slug="exp078_xgb_max_residue_indicator",
        feature_dir=(
            ROOT
            / "data"
            / "processed"
            / "feature_factory"
            / "v1"
            / "exp078_max_residue_indicator"
        ),
        include_robust_aggregates=False,
        selected_robust_aggregates=LOG_BURDEN_FEATURES,
        parent_experiment="EXP-069",
        comparison_metrics_path=(
            ROOT / "reports" / "exp069_xgb_max_residue_position" / "metrics.json"
        ),
        notes=(
            "EXP-069 max-residue configuration with the sole change "
            "missing_policy=indicator. Complex-token positions remain included "
            "and the position transform remains raw."
        ),
    )
