#!/usr/bin/env python
"""Count unresolved signed/bilateral-stop source forms without labels."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from open_cancer.protein_partial_terminal_semantics import (
    PARTIAL_TERMINAL_SEMANTICS_VERSION,
    parse_partial_terminal_token,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports/analysis/partial_terminal_semantics/audit.json"


def audit(path: Path) -> dict[str, object]:
    kinds: Counter[str] = Counter()
    genes: dict[str, Counter[str]] = {}
    unique: dict[str, set[str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        gene_columns = [
            name for name in (reader.fieldnames or ())
            if name not in {"ID", "SUBCLASS"}
        ]
        for row in reader:
            for gene in gene_columns:
                for token in (row.get(gene) or "").split():
                    parsed = parse_partial_terminal_token(token)
                    if parsed.parse_status == "not_applicable":
                        continue
                    kind = parsed.semantic_kind
                    kinds[kind] += 1
                    genes.setdefault(kind, Counter())[gene] += 1
                    unique.setdefault(kind, set()).add(parsed.normalized_token)
    return {
        "occurrences": dict(sorted(kinds.items())),
        "unique_tokens": {
            kind: len(tokens) for kind, tokens in sorted(unique.items())
        },
        "top_genes": {
            kind: [
                {"gene": gene, "occurrences": count}
                for gene, count in counter.most_common(20)
            ]
            for kind, counter in sorted(genes.items())
        },
    }


def main() -> None:
    payload = {
        "parser_version": PARTIAL_TERMINAL_SEMANTICS_VERSION,
        "issue": 362,
        "train": audit(ROOT / "data/raw/train.csv"),
        "test": audit(ROOT / "data/raw/test.csv"),
        "contract": {
            "raw_and_signed_position_preserved": True,
            "protein_position_eligible": False,
            "forced_utr_or_extension_interpretation": False,
            "existing_feature_adapter_changed": False,
            "target_or_public_lb_used": False,
        },
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

