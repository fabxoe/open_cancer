#!/usr/bin/env python
"""Audit fold-train support for parser-v4 Hotspot-12 without model fitting."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from open_cancer.hashing import sha256_file, sha256_lines
from open_cancer.residue_hotspot12 import (
    ResidueHotspot12Family,
    summarize_fold_stability,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRAIN = ROOT / "data" / "raw" / "train.csv"
DEFAULT_SPLIT = ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"
DEFAULT_OUTPUT = (
    ROOT
    / "reports"
    / "analysis"
    / "parser_v4_hotspot12_support_audit"
    / "audit.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--split", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train = pd.read_csv(args.train, dtype=str, keep_default_na=False)
    split = pd.read_csv(args.split, dtype={"ID": str, "fold": int})
    if train["ID"].tolist() != split["ID"].tolist():
        raise ValueError("train과 canonical split의 ID 순서가 다릅니다.")
    gene_columns = tuple(
        column for column in train.columns if column not in {"ID", "SUBCLASS"}
    )
    family = ResidueHotspot12Family(gene_columns)
    fitted_folds = []
    fold_records = []
    for fold in sorted(split["fold"].unique()):
        train_indices = split.index[split["fold"] != fold]
        fitted = family.fit(train.iloc[train_indices])
        fitted_folds.append(fitted)
        metadata = fitted.metadata()
        fold_records.append(
            {
                "fold": int(fold),
                "outer_train_row_count": len(train_indices),
                "candidate_gene_count": metadata["candidate_gene_count"],
                "selected_gene_count": metadata["selected_gene_count"],
                "selected_genes": metadata["selected_genes"],
                "window_profiles": metadata["window_profiles"],
                "window_profiles_sha256": metadata["window_profiles_sha256"],
                "fit_audit": metadata["fit_audit"],
            }
        )

    document = {
        "schema_version": "1.0.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "task_issue": 632,
        "analysis_only": True,
        "model_fit": False,
        "target_used_for_window_selection": False,
        "validation_used_for_window_selection": False,
        "test_distribution_used_for_window_selection": False,
        "train_path": str(args.train.relative_to(ROOT)),
        "train_sha256": sha256_file(args.train),
        "split_path": str(args.split.relative_to(ROOT)),
        "split_sha256": sha256_file(args.split),
        "gene_count": len(gene_columns),
        "gene_columns_sha256": sha256_lines(gene_columns),
        "rule": {
            "event_scope": "parser_v4 substitution:missense resolved positive position",
            "deduplication_unit": "patient_gene_residue_position",
            "window_width": family.window_width,
            "min_event_support": family.min_event_support,
            "min_window_fraction": family.min_window_fraction,
        },
        "folds": fold_records,
        "stability": summarize_fold_stability(fitted_folds),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(document["stability"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
