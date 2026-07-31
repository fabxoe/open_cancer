#!/usr/bin/env python
"""Run EXP-047: EXP-033 plus per-gene minimum protein residue position."""

from open_cancer.mutation_features import LOG_BURDEN_FEATURES
from run_exp005_xgb_mutation_features import ROOT, run_experiment


if __name__ == "__main__":
    run_experiment(
        config_path=ROOT / "configs" / "exp047_xgb_min_residue_position.yaml",
        expected_issue_number=47,
        artifact_slug="exp047_xgb_min_residue_position",
        feature_dir=(
            ROOT
            / "data"
            / "processed"
            / "feature_factory"
            / "v1"
            / "exp047_min_residue_position"
        ),
        include_robust_aggregates=False,
        selected_robust_aggregates=LOG_BURDEN_FEATURES,
        parent_experiment="EXP-033",
        comparison_metrics_path=(
            ROOT / "reports" / "exp033_xgb_log_burden_ablation" / "metrics.json"
        ),
        notes=(
            "EXP-033 features plus one min_residue_position value per gene. "
            "Residue indices are parsed only from source mutation tokens; "
            "transcript, codon nucleotide, genomic coordinate, protein length, "
            "target-derived fitting and test-distribution fitting are excluded."
        ),
    )
