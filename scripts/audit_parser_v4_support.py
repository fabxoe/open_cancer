#!/usr/bin/env python
"""Build train/test and canonical-fold support matrix for parser v4 families."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from open_cancer.hashing import sha256_file
from open_cancer.mutation_parser_contract import route_protein_mutation
from open_cancer.parser_support_gate import decide_support_gate


ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "data/raw/train.csv"
TEST = ROOT / "data/raw/test.csv"
SPLIT = ROOT / "data/splits/stratified_5fold_seed42.csv"
OUTPUT = ROOT / "reports/analysis/parser_v4_support_gate/support_matrix.json"


def _family(token: str) -> tuple[str, str]:
    routed = route_protein_mutation(token)
    return routed.route, routed.event_type


def _audit(
    path: Path, *, fold_by_id: dict[str, int] | None = None
) -> dict[tuple[str, str], dict[str, Any]]:
    stats: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "occurrences": 0,
            "tokens": set(),
            "samples": set(),
            "gene_cells": set(),
            "fold_samples": [set() for _ in range(5)],
        }
    )
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        genes = [
            name for name in (reader.fieldnames or ())
            if name not in {"ID", "SUBCLASS"}
        ]
        for row in reader:
            sample_id = row["ID"]
            for gene in genes:
                cell = (row.get(gene) or "").strip()
                if not cell or cell.upper() == "WT":
                    continue
                seen_families: set[tuple[str, str]] = set()
                for token in cell.split():
                    if not token or token.upper() == "WT":
                        continue
                    key = _family(token)
                    record = stats[key]
                    record["occurrences"] += 1
                    record["tokens"].add(token.upper())
                    record["samples"].add(sample_id)
                    seen_families.add(key)
                for key in seen_families:
                    stats[key]["gene_cells"].add((sample_id, gene))
                    if fold_by_id is not None:
                        stats[key]["fold_samples"][fold_by_id[sample_id]].add(sample_id)
    return stats


def main() -> None:
    with SPLIT.open("r", encoding="utf-8", newline="") as handle:
        fold_by_id = {
            row["ID"]: int(row["fold"]) for row in csv.DictReader(handle)
        }
    train = _audit(TRAIN, fold_by_id=fold_by_id)
    test = _audit(TEST)
    rows: list[dict[str, Any]] = []
    for route, event_type in sorted(set(train) | set(test)):
        train_record = train.get((route, event_type))
        test_record = test.get((route, event_type))
        train_samples = len(train_record["samples"]) if train_record else 0
        fold_counts = (
            [len(values) for values in train_record["fold_samples"]]
            if train_record else [0] * 5
        )
        decision = decide_support_gate(
            route=route,
            train_sample_count=train_samples,
            fold_sample_counts=fold_counts,
        )
        rows.append(
            {
                "route": route,
                "event_type": event_type,
                "train_occurrences": train_record["occurrences"] if train_record else 0,
                "train_unique_tokens": len(train_record["tokens"]) if train_record else 0,
                "train_gene_cells": len(train_record["gene_cells"]) if train_record else 0,
                "train_samples": train_samples,
                "train_fold_samples": fold_counts,
                "test_occurrences": test_record["occurrences"] if test_record else 0,
                "test_unique_tokens": len(test_record["tokens"]) if test_record else 0,
                "test_gene_cells": len(test_record["gene_cells"]) if test_record else 0,
                "test_samples": len(test_record["samples"]) if test_record else 0,
                "decision": decision.decision,
                "reason": decision.reason,
            }
        )
    payload = {
        "issue": 407,
        "parser_contract": "semantic-router-4.0.0",
        "split_path": str(SPLIT.relative_to(ROOT)),
        "split_sha256": sha256_file(SPLIT),
        "gate": {
            "minimum_total_train_samples": 50,
            "minimum_samples_per_canonical_fold": 5,
            "purpose": "execution feasibility only, not feature selection or adoption",
        },
        "families": rows,
        "constraints": {
            "subclass_used": False,
            "public_lb_used": False,
            "test_prevalence_used_for_decision": False,
            "existing_feature_spec_changed": False,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

