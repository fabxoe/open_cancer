#!/usr/bin/env python
"""RUN_MODE=explore: mine additional hotspot candidates from the COSMIC whitelist.

Extends the internal-consistency check (explore_hotspot_numbering_consistency.py)
from a hand-curated list of 19 literature hotspots to an automatic scan of every
(gene, position) inside the COSMIC protect-gene whitelist (361 genes, EXP-012).

Selection rule (fixed BEFORE looking at any CV result, to avoid threshold
tuning against the eval metric):

  1. gene must be in the EXP-012 protect whitelist (bounds the search space to
     genes already known to be cancer-relevant, avoiding the "long gene bias"
     artifact flagged for non-whitelist genes in EXP-012).
  2. zero conflicting reference amino acids at that position (same bar used
     for the original 19 known hotspots).
  3. at least MIN_OBSERVATIONS *non-artifact* occurrences. An initial pass
     over BRAF/RXRA/CD209/MUC1/TP53/FBXW7 found that many multi-position
     mutation cells are not independent biology: the exact same *set* of
     positions in the same gene recurs identically dozens of times (e.g.
     TP53 codons 16+43+136+175 always mutate together in 61 patients). That
     is not plausible tumor biology -- no real tumor acquires the same 4
     point mutations in lockstep that often -- so it is treated as a data
     artifact. Any occurrence that is part of a same-gene position-set
     repeated >=CLUSTER_MIN_REPEATS times is excluded before counting
     evidence for each individual position; only "solo" evidence (not part
     of such a repeated template) counts toward MIN_OBSERVATIONS.

This does not use SUBCLASS labels, so it is not target leakage, but the
output remains a *candidate* list for a final manual smell-test against known
cancer biology before anything is added to hotspot_features.KNOWN_HOTSPOTS.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
WHITELIST_PATH = ROOT / "reports" / "exp012_feature_analysis" / "protected_genes_final.csv"
OUTPUT_PATH = ROOT / "reports" / "exp012_feature_analysis" / "hotspot_candidates.csv"
ARTIFACT_OUTPUT_PATH = ROOT / "reports" / "exp012_feature_analysis" / "hotspot_artifact_clusters.csv"

SUBSTITUTION = re.compile(r"^([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]*)([ACDEFGHIKLMNPQRSTVWY*])$")
MIN_OBSERVATIONS = 5
CLUSTER_MIN_REPEATS = 5

KNOWN_HOTSPOTS = {
    ("BRAF", 600),
    ("CTNNB1", 37),
    ("CTNNB1", 45),
    ("EGFR", 790),
    ("EGFR", 858),
    ("GNAS", 201),
    ("HRAS", 12),
    ("HRAS", 13),
    ("HRAS", 61),
    ("IDH1", 132),
    ("IDH2", 140),
    ("IDH2", 172),
    ("PIK3CA", 545),
    ("PIK3CA", 1047),
    ("TP53", 175),
    ("TP53", 245),
    ("TP53", 248),
    ("TP53", 273),
    ("TP53", 282),
}


def load_whitelist_genes(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return {row["gene"] for row in reader}


def iter_rows(path: Path, gene_start_column: int, whitelist: set[str]):
    """Yield (gene, [substitution positions in this cell]) per row per relevant gene."""

    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        header = next(reader)
        genes = header[gene_start_column:]
        relevant = [(offset, gene) for offset, gene in enumerate(genes) if gene in whitelist]
        for row in reader:
            for offset, gene in relevant:
                cell = row[gene_start_column + offset]
                if not cell:
                    continue
                positions = []
                for token in cell.split():
                    if token == "WT":
                        continue
                    match = SUBSTITUTION.fullmatch(token)
                    if match is not None:
                        positions.append(int(match.group(2)))
                if positions:
                    yield gene, positions


def main() -> None:
    whitelist = load_whitelist_genes(WHITELIST_PATH)
    print(f"whitelist genes: {len(whitelist)}")

    # Pass 1: reference-AA consistency per (gene, position), same as before.
    position_reference_aa: dict[tuple[str, int], Counter] = defaultdict(Counter)
    # Pass 2: per-gene multiset of the exact position-set mutated in each row.
    gene_row_patterns: dict[str, Counter] = defaultdict(Counter)

    for path, gene_start_column in ((TRAIN_PATH, 2), (TEST_PATH, 1)):
        for gene, positions in iter_rows(path, gene_start_column, whitelist):
            gene_row_patterns[gene][tuple(sorted(set(positions)))] += 1

    for path, gene_start_column in ((TRAIN_PATH, 2), (TEST_PATH, 1)):
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.reader(file)
            header = next(reader)
            genes = header[gene_start_column:]
            relevant = [(offset, g) for offset, g in enumerate(genes) if g in whitelist]
            for row in reader:
                for offset, gene in relevant:
                    cell = row[gene_start_column + offset]
                    if not cell:
                        continue
                    for token in cell.split():
                        if token == "WT":
                            continue
                        match = SUBSTITUTION.fullmatch(token)
                        if match is None:
                            continue
                        reference, position_str, _alternate = match.groups()
                        position_reference_aa[(gene, int(position_str))][reference] += 1

    # Identify artifact clusters: same-gene position-sets (size > 1) repeated
    # CLUSTER_MIN_REPEATS+ times -- no real tumor acquires the identical set
    # of point mutations that often.
    artifact_clusters: list[tuple[str, tuple[int, ...], int]] = []
    artifact_evidence: dict[tuple[str, int], int] = defaultdict(int)
    for gene, patterns in gene_row_patterns.items():
        for pattern, count in patterns.items():
            if len(pattern) > 1 and count >= CLUSTER_MIN_REPEATS:
                artifact_clusters.append((gene, pattern, count))
                for position in pattern:
                    artifact_evidence[(gene, position)] += count

    artifact_clusters.sort(key=lambda item: item[2], reverse=True)
    with ARTIFACT_OUTPUT_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["gene", "positions", "repeat_count"])
        for gene, pattern, count in artifact_clusters:
            writer.writerow([gene, "+".join(map(str, pattern)), count])
    print(f"artifact clusters (same position-set repeated >={CLUSTER_MIN_REPEATS}x): {len(artifact_clusters)}")
    print(f"  written to {ARTIFACT_OUTPUT_PATH}")
    print()

    candidates = []
    for (gene, position), counter in position_reference_aa.items():
        total = sum(counter.values())
        if len(counter) != 1:
            continue
        artifact = artifact_evidence.get((gene, position), 0)
        genuine = total - artifact
        if genuine < MIN_OBSERVATIONS:
            continue
        (reference_aa,) = counter.keys()
        candidates.append((gene, position, reference_aa, total, artifact, genuine))

    candidates.sort(key=lambda item: item[5], reverse=True)

    print(
        f"positions passing filter (whitelist, consistent, "
        f"genuine(non-artifact) count>={MIN_OBSERVATIONS}): {len(candidates)}"
    )
    print()
    header = f"{'gene':10s} {'pos':>6s} {'ref':>4s} {'total':>6s} {'artifact':>9s} {'genuine':>8s}  already_known"
    print(header)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(
            ["gene", "position", "reference_aa", "total_count", "artifact_count", "genuine_count", "already_known"]
        )
        for gene, position, reference_aa, total, artifact, genuine in candidates:
            already_known = (gene, position) in KNOWN_HOTSPOTS
            writer.writerow([gene, position, reference_aa, total, artifact, genuine, already_known])
            print(
                f"{gene:10s} {position:>6d} {reference_aa:>4s} {total:>6d} {artifact:>9d} {genuine:>8d}  {already_known}"
            )

    print()
    print(f"full candidate table written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
