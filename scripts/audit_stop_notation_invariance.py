#!/usr/bin/env python
"""Metamorphic audit for */X/Ter stop notation on the train vocabulary."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

from open_cancer.mutation_features import parse_mutation_token
from open_cancer.robust_mutation_parser import (
    POSITION_SANITATION_PARSER_CONTRACT,
    STOP_NOTATION_PARSER_CONTRACT,
    parse_position_sanitized_cell,
    parse_stop_notation_invariant_cell,
)


ROOT = Path(__file__).resolve().parents[1]
STAR_STOP = re.compile(r"^([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]*)\*$")
DOUBLE_STOP = re.compile(r"^\*[1-9][0-9]*\*$")


def scan(path: Path) -> tuple[Counter[str], set[str], Counter[str]]:
    stop_tokens: Counter[str] = Counter()
    stop_genes: set[str] = set()
    ambiguous: Counter[str] = Counter()
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        start = 2 if "SUBCLASS" in header else 1
        genes = header[start:]
        for row in reader:
            for gene, cell in zip(genes, row[start:], strict=True):
                for token in cell.split():
                    if STAR_STOP.fullmatch(token):
                        stop_tokens[token] += 1
                        stop_genes.add(gene)
                    if token.startswith("-"):
                        ambiguous["leading_negative"] += 1
                    if DOUBLE_STOP.fullmatch(token):
                        ambiguous["double_stop"] += 1
    return stop_tokens, stop_genes, ambiguous


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, default=ROOT / "data/raw/train.csv")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "reports/analysis/stop_notation_invariance/audit.json",
    )
    args = parser.parse_args()

    stop_tokens, stop_genes, ambiguous = scan(args.train)
    v1_type_changes = 0
    canonical_failures: list[dict[str, str]] = []
    for star, occurrences in stop_tokens.items():
        match = STAR_STOP.fullmatch(star)
        assert match is not None
        reference, position = match.groups()
        x_form = f"{reference}{position}X"
        ter_form = f"{reference}{position}Ter"
        if parse_mutation_token(star).mutation_type != parse_mutation_token(
            x_form
        ).mutation_type:
            v1_type_changes += occurrences
        parsed = [
            parse_stop_notation_invariant_cell(value).tokens[0]
            for value in (star, x_form, ter_form)
        ]
        if not (parsed[0] == parsed[1] == parsed[2]):
            canonical_failures.append(
                {"star": star, "x": x_form, "ter": ter_form}
            )

    negative = parse_position_sanitized_cell("-287fs").tokens[0]
    double_stop = parse_position_sanitized_cell("*261*").tokens[0]
    document = {
        "analysis_only": True,
        "target_used": False,
        "test_data_used": False,
        "public_leaderboard_used": False,
        "patient_level_values_retained": False,
        "stop_parser_contract": STOP_NOTATION_PARSER_CONTRACT,
        "position_parser_contract": POSITION_SANITATION_PARSER_CONTRACT,
        "train_star_stop_occurrences_tested": sum(stop_tokens.values()),
        "train_unique_star_stop_tokens_tested": len(stop_tokens),
        "train_genes_with_star_stop": len(stop_genes),
        "v1_occurrences_whose_type_changes_under_x_notation": v1_type_changes,
        "canonical_equivalence_failures": canonical_failures,
        "canonical_equivalence_passed": not canonical_failures,
        "ambiguous_occurrences": dict(sorted(ambiguous.items())),
        "negative_control": {
            "-287fs_positions": list(negative.residue_positions),
            "-287fs_mutation_type_preserved": negative.mutation_type,
            "*261*_positions": list(double_stop.residue_positions),
            "*261*_mutation_type_preserved": double_stop.mutation_type,
            "position_sanitation_passed": (
                not negative.residue_positions and not double_stop.residue_positions
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(document, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
