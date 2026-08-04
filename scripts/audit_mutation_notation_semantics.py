#!/usr/bin/env python
"""Audit mutation notation normalization without retaining patient-level data."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from open_cancer.robust_mutation_parser import (
    EVENT_FAMILIES,
    ROBUST_PARSER_VERSION,
    parse_robust_mutation_token,
)


ROOT = Path(__file__).resolve().parents[1]
SIMPLE_X_STOP = re.compile(r"^[ACDEFGHIKLMNPQRSTVWY][1-9][0-9]*X$", re.IGNORECASE)
SIMPLE_TER_STOP = re.compile(
    r"^[ACDEFGHIKLMNPQRSTVWY][1-9][0-9]*TER$", re.IGNORECASE
)
DOUBLE_STOP = re.compile(r"^\*[1-9][0-9]*\*$")


def count_tokens(path: Path) -> tuple[Counter[str], int, int]:
    counter: Counter[str] = Counter()
    rows = 0
    genes = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        start = 2 if "SUBCLASS" in header else 1
        genes = len(header) - start
        for row in reader:
            rows += 1
            for cell in row[start:]:
                for token in cell.split():
                    if token and token.upper() != "WT":
                        counter[token] += 1
    return counter, rows, genes


def summarize(counter: Counter[str], *, rows: int, genes: int) -> dict[str, object]:
    event_counts = Counter()
    confidence_counts = Counter()
    normalized_counts = Counter()
    raw_forms: dict[str, set[str]] = defaultdict(set)
    position_eligible = 0
    for raw, count in counter.items():
        parsed = parse_robust_mutation_token(raw)
        event_counts[parsed.event_family] += count
        confidence_counts[parsed.confidence] += count
        normalized_counts[parsed.normalized] += count
        raw_forms[parsed.normalized].add(raw)
        position_eligible += count * int(parsed.position_eligible)

    collisions = sorted(
        (
            {
                "canonical": normalized,
                "raw_forms": sorted(forms),
                "occurrences": normalized_counts[normalized],
            }
            for normalized, forms in raw_forms.items()
            if len(forms) > 1
        ),
        key=lambda item: (-int(item["occurrences"]), str(item["canonical"])),
    )
    total = sum(counter.values())
    return {
        "rows": rows,
        "gene_columns": genes,
        "source_token_occurrences": total,
        "unique_raw_tokens": len(counter),
        "unique_canonical_tokens": len(normalized_counts),
        "canonical_vocabulary_reduction": len(counter) - len(normalized_counts),
        "position_eligible_occurrences": position_eligible,
        "position_ineligible_occurrences": total - position_eligible,
        "event_family_occurrences": {
            family: event_counts[family] for family in EVENT_FAMILIES
        },
        "confidence_occurrences": {
            confidence: confidence_counts[confidence]
            for confidence in ("high", "medium", "low")
        },
        "known_notation_cases": {
            "simple_x_stop": sum(
                count for token, count in counter.items() if SIMPLE_X_STOP.fullmatch(token)
            ),
            "simple_ter_stop": sum(
                count for token, count in counter.items() if SIMPLE_TER_STOP.fullmatch(token)
            ),
            "negative_or_upstream_partial": sum(
                count for token, count in counter.items() if token.startswith("-")
            ),
            "ambiguous_double_stop": sum(
                count for token, count in counter.items() if DOUBLE_STOP.fullmatch(token)
            ),
        },
        "top_semantic_collisions": collisions[:25],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, default=ROOT / "data/raw/train.csv")
    parser.add_argument("--test", type=Path, default=ROOT / "data/raw/test.csv")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports/analysis/mutation_notation_semantic_contract/audit.json",
    )
    args = parser.parse_args()

    train, train_rows, train_genes = count_tokens(args.train)
    test, test_rows, test_genes = count_tokens(args.test)
    document = {
        "analysis_only": True,
        "parser_version": ROBUST_PARSER_VERSION,
        "target_used": False,
        "public_leaderboard_used": False,
        "patient_level_values_retained": False,
        "train": summarize(train, rows=train_rows, genes=train_genes),
        "test": summarize(test, rows=test_rows, genes=test_genes),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(document, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
