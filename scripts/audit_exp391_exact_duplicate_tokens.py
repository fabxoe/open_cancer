#!/usr/bin/env python
"""Print label-free exact-duplicate impact counts for EXP-391."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from open_cancer.exact_duplicate_mutation_parser import audit_exact_duplicate_cell


ROOT = Path(__file__).resolve().parents[1]


def audit(path: Path) -> dict[str, int | str]:
    totals = {
        "source_tokens": 0,
        "raw_exact_duplicates": 0,
        "normalized_exact_duplicates": 0,
        "duplicates_introduced_by_normalization": 0,
    }
    affected_cells = 0
    affected_samples = 0

    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    genes = [
        column for column in frame.columns if column not in {"ID", "SUBCLASS"}
    ]
    for row in frame.loc[:, genes].itertuples(index=False, name=None):
        sample_affected = False
        for cell in row:
            if not cell or cell == "WT":
                continue
            result = audit_exact_duplicate_cell(cell)
            for key in totals:
                totals[key] += result[key]
            if result["normalized_exact_duplicates"]:
                affected_cells += 1
                sample_affected = True
        affected_samples += int(sample_affected)

    return {
        "file": path.name,
        "samples": len(frame),
        "genes": len(genes),
        "affected_samples": affected_samples,
        "affected_cells": affected_cells,
        **totals,
    }


if __name__ == "__main__":
    result = {
        "rule_definition": (
            "stop-normalize, sort, and retain one copy of each exact "
            "normalized token"
        ),
        "selection_use": False,
        "train": audit(ROOT / "data" / "raw" / "train.csv"),
        "test": audit(ROOT / "data" / "raw" / "test.csv"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
