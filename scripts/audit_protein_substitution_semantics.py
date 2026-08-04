#!/usr/bin/env python
"""Audit compact one-letter protein substitution semantics on raw CSVs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from open_cancer.hashing import sha256_file
from open_cancer.protein_substitution_semantics import (
    audit_protein_substitution_semantics,
    parse_protein_substitution_token,
)


ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> tuple[pd.DataFrame, tuple[str, ...]]:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    genes = tuple(column for column in frame.columns if column not in {"ID", "SUBCLASS"})
    if not genes:
        raise ValueError(f"{path}: 유전자 열이 없습니다.")
    return frame, genes


def _stop_metamorphic_audit(frame: pd.DataFrame, genes: tuple[str, ...]) -> dict[str, int]:
    source_stop_tokens = 0
    x_failures = 0
    ter_failures = 0
    for row in frame.loc[:, genes].itertuples(index=False, name=None):
        for cell in row:
            if not isinstance(cell, str):
                continue
            for raw in cell.split():
                parsed = parse_protein_substitution_token(raw)
                if parsed.event_type != "nonsense" or not raw.upper().endswith("*"):
                    continue
                source_stop_tokens += 1
                prefix = raw[:-1]
                canonical = parsed.normalized_token
                x_failures += int(
                    parse_protein_substitution_token(prefix + "X").normalized_token
                    != canonical
                )
                ter_failures += int(
                    parse_protein_substitution_token(prefix + "Ter").normalized_token
                    != canonical
                )
    return {
        "source_star_stop_tokens": source_stop_tokens,
        "star_to_x_equivalence_failures": x_failures,
        "star_to_ter_equivalence_failures": ter_failures,
    }


def audit(path: Path) -> dict[str, object]:
    frame, genes = _read(path)
    result = audit_protein_substitution_semantics(frame, genes)
    result["source_path"] = str(path.relative_to(ROOT))
    result["source_sha256"] = sha256_file(path)
    result["stop_metamorphic_audit"] = _stop_metamorphic_audit(frame, genes)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, default=ROOT / "data/raw/train.csv")
    parser.add_argument("--test", type=Path, default=ROOT / "data/raw/test.csv")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports/analysis/protein_substitution_semantics/audit.json",
    )
    args = parser.parse_args()
    result = {
        "record_role": "explore",
        "target_used": False,
        "public_lb_used": False,
        "test_distribution_used_for_rule": False,
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
