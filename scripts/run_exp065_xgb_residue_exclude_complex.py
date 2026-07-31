#!/usr/bin/env python
"""Run EXP-065: EXP-047 while excluding complex-token residue positions."""

from open_cancer.mutation_features import LOG_BURDEN_FEATURES
from run_exp005_xgb_mutation_features import ROOT, run_experiment


if __name__ == "__main__":
    run_experiment(
        config_path=ROOT / "configs" / "exp065_xgb_residue_exclude_complex.yaml",
        expected_issue_number=65,
        artifact_slug="exp065_xgb_residue_exclude_complex",
        feature_dir=(
            ROOT
            / "data"
            / "processed"
            / "feature_factory"
            / "v1"
            / "exp065_residue_exclude_complex"
        ),
        include_robust_aggregates=False,
        selected_robust_aggregates=LOG_BURDEN_FEATURES,
        parent_experiment="EXP-047",
        comparison_metrics_path=(
            ROOT / "reports" / "exp047_xgb_min_residue_position" / "metrics.json"
        ),
        notes=(
            "EXP-047 min-residue configuration with the sole change "
            "complex_tokens=exclude. Missing positions remain zero and the "
            "position transform remains raw."
        ),
    )
