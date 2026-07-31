#!/usr/bin/env python
"""Run EXP-052: EXP-047 plus curated hotspot-gene co-mutation pairs.

Adds Feature Factory family 7 (co-mutation): three literature-documented gene
pairs among the EXP-031 hotspot-implicated genes (IDH1/IDH2 mutual
exclusivity, APC/CTNNB1 mutual exclusivity in the Wnt pathway, PIK3CA/PTEN
PI3K-pathway co-occurrence). Pairs are fixed by external biological knowledge,
not mined from this dataset's co-occurrence frequency, so no fold-train
fitting is required (see mutation_features.CO_MUTATION_PAIRS).
"""

from open_cancer.mutation_features import CO_MUTATION_PAIRS, LOG_BURDEN_FEATURES
from run_exp005_xgb_mutation_features import ROOT, run_experiment


if __name__ == "__main__":
    run_experiment(
        config_path=ROOT / "configs" / "exp052_hotspot_cooccurrence.yaml",
        expected_issue_number=52,
        artifact_slug="exp052_hotspot_cooccurrence",
        feature_dir=(
            ROOT
            / "data"
            / "processed"
            / "feature_factory"
            / "v1"
            / "exp052_hotspot_cooccurrence"
        ),
        include_robust_aggregates=False,
        selected_robust_aggregates=LOG_BURDEN_FEATURES,
        parent_experiment="EXP-047",
        comparison_metrics_path=(
            ROOT / "reports" / "exp047_xgb_min_residue_position" / "metrics.json"
        ),
        notes=(
            "EXP-047 features plus 3 curated co-mutation pairs "
            f"({CO_MUTATION_PAIRS}) among EXP-031 hotspot-implicated genes: "
            "1 indicator per pair (both genes mutated, any position) + 1 "
            "total co-mutation count. Pairs are fixed literature knowledge, "
            "not mined from this dataset's frequency; no target or fold "
            "fitting."
        ),
    )
