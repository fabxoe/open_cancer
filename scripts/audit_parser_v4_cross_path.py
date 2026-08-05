#!/usr/bin/env python3
"""Audit canonical identity and the v4-to-legacy compatibility projection."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from open_cancer.canonical_mutation_events import (
    canonical_event_sha256,
    route_canonical_token,
)
from open_cancer.mutation_features import MUTATION_TYPES, classify_mutation_token
from open_cancer.parser_compatibility_features import (
    ParserCompatibilityFamily,
    compatibility_family,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "analysis" / "parser_v4_cross_path"


def audit_csv(path: Path, *, has_target: bool) -> tuple[dict[str, object], tuple[str, ...]]:
    crosswalk: Counter[tuple[str, str]] = Counter()
    route_counts: Counter[str] = Counter()
    normalized_hashes: dict[str, set[str]] = defaultdict(set)
    source_tokens = 0
    non_wt_cells = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        offset = 2 if has_target else 1
        genes = tuple(header[offset:])
        for row in reader:
            for cell in row[offset:]:
                if not cell or cell.strip().upper() == "WT":
                    continue
                non_wt_cells += 1
                for raw in cell.split():
                    if not raw or raw.upper() == "WT":
                        continue
                    source_tokens += 1
                    event = route_canonical_token(raw)
                    projected = compatibility_family(event)
                    legacy = classify_mutation_token(raw)
                    crosswalk[(legacy, projected)] += 1
                    route_counts[event.route] += 1
                    normalized_hashes[event.normalized_token].add(
                        canonical_event_sha256(event)
                    )
    collisions = {
        token: sorted(hashes)
        for token, hashes in normalized_hashes.items()
        if len(hashes) > 1
    }
    return (
        {
            "path": str(path.relative_to(ROOT)),
            "source_tokens": source_tokens,
            "non_wt_gene_cells": non_wt_cells,
            "canonical_route_counts": dict(sorted(route_counts.items())),
            "normalized_identity_collision_count": len(collisions),
            "normalized_identity_collision_examples": dict(list(collisions.items())[:20]),
            "legacy_to_v4_compatibility_crosswalk": [
                {"legacy": old, "compatibility": new, "count": count}
                for (old, new), count in sorted(crosswalk.items())
            ],
            "changed_family_token_count": sum(
                count for (old, new), count in crosswalk.items() if old != new
            ),
        },
        genes,
    )


def main() -> None:
    train, train_genes = audit_csv(ROOT / "data" / "raw" / "train.csv", has_target=True)
    test, test_genes = audit_csv(ROOT / "data" / "raw" / "test.csv", has_target=False)
    if train_genes != test_genes:
        raise ValueError("train/test 유전자 열 이름 또는 순서가 다릅니다.")
    empty = pd.DataFrame(columns=train_genes)
    fitted = ParserCompatibilityFamily(train_genes).fit(empty)
    expected_names = (
        *(f"sample__{family}_count" for family in MUTATION_TYPES),
        *(f"{gene}__{family}" for gene in train_genes for family in MUTATION_TYPES),
    )
    if fitted.descriptor.feature_names != expected_names:
        raise ValueError("compatibility feature 이름·순서가 legacy 5-family와 다릅니다.")
    if train["normalized_identity_collision_count"] or test[
        "normalized_identity_collision_count"
    ]:
        raise ValueError("동일 normalized token이 여러 canonical identity를 가집니다.")
    document = {
        "schema_version": "1.0.0",
        "issue": 429,
        "analysis_only": True,
        "model_trained": False,
        "subclass_used": False,
        "public_lb_used": False,
        "compatibility_contract": {
            "output_dimension": fitted.descriptor.output_dimension,
            "feature_names_sha256": fitted.descriptor.feature_names_sha256,
            "base_feature_names_to_drop_sha256": fitted.descriptor.feature_names_sha256,
            "mutation_presence_replaced": False,
            "legacy_families": list(MUTATION_TYPES),
        },
        "train": train,
        "test": test,
        "legacy_consumer_policy": {
            "allowed_for_historical_lineage": [
                "open_cancer.mutation_features",
                "open_cancer.pathway_aggregation_features",
                "open_cancer.parser_semantic_completeness",
            ],
            "new_parser_lineage_modules": [
                "open_cancer.canonical_mutation_events",
                "open_cancer.parser_native_features",
                "open_cancer.parser_compatibility_features",
            ],
            "new_lineage_direct_legacy_classifier_calls": 0,
        },
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "audit.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(document, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

