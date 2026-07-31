#!/usr/bin/env python
"""Run EXP-058: EXP-052 co-mutation pairs minus APC/CTNNB1.

EXP-052(#52) added 3 literature-curated co-mutation pairs. A TreeSHAP check
on EXP-052's saved checkpoints (mean per-class contribution of each pair
feature, restricted to the samples where it fires) showed the three pairs
behave very differently:

- PIK3CA/PTEN: UCEC ranks #1/26 by mean contribution (0.042 vs -0.006 mean
  for the other 25 classes) -- the tree already learned this pair as a
  strong, biologically correct UCEC signal on its own, no gating needed.
- APC/CTNNB1: COAD ranks dead last (26/26), with a *negative* mean
  contribution -- applying a colorectal-specific mutual-exclusivity prior
  across all 26 cancer types did not transfer into a useful signal here.
- IDH1/IDH2: only 3 active training rows; contribution is essentially zero
  either way (underpowered, not informative).

A per-cancer-type conditional gate was considered but rejected: it would
require the true SUBCLASS label to decide whether to activate the feature,
which is unavailable at test time (target leakage). This attempt instead
makes the simplest evidence-based choice: drop the pair (APC/CTNNB1) shown
to hurt, keep the other two.
"""

from open_cancer.mutation_features import LOG_BURDEN_FEATURES
from run_exp005_xgb_mutation_features import ROOT, run_experiment


if __name__ == "__main__":
    run_experiment(
        config_path=ROOT / "configs" / "exp058_cooccurrence_pair_ablation.yaml",
        expected_issue_number=58,
        artifact_slug="exp058_cooccurrence_pair_ablation",
        feature_dir=(
            ROOT
            / "data"
            / "processed"
            / "feature_factory"
            / "v1"
            / "exp058_cooccurrence_pair_ablation"
        ),
        include_robust_aggregates=False,
        selected_robust_aggregates=LOG_BURDEN_FEATURES,
        parent_experiment="EXP-052",
        comparison_metrics_path=(
            ROOT / "reports" / "exp052_hotspot_cooccurrence" / "metrics.json"
        ),
        notes=(
            "EXP-052 co-mutation pairs minus APC/CTNNB1, dropped after a "
            "TreeSHAP check on EXP-052's checkpoints showed its mean "
            "contribution to COAD ranked last (26/26) and was negative, "
            "while PIK3CA/PTEN correctly ranked UCEC #1/26. IDH1/IDH2 kept "
            "(only 3 active rows, no evidence of harm). A per-cancer-type "
            "conditional gate was rejected as target leakage (would need "
            "the unknown test SUBCLASS)."
        ),
    )
