#!/usr/bin/env python
"""Label-free full-vocabulary audit for Issue #383."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from open_cancer.hashing import sha256_file
from open_cancer.isoform_semantics import load_annotation_index
from open_cancer.protein_frameshift_semantics import (
    PROTEIN_FRAMESHIFT_SEMANTICS_VERSION,
    parse_protein_frameshift_token,
    validate_frameshift_reference,
)


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/external/ensembl_release_116/competition_gene_isoform_index.json"
OUTPUT = ROOT / "reports/analysis/protein_frameshift_semantics/audit.json"
EXAMPLES = {"WQ288FS", "P953HFS", "SDEL133FS"}


def audit(path: Path, annotations: dict) -> dict:
    grammar = Counter(); tiers = Counter(); examples = Counter(); genes = set()
    grammar_tiers: dict[str, Counter[str]] = {}
    occurrences = 0; unique = set()
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle); header = next(reader)
        for row in reader:
            for gene, cell in zip(header, row, strict=True):
                if gene in {"ID", "SUBCLASS"} or not cell or cell.upper() == "WT":
                    continue
                for raw in cell.split():
                    parsed = parse_protein_frameshift_token(raw)
                    if parsed.parse_status == "not_applicable":
                        continue
                    validated = validate_frameshift_reference(parsed, annotations.get(gene, ()))
                    occurrences += 1; unique.add(parsed.normalized_token); genes.add(gene)
                    grammar[parsed.grammar] += 1; tiers[validated.reference_match_tier] += 1
                    grammar_tiers.setdefault(parsed.grammar, Counter())[
                        validated.reference_match_tier
                    ] += 1
                    if parsed.normalized_token in EXAMPLES:
                        examples[f"{gene}:{parsed.normalized_token}"] += 1
    return {
        "source_sha256": sha256_file(path), "occurrences": occurrences,
        "unique_tokens": len(unique), "affected_genes": len(genes),
        "grammar_occurrences": dict(sorted(grammar.items())),
        "grammar_reference_match_tiers": {
            key: dict(sorted(value.items()))
            for key, value in sorted(grammar_tiers.items())
        },
        "reference_match_tiers": dict(sorted(tiers.items())),
        "team_examples": dict(sorted(examples.items())),
    }


def main() -> None:
    annotations = load_annotation_index(CACHE)
    result = {
        "record_role": "explore", "issue": 383,
        "parser_version": PROTEIN_FRAMESHIFT_SEMANTICS_VERSION,
        "annotation_cache_sha256": sha256_file(CACHE),
        "target_used": False, "public_lb_used": False,
        "termination_distance_inferred": False,
        "train": audit(ROOT / "data/raw/train.csv", annotations),
        "test": audit(ROOT / "data/raw/test.csv", annotations),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
