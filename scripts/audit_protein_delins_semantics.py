#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from open_cancer.hashing import sha256_file
from open_cancer.protein_delins_semantics import audit_protein_delins_semantics

ROOT = Path(__file__).resolve().parents[1]


def audit(path: Path) -> dict[str, object]:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    genes = tuple(c for c in frame.columns if c not in {"ID", "SUBCLASS"})
    result = audit_protein_delins_semantics(frame, genes)
    result["source_path"] = str(path.relative_to(ROOT))
    result["source_sha256"] = sha256_file(path)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, default=ROOT / "data/raw/train.csv")
    parser.add_argument("--test", type=Path, default=ROOT / "data/raw/test.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/analysis/protein_delins_semantics/audit.json")
    args = parser.parse_args()
    result = {"record_role": "explore", "target_used": False, "public_lb_used": False,
              "test_distribution_used_for_rule": False, "train": audit(args.train.resolve()), "test": audit(args.test.resolve())}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
