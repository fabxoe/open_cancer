#!/usr/bin/env python
"""RUN_MODE=explore: internal consistency check for protein position numbering.

For every substitution-style token (e.g. V600E) observed anywhere in
train/test, record the reference amino acid claimed at each (gene, position).
If the same (gene, position) shows conflicting reference amino acids across
patients, the panel's numbering is internally inconsistent for that gene
(at minimum) and any hotspot feature keyed on absolute codon number would be
unsafe there regardless of which external transcript we later validate
against. This does not prove agreement with a canonical transcript -- it only
checks that our own data does not already contradict itself.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"

SUBSTITUTION = re.compile(r"^([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]*)([ACDEFGHIKLMNPQRSTVWY*])$")

KNOWN_HOTSPOTS = {
    ("BRAF", 600),
    ("KRAS", 12),
    ("KRAS", 13),
    ("KRAS", 61),
    ("NRAS", 12),
    ("NRAS", 13),
    ("NRAS", 61),
    ("PIK3CA", 545),
    ("PIK3CA", 1047),
    ("IDH1", 132),
    ("IDH2", 140),
    ("IDH2", 172),
    ("EGFR", 858),
    ("EGFR", 790),
    ("TP53", 175),
    ("TP53", 245),
    ("TP53", 248),
    ("TP53", 273),
    ("TP53", 282),
    ("CTNNB1", 37),
    ("CTNNB1", 45),
    ("GNAS", 201),
    ("HRAS", 12),
    ("HRAS", 13),
    ("HRAS", 61),
}


def iter_cells(path: Path, gene_start_column: int):
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        header = next(reader)
        genes = header[gene_start_column:]
        for row in reader:
            for gene, cell in zip(genes, row[gene_start_column:]):
                if not cell:
                    continue
                for token in cell.split():
                    if token == "WT":
                        continue
                    yield gene, token


def main() -> None:
    position_reference_aa: dict[tuple[str, int], Counter] = defaultdict(Counter)
    total_substitution_tokens = 0

    for path, gene_start_column in ((TRAIN_PATH, 2), (TEST_PATH, 1)):
        for gene, token in iter_cells(path, gene_start_column):
            match = SUBSTITUTION.fullmatch(token)
            if match is None:
                continue
            reference, position_str, _alternate = match.groups()
            total_substitution_tokens += 1
            position_reference_aa[(gene, int(position_str))][reference] += 1

    distinct_positions = len(position_reference_aa)
    inconsistent = {
        key: counter for key, counter in position_reference_aa.items() if len(counter) > 1
    }

    print(f"substitution-style tokens parsed: {total_substitution_tokens}")
    print(f"distinct (gene, position) pairs : {distinct_positions}")
    print(f"inconsistent pairs (>1 reference AA): {len(inconsistent)}")
    print(f"inconsistency rate: {len(inconsistent) / distinct_positions:.4%}")
    print()

    if inconsistent:
        print("-- inconsistent (gene, position) examples (up to 20) --")
        for (gene, position), counter in list(inconsistent.items())[:20]:
            print(f"  {gene} @ {position}: {dict(counter)}")
        print()

    print("-- known hotspot coverage check --")
    for gene, position in sorted(KNOWN_HOTSPOTS):
        counter = position_reference_aa.get((gene, position))
        if counter is None:
            print(f"  {gene} {position}: not observed in this panel")
            continue
        status = "OK (single reference AA)" if len(counter) == 1 else "INCONSISTENT"
        print(f"  {gene} {position}: {dict(counter)} -> {status}")


if __name__ == "__main__":
    main()
