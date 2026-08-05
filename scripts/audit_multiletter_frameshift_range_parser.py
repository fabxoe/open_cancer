#!/usr/bin/env python
"""Audit Issue #378 parser grammars without labels or patient-level output."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from open_cancer.hashing import sha256_file
from open_cancer.mutation_features import classify_mutation_token
from open_cancer.robust_mutation_parser import (
    ROBUST_PARSER_VERSION,
    parse_robust_mutation_token,
)


ROOT = Path(__file__).resolve().parents[1]
TEAM_EXAMPLES: tuple[str, ...] = (
    "1436_1437SI>RF",
    "59_60HY>QH",
    "300_301LE>F*",
    "2126_2127WE>*K",
    "236_237LL>LL",
    "197_198YQ>**",
    "SDEL133fs",
)
MULTILETTER_FRAMESHIFT = re.compile(
    r"^(?P<prefix>[ACDEFGHIKLMNPQRSTVWY*]{2,})(?P<position>[1-9][0-9]*)FS$",
    re.IGNORECASE,
)


def _iter_gene_tokens(
    frame: pd.DataFrame,
    genes: tuple[str, ...],
) -> Iterator[tuple[str, str]]:
    for row in frame.loc[:, genes].itertuples(index=False, name=None):
        for gene, cell in zip(genes, row, strict=True):
            if not isinstance(cell, str) or not cell or cell.upper() == "WT":
                continue
            for token in cell.split():
                if token and token.upper() != "WT":
                    yield gene, token


def audit_dataset(path: Path) -> dict[str, Any]:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    genes = tuple(
        column for column in frame.columns if column not in {"ID", "SUBCLASS"}
    )
    if not genes:
        raise ValueError(f"{path}: 유전자 열이 없습니다.")

    example_counts: Counter[str] = Counter()
    example_genes: dict[str, set[str]] = defaultdict(set)
    multiletter_tokens: Counter[str] = Counter()
    multiletter_genes: set[str] = set()
    multiletter_prefix_lengths: Counter[int] = Counter()
    multiletter_v1_families: Counter[str] = Counter()
    multiletter_v3_families: Counter[str] = Counter()
    range_semantics: Counter[str] = Counter()
    range_tokens: Counter[str] = Counter()
    total_tokens = 0

    upper_examples = {example.upper(): example for example in TEAM_EXAMPLES}
    for gene, raw in _iter_gene_tokens(frame, genes):
        total_tokens += 1
        normalized_raw = raw.upper()
        if normalized_raw in upper_examples:
            example = upper_examples[normalized_raw]
            example_counts[example] += 1
            example_genes[example].add(gene)

        multiletter_match = MULTILETTER_FRAMESHIFT.fullmatch(normalized_raw)
        if multiletter_match is not None:
            prefix = multiletter_match.group("prefix").upper()
            multiletter_tokens[normalized_raw] += 1
            multiletter_genes.add(gene)
            multiletter_prefix_lengths[len(prefix)] += 1
            multiletter_v1_families[classify_mutation_token(raw)] += 1
            multiletter_v3_families[
                parse_robust_mutation_token(raw).event_family
            ] += 1

        parsed = parse_robust_mutation_token(raw)
        if parsed.source_structure == "range_replacement":
            range_tokens[parsed.normalized] += 1
            if parsed.protein_no_change:
                range_semantics["protein_no_change"] += 1
            elif parsed.first_stop_offset == 0:
                range_semantics["immediate_stop"] += 1
            elif parsed.contains_stop:
                range_semantics["translated_prefix_then_stop"] += 1
            else:
                range_semantics["amino_acid_range_replacement"] += 1
            if parsed.range_reference_span_valid is False:
                range_semantics["invalid_reference_span"] += 1

    return {
        "source_path": str(path.relative_to(ROOT)),
        "source_sha256": sha256_file(path),
        "rows": len(frame),
        "gene_columns": len(genes),
        "raw_non_wt_tokens": total_tokens,
        "team_examples": {
            example: {
                "occurrences": example_counts[example],
                "genes": sorted(example_genes[example]),
            }
            for example in TEAM_EXAMPLES
        },
        "multiletter_frameshift": {
            "occurrences": sum(multiletter_tokens.values()),
            "unique_tokens": len(multiletter_tokens),
            "affected_genes": len(multiletter_genes),
            "prefix_length_occurrences": {
                str(length): multiletter_prefix_lengths[length]
                for length in sorted(multiletter_prefix_lengths)
            },
            "v1_event_family_occurrences": dict(
                sorted(multiletter_v1_families.items())
            ),
            "v3_event_family_occurrences": dict(
                sorted(multiletter_v3_families.items())
            ),
            "top_tokens": [
                {"token": token, "occurrences": count}
                for token, count in multiletter_tokens.most_common(25)
            ],
        },
        "range_replacement": {
            "occurrences": sum(range_tokens.values()),
            "unique_canonical_tokens": len(range_tokens),
            "semantic_occurrences": {
                key: range_semantics[key]
                for key in (
                    "amino_acid_range_replacement",
                    "protein_no_change",
                    "translated_prefix_then_stop",
                    "immediate_stop",
                    "invalid_reference_span",
                )
            },
            "top_canonical_tokens": [
                {"token": token, "occurrences": count}
                for token, count in range_tokens.most_common(25)
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, default=ROOT / "data/raw/train.csv")
    parser.add_argument("--test", type=Path, default=ROOT / "data/raw/test.csv")
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            ROOT
            / "reports/analysis/multiletter_frameshift_range_parser/audit.json"
        ),
    )
    args = parser.parse_args()
    result = {
        "record_role": "explore",
        "issue": 378,
        "parser_version": ROBUST_PARSER_VERSION,
        "target_used": False,
        "patient_level_output_retained": False,
        "public_lb_used": False,
        "train_test_prevalence_used_to_define_grammar": False,
        "external_annotation_used": False,
        "multiletter_prefix_interpretation": (
            "unresolved_without_source-format or transcript evidence"
        ),
        "train": audit_dataset(args.train.resolve()),
        "test": audit_dataset(args.test.resolve()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
