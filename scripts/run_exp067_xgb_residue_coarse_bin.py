#!/usr/bin/env python
"""Run EXP-067: EXP-047 with fixed-width coarse residue-position bins."""

from open_cancer.mutation_features import LOG_BURDEN_FEATURES
from run_exp005_xgb_mutation_features import ROOT, run_experiment


if __name__ == "__main__":
    run_experiment(
        config_path=ROOT / "configs" / "exp067_xgb_residue_coarse_bin.yaml",
        expected_issue_number=67,
        artifact_slug="exp067_xgb_residue_coarse_bin",
        feature_dir=(
            ROOT
            / "data"
            / "processed"
            / "feature_factory"
            / "v1"
            / "exp067_residue_coarse_bin"
        ),
        include_robust_aggregates=False,
        selected_robust_aggregates=LOG_BURDEN_FEATURES,
        parent_experiment="EXP-047",
        comparison_metrics_path=(
            ROOT / "reports" / "exp047_xgb_min_residue_position" / "metrics.json"
        ),
        notes=(
            "EXP-047 min-residue configuration with the sole representation "
            "change transform=coarse_bin and a fixed bin width of 100. Missing "
            "positions remain zero and complex-token positions remain included."
        ),
    )
