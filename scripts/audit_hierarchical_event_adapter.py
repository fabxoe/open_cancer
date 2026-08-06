#!/usr/bin/env python
"""Measure fold-safe detail OOV recovery of the hierarchical adapter."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from open_cancer.canonical_event_tokenizer import tokenize_patient_event_row
from open_cancer.hashing import sha256_file
from open_cancer.hierarchical_event_adapter import fit_hierarchical_event_adapter


ROOT = Path(__file__).resolve().parents[1]


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, default=ROOT / "data/raw/train.csv")
    parser.add_argument("--test", type=Path, default=ROOT / "data/raw/test.csv")
    parser.add_argument(
        "--split", type=Path,
        default=ROOT / "data/splits/stratified_5fold_seed42.csv",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "reports/analysis/parser_v4_hierarchical_adapter",
    )
    parser.add_argument("--detail-minimum-support", type=int, default=2)
    parser.add_argument("--global-minimum-support", type=int, default=1)
    return parser.parse_args()


def _tokenize(frame: pd.DataFrame, genes: tuple[str, ...]):
    result = []
    for index, (_, row) in enumerate(frame.iterrows(), start=1):
        result.append(tokenize_patient_event_row(row, genes))
        if index % 500 == 0 or index == len(frame):
            print(f"tokenized {index}/{len(frame)}", flush=True)
    return tuple(result)


def main() -> None:
    args = _args()
    train = pd.read_csv(args.train, dtype=str, keep_default_na=False)
    test = pd.read_csv(args.test, dtype=str, keep_default_na=False)
    split = pd.read_csv(args.split, dtype={"ID": str, "fold": int})
    genes = tuple(c for c in train if c not in {"ID", "SUBCLASS"})
    if tuple(c for c in test if c != "ID") != genes:
        raise ValueError("train/test gene column order differs")
    if train["ID"].tolist() != split["ID"].tolist():
        raise ValueError("canonical split order differs")

    train_tokens = _tokenize(train, genes)
    test_tokens = _tokenize(test, genes)
    full = fit_hierarchical_event_adapter(
        train_tokens,
        detail_minimum_support=args.detail_minimum_support,
        global_minimum_support=args.global_minimum_support,
    )
    folds = split["fold"].to_numpy()
    fold_results = []
    for fold in sorted(set(folds.tolist())):
        fit = tuple(x for x, value in zip(train_tokens, folds) if value != fold)
        valid = tuple(x for x, value in zip(train_tokens, folds) if value == fold)
        adapter = fit_hierarchical_event_adapter(
            fit,
            detail_minimum_support=args.detail_minimum_support,
            global_minimum_support=args.global_minimum_support,
        )
        fold_results.append({
            "fold": int(fold),
            "detail_dimension": len(adapter.detail_tokens),
            "global_dimension": len(adapter.global_tokens),
            "feature_sha256": adapter.feature_sha256,
            "adapter_sha256": adapter.adapter_sha256,
            "validation": asdict(adapter.audit(valid)),
        })

    result = {
        "audit_type": "parser_v4_hierarchical_event_adapter",
        "detail_minimum_support": args.detail_minimum_support,
        "global_minimum_support": args.global_minimum_support,
        "inputs": {
            "train_sha256": sha256_file(args.train),
            "test_sha256": sha256_file(args.test),
            "split_sha256": sha256_file(args.split),
        },
        "full_train_fit": {
            "detail_dimension": len(full.detail_tokens),
            "global_dimension": len(full.global_tokens),
            "output_dimension": full.output_dimension,
            "feature_sha256": full.feature_sha256,
            "adapter_sha256": full.adapter_sha256,
            "train": asdict(full.audit(train_tokens)),
            "test": asdict(full.audit(test_tokens)),
        },
        "canonical_folds": fold_results,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "audit.json"
    path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(path)


if __name__ == "__main__":
    main()
