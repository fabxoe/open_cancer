#!/usr/bin/env python
"""Materialize a static feature matrix for the #421 family-AUC recompute.

Not an official experiment (analysis_only, no SUBCLASS, no EXPERIMENT_HISTORY
entry). Rebuilds the same base feature families #292's adversarial validation
originally measured (raw_mutation_presence, gene_mutation_type_indicators,
sample_aggregate_burden, residue_position, fixed_hotspot), this time under
EXP-392's parser (stop-notation-invariant v2) and Ensembl isoform mask, plus
two new static columns for the range_stop/range_no_change family (#392).

The official range_stop/range_no_change family is fold-train-fit
(RangeSemanticGeneFamily) inside the model pipeline. For this train-vs-test
domain-AUC diagnostic there is no target/model involved, so fitting once on
the full train.csv (rather than per outer-fold) is not a leakage concern --
it mirrors exactly how the other four families are already static, dataset-
wide feature columns.

Usage: uv run python scripts/build_family_auc_v4_features.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from scipy import sparse

from open_cancer.hotspot_features import build_hotspot_augmented_features, resolve_hotspot_config
from open_cancer.isoform_position_mask import resolve_isoform_position_mask_from_config
from open_cancer.isoform_relative_position import resolve_isoform_relative_position_from_config
from open_cancer.mutation_features import (
    resolve_position_features_from_config,
    resolve_position_options_from_config,
)
from open_cancer.range_semantic_features import RangeSemanticGeneFamily
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    parse_stop_notation_invariant_cell,
)

ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
FEATURE_DIR = ROOT / "data" / "processed" / "family_auc_v4_features"

# Mirrors configs/exp392_range_semantic_indicators.yaml's `features`/`hotspots` blocks.
CONFIG = {
    "hotspots": {
        "table": "extended_34",
        "evidence_scope": "additions_15",
        "minimum_matching_train_rows": 5,
    },
    "features": {
        "robust_aggregates": [
            "sample__mutated_gene_count_log1p",
            "sample__total_variant_count_log1p",
            "sample__multi_variant_gene_count_log1p",
        ],
    },
    "residue_position": {
        "isoform_semantic_mask": {
            "enabled": True,
            "manifest_path": "knowledge/ensembl_isoform_annotation_v1.json",
            "manifest_sha256": "568ea31f5b7fc7ff47d181fe552d39f3b9185f8d0a76cbb2a49d06be022d5bc0",
            "annotation_cache_path": "data/external/ensembl_release_116/competition_gene_isoform_index.json",
            "annotation_cache_sha256": "b9565339f1755d5b07e782c39064207310fa6c254b2e915a15492f4f38903daa",
            "trusted_categories": ["CANONICAL_MATCH", "MANE_MATCH", "OTHER_ISOFORM_MATCH"],
            "masked_categories": [
                "COMPLEX_OR_UNMAPPABLE",
                "OUTSIDE_ALL_KNOWN_ISOFORMS",
                "POSITION_VALID_REF_MISMATCH",
            ],
        }
    },
}


def main() -> None:
    hotspots, _evidence, _min_rows = resolve_hotspot_config(CONFIG["hotspots"])
    selected_position_features = resolve_position_features_from_config(
        {"features": {"residue_position": {"enabled": True, "aggregates": ["max"], "missing_policy": "zero", "complex_tokens": "include", "transform": "raw"}}}
    )
    position_options = resolve_position_options_from_config(
        {"features": {"residue_position": {"enabled": True, "aggregates": ["max"], "missing_policy": "zero", "complex_tokens": "include", "transform": "raw"}}}
    )
    position_token_filter, mask_contract = resolve_isoform_position_mask_from_config(
        {"features": {"residue_position": CONFIG["residue_position"]}}, root=ROOT
    )
    position_token_transformer, relative_contract = resolve_isoform_relative_position_from_config(
        {"features": {"residue_position": CONFIG["residue_position"]}}, root=ROOT
    )
    position_semantic_contract = relative_contract or mask_contract
    selected_robust_aggregates = tuple(CONFIG["features"]["robust_aggregates"])

    build_hotspot_augmented_features(
        TRAIN_PATH,
        TEST_PATH,
        FEATURE_DIR,
        hotspots=hotspots,
        base_feature_options={
            "mutation_cell_parser": parse_stop_notation_invariant_cell,
            "mutation_parser_contract": STOP_NOTATION_PARSER_CONTRACT,
            "selected_robust_aggregates": selected_robust_aggregates,
            "selected_position_features": selected_position_features,
            "position_token_filter": position_token_filter,
            "position_token_transformer": position_token_transformer,
            "position_semantic_contract": position_semantic_contract,
            **position_options,
        },
    )

    train_matrix = sparse.load_npz(FEATURE_DIR / "train_features.npz").tocsr()
    test_matrix = sparse.load_npz(FEATURE_DIR / "test_features.npz").tocsr()
    feature_names = list(json.loads((FEATURE_DIR / "feature_names.json").read_text(encoding="utf-8")))

    train_frame = pd.read_csv(TRAIN_PATH, dtype=str, keep_default_na=False)
    test_frame = pd.read_csv(TEST_PATH, dtype=str, keep_default_na=False)
    gene_columns = tuple(c for c in train_frame.columns if c not in ("ID", "SUBCLASS"))

    fitted = RangeSemanticGeneFamily(gene_columns).fit(train_frame)
    range_train = fitted.transform(train_frame)
    range_test = fitted.transform(test_frame)

    combined_train = sparse.hstack([train_matrix, range_train], format="csr")
    combined_test = sparse.hstack([test_matrix, range_test], format="csr")
    combined_names = feature_names + list(fitted.descriptor.feature_names)

    sparse.save_npz(FEATURE_DIR / "train_features.npz", combined_train, compressed=True)
    sparse.save_npz(FEATURE_DIR / "test_features.npz", combined_test, compressed=True)
    (FEATURE_DIR / "feature_names.json").write_text(
        json.dumps(combined_names, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"base features: {len(feature_names)}, range_stop/no_change: "
        f"{len(fitted.descriptor.feature_names)}, combined: {len(combined_names)}"
    )
    print(f"saved: {FEATURE_DIR}")


if __name__ == "__main__":
    main()
