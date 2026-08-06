#!/usr/bin/env python
"""Run EXP-660: minimal notation-invariant, isoform-aware Track A baseline."""

from __future__ import annotations

from dataclasses import replace

from open_cancer.feature_family import FoldFeatureBundle
from open_cancer.parser_baseline_features import ParserBaselineFoldBuilder
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
)
from run_hotspot_xgb import ROOT, TEST_PATH, TRAIN_PATH, main


CONFIG = ROOT / "configs" / "exp660_minimal_track_a.yaml"


class MinimalTrackAFoldBuilder:
    """Keep gene-level v4 semantics and remove every sample aggregate."""

    def __init__(self) -> None:
        self.source = ParserBaselineFoldBuilder(
            representation="native_v3_semantic_range",
            train_path=TRAIN_PATH,
            test_path=TEST_PATH,
        )

    def __call__(self, **kwargs) -> FoldFeatureBundle:
        bundle = self.source(**kwargs)
        keep = tuple(
            index
            for index, name in enumerate(bundle.feature_names)
            if not name.startswith("sample__")
        )
        base_sample_names = tuple(
            name
            for name in kwargs["base_feature_names"]
            if name.startswith("sample__")
        )
        registry = {
            **bundle.registry,
            "minimal_track_a_projection": {
                "definition_version": "1.0.0",
                "sample_aggregates_removed": True,
                "removed_native_sample_feature_count": len(bundle.feature_names)
                - len(keep),
                "removed_base_sample_feature_count": len(base_sample_names),
                "preserves_gene_mutation_presence": True,
                "preserves_gene_missingness": True,
                "target_used": False,
                "test_distribution_used_for_schema": False,
            },
        }
        return replace(
            bundle,
            train=bundle.train[:, keep],
            validation=bundle.validation[:, keep],
            test=bundle.test[:, keep],
            feature_names=tuple(bundle.feature_names[index] for index in keep),
            registry=registry,
            base_feature_names_to_drop=tuple(
                dict.fromkeys((*bundle.base_feature_names_to_drop, *base_sample_names))
            ),
        )


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=MinimalTrackAFoldBuilder(),
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        runner_command="uv run python scripts/run_exp660_minimal_track_a.py",
    )
