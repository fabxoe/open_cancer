#!/usr/bin/env python
"""Run EXP-334: EXP-285 frozen fold parameters plus EXP-313 semantic mask."""

from __future__ import annotations

import yaml

from open_cancer.frozen_fold_parameters import FrozenFoldParameterSelector
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp334_exp285_isoform_residue_mask.yaml"
ARTIFACT_SLUG = "exp334_exp285_isoform_residue_mask"


if __name__ == "__main__":
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    frozen = config["frozen_fold_parameters"]
    main(
        CONFIG,
        fold_feature_builder=PathwayMutationTypeFoldBuilder(
            membership_path=ROOT / "reports" / ARTIFACT_SLUG / "pathway_membership.json"
        ),
        fold_model_tuner=FrozenFoldParameterSelector(
            root=ROOT,
            source_experiment=frozen["source_experiment"],
            fold_records=frozen["folds"],
        ),
        runner_command=(
            "uv run --group experiment python "
            "scripts/run_exp334_exp285_isoform_residue_mask.py"
        ),
    )
