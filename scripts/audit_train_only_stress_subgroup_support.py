#!/usr/bin/env python
"""Issue #606 (#502 Track B, item B0): train-fold-only stress subgroup support audit.

Explore-only analysis: computes, per outer canonical fold, how many TRAIN rows
fall into each stress-axis bucket defined in
reports/analysis/train_only_ood_stress/subgroup_contract.json. All thresholds
are computed on that fold's train rows only. SUBCLASS, test distribution, and
Public LB are never read for bucket boundaries or gate decisions -- this
script never opens test.csv and never loads SUBCLASS beyond the fold split
file's ID/fold columns.

This produces support counts only (B0). Actual OOF subgroup performance
(B1) is out of scope here.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

from open_cancer.canonical_mutation_events import parse_canonical_gene_cell
from open_cancer.parser_v4_semantic_counts import (
    FEATURE_NAMES as PARSER_V4_FEATURE_NAMES,
    ParserV4SemanticCountFamily,
)

ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
SPLIT_PATH = ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"
OUTPUT_JSON = ROOT / "reports" / "analysis" / "train_only_ood_stress" / "summary.json"
OUTPUT_CSV = ROOT / "reports" / "analysis" / "train_only_ood_stress" / "subgroup_support_counts.csv"
GENE_START_COLUMN = 2  # train.csv columns: ID, SUBCLASS, gene_0, gene_1, ...
MIN_USABLE_POSITIVE_ROWS = 5  # below this, a >0 bucket is treated as under-powered for that fold


def load_burden_and_missingness() -> tuple[np.ndarray, np.ndarray, list[str]]:
    ids: list[str] = []
    mutated: list[int] = []
    missing: list[int] = []
    with TRAIN_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        del header
        for row in reader:
            ids.append(row[0])
            mutated_count = 0
            missing_count = 0
            for cell in row[GENE_START_COLUMN:]:
                if not cell:
                    missing_count += 1
                    continue
                if any(token.upper() != "WT" for token in cell.split()):
                    mutated_count += 1
            mutated.append(mutated_count)
            missing.append(missing_count)
    return np.asarray(mutated, dtype=np.float64), np.asarray(missing, dtype=np.float64), ids


def load_nonstandard_notation_count(ids: list[str]) -> np.ndarray:
    """Per-row count of parsed events with event_type == 'other_unmappable'."""

    counts = np.zeros(len(ids), dtype=np.float64)
    with TRAIN_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        for row_index, row in enumerate(reader):
            for cell in row[GENE_START_COLUMN:]:
                if not cell or cell.strip().upper() == "WT":
                    continue
                parsed = parse_canonical_gene_cell(cell)
                for event in parsed.events:
                    if event.event_type == "other_unmappable":
                        counts[row_index] += 1.0
    return counts


def load_parser_v4_family_matrix(gene_columns: list[str]) -> np.ndarray:
    frame = pd.read_csv(TRAIN_PATH, dtype=str, keep_default_na=False)
    family = ParserV4SemanticCountFamily(gene_columns=tuple(gene_columns))
    fitted = family.fit(frame)
    matrix = fitted.transform(frame)
    return np.asarray(matrix.todense())


def bucket_counts(values: np.ndarray, edges: dict[str, tuple[float, float]]) -> dict[str, int]:
    return {
        name: int(np.sum((values > lower) & (values <= upper)))
        for name, (lower, upper) in edges.items()
    }


def main() -> None:
    mutated, missing, ids = load_burden_and_missingness()
    folds = pd.read_csv(SPLIT_PATH, dtype={"ID": str, "fold": int})
    fold_by_id = dict(zip(folds["ID"], folds["fold"]))
    fold_assignment = np.asarray([fold_by_id[identifier] for identifier in ids], dtype=int)

    header_frame = pd.read_csv(TRAIN_PATH, nrows=0)
    gene_columns = [c for c in header_frame.columns if c not in {"ID", "SUBCLASS"}]
    parser_v4_matrix = load_parser_v4_family_matrix(gene_columns)
    unresolved_index = PARSER_V4_FEATURE_NAMES.index("sample__parser_v4_unresolved_count")
    unresolved = parser_v4_matrix[:, unresolved_index]

    nonstandard_notation = load_nonstandard_notation_count(ids)

    per_fold: dict[str, dict] = {}
    for fold in sorted(set(fold_assignment.tolist())):
        train_mask = fold_assignment != fold
        n_train = int(train_mask.sum())

        fold_mutated = mutated[train_mask]
        q10, q90 = np.quantile(fold_mutated, [0.10, 0.90])
        mutation_burden = {
            "n_outer_train": n_train,
            "q10": float(q10),
            "q90": float(q90),
            "bucket_counts": bucket_counts(
                fold_mutated,
                {
                    "<=q10": (-np.inf, q10),
                    "q10-q90": (q10, q90),
                    ">q90": (q90, np.inf),
                },
            ),
        }

        all_wt_low_mutation = {
            "n_outer_train": n_train,
            "bucket_counts": {
                "all_wt": int(np.sum(fold_mutated == 0)),
                "1-4": int(np.sum((fold_mutated >= 1) & (fold_mutated <= 4))),
                ">=5": int(np.sum(fold_mutated >= 5)),
            },
        }

        fold_missing = missing[train_mask]
        missingness = {
            "n_outer_train": n_train,
            "bucket_counts": {
                "==0": int(np.sum(fold_missing == 0)),
                ">0": int(np.sum(fold_missing > 0)),
            },
            "usable": int(np.sum(fold_missing > 0)) >= MIN_USABLE_POSITIVE_ROWS,
        }

        fold_unresolved = unresolved[train_mask]
        complex_unresolved = {
            "n_outer_train": n_train,
            "bucket_counts": {
                "==0": int(np.sum(fold_unresolved == 0)),
                ">0": int(np.sum(fold_unresolved > 0)),
            },
            "usable": int(np.sum(fold_unresolved > 0)) >= MIN_USABLE_POSITIVE_ROWS,
        }

        fold_nonstandard = nonstandard_notation[train_mask]
        nonstandard_notation_bucket = {
            "n_outer_train": n_train,
            "bucket_counts": {
                "==0": int(np.sum(fold_nonstandard == 0)),
                ">0": int(np.sum(fold_nonstandard > 0)),
            },
            "usable": int(np.sum(fold_nonstandard > 0)) >= MIN_USABLE_POSITIVE_ROWS,
        }

        family_support = {}
        fold_family_matrix = parser_v4_matrix[train_mask]
        for name, column in zip(PARSER_V4_FEATURE_NAMES, fold_family_matrix.T):
            positive = int(np.sum(column > 0))
            family_support[name] = {
                "positive_rows": positive,
                "usable": positive >= MIN_USABLE_POSITIVE_ROWS,
            }

        per_fold[str(fold)] = {
            "mutation_burden": mutation_burden,
            "all_wt_low_mutation": all_wt_low_mutation,
            "missingness": missingness,
            "complex_unresolved": complex_unresolved,
            "nonstandard_notation": nonstandard_notation_bucket,
            "parser_semantic_family_support": family_support,
        }

    result = {
        "record_role": "explore",
        "issue": 606,
        "parent_roadmap_issue": 502,
        "roadmap_item": "B0",
        "target_used": False,
        "test_distribution_used": False,
        "public_lb_used": False,
        "min_usable_positive_rows": MIN_USABLE_POSITIVE_ROWS,
        "contract": "reports/analysis/train_only_ood_stress/subgroup_contract.json",
        "per_fold": per_fold,
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rows = []
    for fold, axes in per_fold.items():
        for axis_name, axis_data in axes.items():
            if axis_name == "parser_semantic_family_support":
                for family_name, family_data in axis_data.items():
                    rows.append(
                        {
                            "fold": fold,
                            "axis": f"parser_semantic_burden::{family_name}",
                            "bucket": ">0",
                            "count": family_data["positive_rows"],
                            "usable": family_data["usable"],
                        }
                    )
                continue
            for bucket_name, count in axis_data["bucket_counts"].items():
                rows.append(
                    {
                        "fold": fold,
                        "axis": axis_name,
                        "bucket": bucket_name,
                        "count": count,
                        "usable": axis_data.get("usable", True),
                    }
                )
    pd.DataFrame(rows).to_csv(OUTPUT_CSV, index=False)
    print(json.dumps({"folds": list(per_fold.keys())}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
