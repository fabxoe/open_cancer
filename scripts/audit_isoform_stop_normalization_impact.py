#!/usr/bin/env python
"""Audit Ensembl isoform-semantic categories before/after stop normalization."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from open_cancer.hashing import sha256_file
from open_cancer.isoform_semantics import (
    ISOFORM_CATEGORIES,
    TranscriptAnnotation,
    classify_token_semantics,
    load_annotation_index,
)
from open_cancer.robust_mutation_parser import normalize_stop_notation_token


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = (
    ROOT / "data/external/ensembl_release_116/competition_gene_isoform_index.json"
)
DEFAULT_TOKEN_DIR = ROOT / "data/processed/isoform_residue_semantics"
DEFAULT_OUTPUT = (
    ROOT / "reports/analysis/isoform_stop_normalization_impact/audit.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--token-dir", type=Path, default=DEFAULT_TOKEN_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def audit_token_table(
    path: Path,
    annotation_index: Mapping[str, Sequence[TranscriptAnnotation]],
) -> dict[str, object]:
    """Reclassify a frozen token table after the isolated stop rule."""

    before: Counter[str] = Counter()
    after: Counter[str] = Counter()
    transitions: Counter[tuple[str, str]] = Counter()
    total = 0
    normalized = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            total += 1
            old_category = row["category"]
            before[old_category] += 1
            raw_token = row["token"]
            normalized_token = normalize_stop_notation_token(raw_token)
            normalized += normalized_token != raw_token
            new_category = classify_token_semantics(
                row["gene"],
                normalized_token,
                annotation_index.get(row["gene"], ()),
            ).category
            after[new_category] += 1
            transitions[(old_category, new_category)] += 1

    return {
        "tokens_total": total,
        "normalized_token_count": normalized,
        "before": _category_summary(before, total),
        "after": _category_summary(after, total),
        "changed_transitions": [
            {"from": old, "to": new, "count": count}
            for (old, new), count in sorted(
                transitions.items(), key=lambda item: (-item[1], item[0])
            )
            if old != new
        ],
    }


def _category_summary(counts: Counter[str], total: int) -> dict[str, object]:
    return {
        category: {
            "count": counts[category],
            "rate": counts[category] / total if total else None,
        }
        for category in ISOFORM_CATEGORIES
    }


def main() -> None:
    args = parse_args()
    annotation_index = load_annotation_index(args.cache)
    train = audit_token_table(args.token_dir / "train_token_semantics.csv", annotation_index)
    test = audit_token_table(args.token_dir / "test_token_semantics.csv", annotation_index)

    train_mane = train["after"]["MANE_MATCH"]["rate"]
    test_mane_before = test["before"]["MANE_MATCH"]["rate"]
    test_mane_after = test["after"]["MANE_MATCH"]["rate"]
    train_mane_before = train["before"]["MANE_MATCH"]["rate"]
    assert isinstance(train_mane, float)
    assert isinstance(test_mane_before, float)
    assert isinstance(test_mane_after, float)
    assert isinstance(train_mane_before, float)

    payload = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis_only": True,
        "target_used": False,
        "public_leaderboard_used_for_rule": False,
        "normalization_contract": {
            "scope": "simple stop alternate notation only",
            "equivalent_inputs": ["*", "X", "Ter"],
            "canonical_output": "*",
        },
        "annotation_cache": str(args.cache.relative_to(ROOT)),
        "annotation_cache_sha256": sha256_file(args.cache),
        "token_tables": {
            "train": str((args.token_dir / "train_token_semantics.csv").relative_to(ROOT)),
            "test": str((args.token_dir / "test_token_semantics.csv").relative_to(ROOT)),
        },
        "train": train,
        "test": test,
        "mane_gap": {
            "before": train_mane_before - test_mane_before,
            "after": train_mane - test_mane_after,
            "absolute_reduction": (
                train_mane_before - test_mane_before
            ) - (train_mane - test_mane_after),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
