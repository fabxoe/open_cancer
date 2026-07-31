#!/usr/bin/env python
"""RUN_MODE=explore: investigate whether hotspot artifact clusters imply CV leakage.

Triggered by a finding in explore_hotspot_candidate_mining.py: some genes
(BRAF, TP53, RXRA, CD209, MUC1) show identical position-sets recurring
across many rows, which is not plausible tumor biology. Before trusting any
further OOF Macro F1 comparisons, this checks the concrete leakage
mechanism that would matter: are these repeated rows actual duplicated
patients (identical across all 4,384 gene columns), do duplicates share a
SUBCLASS, and are duplicate groups split across CV folds?

Findings (see EXPERIMENT_HISTORY.md EXP-031 for the full writeup):
  1. The BRAF/TP53/RXRA/CD209/MUC1 position-cluster artifacts occur only in
     TEST, never in TRAIN, and the affected rows are NOT full-row duplicates
     of each other or of any train row. They cannot bias 5-fold CV (computed
     entirely on train), and the current hotspot feature set already only
     encodes the verified individual positions, not the decoy companions.
  2. A separate, independent phenomenon exists: ~16% of train rows are
     involved in exact full-row (all 4,384 gene columns) duplicate groups.
     The overwhelming majority (447/451 groups) mix multiple SUBCLASS
     values -- an expected consequence of extreme sparsity (~99% WT cells),
     not a leakage risk, since the label is not predictable from a mostly-
     empty profile. Only 4 groups are exact duplicates that also share one
     SUBCLASS, and 3 of those span multiple folds -- a real but very
     small-scale (~9 rows total) source of CV optimism.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
SPLIT_PATH = ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"


def load_train() -> list[tuple[str, str, tuple[str, ...]]]:
    with TRAIN_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        next(reader)
        return [(row[0], row[1], tuple(row[2:])) for row in reader]


def load_test_gene_rows() -> dict[str, tuple[str, ...]]:
    with TEST_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        next(reader)
        return {row[0]: tuple(row[1:]) for row in reader}


def load_folds() -> dict[str, int]:
    with SPLIT_PATH.open("r", encoding="utf-8", newline="") as file:
        return {row["ID"]: int(row["fold"]) for row in csv.DictReader(file)}


def main() -> None:
    train_rows = load_train()
    test_gene_rows = load_test_gene_rows()
    folds = load_folds()

    train_gene_rows = {id_: rest for id_, _, rest in train_rows}
    id_to_subclass = {id_: subclass for id_, subclass, _ in train_rows}

    groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for id_, rest in train_gene_rows.items():
        groups[rest].append(id_)

    print(f"train rows: {len(train_gene_rows)}, distinct full-row patterns: {len(groups)}")
    dupe_groups = {pattern: ids for pattern, ids in groups.items() if len(ids) > 1}
    total_dupe_rows = sum(len(ids) for ids in dupe_groups.values())
    print(f"duplicate groups (>1 row): {len(dupe_groups)}, rows involved: {total_dupe_rows}")

    same_class = 0
    mixed_class = 0
    single_fold = 0
    multi_fold = 0
    concerning_examples: list[tuple[set[str], list[tuple[str, int]]]] = []
    for pattern, ids in dupe_groups.items():
        classes = {id_to_subclass[i] for i in ids}
        fold_ids = {folds[i] for i in ids}
        if len(classes) == 1:
            same_class += 1
        else:
            mixed_class += 1
        if len(fold_ids) == 1:
            single_fold += 1
        else:
            multi_fold += 1
        if len(classes) == 1 and len(fold_ids) > 1:
            concerning_examples.append((classes, [(i, folds[i]) for i in ids]))

    print(f"same-SUBCLASS groups: {same_class} / mixed-SUBCLASS groups: {mixed_class}")
    print(f"single-fold groups: {single_fold} / multi-fold groups: {multi_fold}")
    print(f"CONCERNING (same-class AND multi-fold) groups: {len(concerning_examples)}")
    for classes, members in concerning_examples:
        print("   ", classes, members)

    test_groups: dict[tuple[str, ...], list[str]] = defaultdict(list)
    for id_, rest in test_gene_rows.items():
        test_groups[rest].append(id_)
    test_dupe_groups = {pattern: ids for pattern, ids in test_groups.items() if len(ids) > 1}
    print()
    print(
        f"test rows: {len(test_gene_rows)}, distinct patterns: {len(test_groups)}, "
        f"duplicate groups: {len(test_dupe_groups)}"
    )

    shared = set(train_gene_rows.values()) & set(test_gene_rows.values())
    print(f"exact full gene-row patterns shared between train and test: {len(shared)}")

    print()
    print("-- confirming known artifact clusters are test-only --")
    artifact_probe = {
        "BRAF": ({512, 548, 563, 566, 578, 600, 603, 640}, 5),
        "TP53_a": ({16, 43, 136, 175}, 4),
        "RXRA": ({66, 93}, 2),
        "CD209": ({191, 211, 235}, 3),
        "MUC1": ({156, 165, 911}, 3),
    }
    import re

    substitution = re.compile(r"^([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]*)([ACDEFGHIKLMNPQRSTVWY*])$")

    def count_hits(path: Path, id_col: int, gene_start: int, gene: str, target: set[int], min_hits: int) -> int:
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.reader(file)
            header = next(reader)
            genes = header[gene_start:]
            if gene not in genes:
                return 0
            idx = genes.index(gene)
            count = 0
            for row in reader:
                cell = row[gene_start + idx]
                if not cell:
                    continue
                hits = set()
                for token in cell.split():
                    if token == "WT":
                        continue
                    match = substitution.fullmatch(token)
                    if match is not None:
                        hits.add(int(match.group(2)))
                if len(hits & target) >= min_hits:
                    count += 1
            return count

    for label, (target, min_hits) in artifact_probe.items():
        gene = "TP53" if label.startswith("TP53") else label
        train_n = count_hits(TRAIN_PATH, 0, 2, gene, target, min_hits)
        test_n = count_hits(TEST_PATH, 0, 1, gene, target, min_hits)
        print(f"  {label}: train={train_n} test={test_n}")


if __name__ == "__main__":
    main()
