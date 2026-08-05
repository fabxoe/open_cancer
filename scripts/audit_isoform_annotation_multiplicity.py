#!/usr/bin/env python
"""Compact label-free audit for Issue #389."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from open_cancer.hashing import sha256_file
from open_cancer.isoform_annotation_multiplicity import (
    MULTIPLICITY_GROUPER_VERSION,
    group_gene_cell_annotations,
)
from open_cancer.mutation_parser_contract import route_protein_mutation


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports/analysis/isoform_annotation_multiplicity/audit.json"
CASES = {
    ("test", "TEST_0063", "IARS1"),
    ("test", "TEST_0027", "CPEB2"),
    ("test", "TEST_2438", "EGFR"),
}


def audit(split: str) -> dict:
    path = ROOT / f"data/raw/{split}.csv"
    cells = 0; likely_cells = 0; strict_reduction = 0; likely_reduction = 0
    group_routes = Counter(); examples = {}
    tmem97_tokens = Counter(); tmem97_cells = 0
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        genes = tuple(c for c in reader.fieldnames or () if c not in {"ID", "SUBCLASS"})
        for row in reader:
            for gene in genes:
                cell = row[gene]
                if not cell or cell.upper() == "WT":
                    continue
                cells += 1
                grouped = group_gene_cell_annotations(cell)
                if gene == "TMEM97":
                    tmem97_cells += 1
                    for token in grouped.raw_tokens:
                        tmem97_tokens[route_protein_mutation(token).normalized_token] += 1
                strict_reduction += grouped.exact_duplicate_count
                likely_reduction += grouped.likely_collapse_count
                if grouped.likely_groups:
                    likely_cells += 1
                    for group in grouped.likely_groups:
                        group_routes[str(group.signature[0])] += 1
                key = (split, row["ID"], gene)
                if key in CASES:
                    examples[f"{row['ID']}:{gene}"] = {
                        "raw_annotation_count": grouped.raw_annotation_count,
                        "strict_event_count": grouped.strict_event_count,
                        "likely_event_count": grouped.likely_event_count,
                        "likely_groups": [
                            {
                                "signature": list(group.signature),
                                "annotation_count": group.annotation_count,
                                "normalized_tokens": list(group.normalized_tokens),
                                "confidence": group.confidence,
                            }
                            for group in grouped.likely_groups
                        ],
                    }
    return {
        "source_sha256": sha256_file(path), "non_wt_gene_cells": cells,
        "cells_with_likely_multiplicity": likely_cells,
        "exact_duplicate_reduction": strict_reduction,
        "additional_likely_reduction": likely_reduction,
        "likely_group_routes": dict(sorted(group_routes.items())),
        "team_examples": examples,
        "tmem97_cross_sample_recurrence": {
            "non_wt_cells": tmem97_cells,
            "tokens": [
                {
                    "sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
                    "token_length": len(token),
                    "occurrences": count,
                    "prefix": token[:32],
                }
                for token, count in tmem97_tokens.most_common(10)
            ],
            "interpretation": (
                "cross-sample recurrence only; never collapsed across patients"
            ),
        },
    }


def main() -> None:
    result = {
        "record_role": "explore", "issue": 389,
        "grouper_version": MULTIPLICITY_GROUPER_VERSION,
        "target_used": False, "public_lb_used": False,
        "confirmed_groups_created": 0,
        "train": audit("train"), "test": audit("test"),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
