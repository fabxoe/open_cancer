#!/usr/bin/env python
"""Write compact train/test parser-v2 QC without patient-level output."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from open_cancer.mutation_features import parse_mutation_token
from open_cancer.robust_mutation_parser import (
    EVENT_FAMILIES,
    audit_robust_mutation_parser,
    canonicalize_mutation_cell,
)


ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> tuple[pd.DataFrame, tuple[str, ...]]:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    genes = tuple(column for column in frame.columns if column not in {"ID", "SUBCLASS"})
    if not genes:
        raise ValueError(f"{path}: 유전자 열이 없습니다.")
    return frame, genes


def _v1_complex_reclassification(
    frame: pd.DataFrame,
    genes: tuple[str, ...],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in frame.loc[:, genes].itertuples(index=False, name=None):
        for cell in row:
            canonical = canonicalize_mutation_cell(cell)
            for token in canonical.tokens:
                if parse_mutation_token(token.raw).is_complex:
                    counts[token.event_family] += 1
    return {family: counts[family] for family in EVENT_FAMILIES}


def audit(path: Path) -> dict[str, Any]:
    frame, genes = _read(path)
    result = audit_robust_mutation_parser(frame, genes)
    result["source_path"] = str(path.relative_to(ROOT))
    result["v1_complex_reclassified_as_v2"] = _v1_complex_reclassification(frame, genes)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, default=ROOT / "data/raw/train.csv")
    parser.add_argument("--test", type=Path, default=ROOT / "data/raw/test.csv")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports/analysis/robust_mutation_parser_v2/audit.json",
    )
    args = parser.parse_args()
    result = {
        "record_role": "explore",
        "target_used": False,
        "public_lb_used": False,
        "threshold_selected_from_train_test_prevalence": False,
        "train": audit(args.train.resolve()),
        "test": audit(args.test.resolve()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
