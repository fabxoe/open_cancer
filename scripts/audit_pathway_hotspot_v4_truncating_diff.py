"""N8 audit: diff the legacy-regex truncating classification currently used by
pathway burden and hotspot features (Task #422 roadmap, ahead of N8) against
the parser-v4-native truncating definition already adopted by EXP-558
(`compact_clinical_features._is_truncating`).

Motivation (found by static code audit, see reports/analysis/
n8_pathway_hotspot_truncating_audit/README.md): EXP-374's runner already fixes
the *stop-notation* gap for pathway/hotspot (X/Ter -> * before classification),
but `classify_mutation_token` (still used underneath, in
`open_cancer.mutation_features`) determines "frameshift" with a naive
`token.endswith("fs")` substring check and has no delins handling at all --
exactly the naive-substring failure mode PROJECT_CONTEXT.md warns about
(`SDEL133fs`, `721_722LA>FS`). This audit measures how often that naive check
disagrees with parser v4's dedicated grammar across the pathway- and
hotspot-relevant gene population.

Target-independent: SUBCLASS and Public LB are not used. Deduplicates by
(gene, raw token) pair -- classification is deterministic given that pair, so
repeated occurrences across patients do not need to be reclassified.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from open_cancer.hotspot_features import EXTENDED_HOTSPOTS
from open_cancer.mutation_features import classify_mutation_token
from open_cancer.mutation_parser_contract import route_protein_mutation
from open_cancer.robust_mutation_parser import normalize_stop_notation_token

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "data/raw/train.csv"
TEST = ROOT / "data/raw/test.csv"
PATHWAY_KNOWLEDGE = ROOT / "knowledge/canonical_pathways_sanchez_vega_v1.json"
OUTPUT_DIR = ROOT / "reports/analysis/n8_pathway_hotspot_truncating_audit"

_LEGACY_TRUNCATING_TYPES = frozenset({"nonsense", "frameshift"})


def _pathway_hotspot_genes() -> frozenset[str]:
    payload = json.loads(PATHWAY_KNOWLEDGE.read_text(encoding="utf-8"))
    pathway_genes = {
        gene for members in payload["pathways"].values() for gene in members
    }
    hotspot_genes = {gene for gene, _position, _ref in EXTENDED_HOTSPOTS}
    return frozenset(pathway_genes | hotspot_genes)


def _legacy_truncating(raw_token: str) -> bool:
    normalized = normalize_stop_notation_token(raw_token)
    return classify_mutation_token(normalized) in _LEGACY_TRUNCATING_TYPES


def _v4_truncating(raw_token: str) -> bool:
    routed = route_protein_mutation(raw_token)
    return (
        routed.route == "frameshift"
        or (routed.route == "substitution" and routed.event_type == "nonsense")
        or (routed.route == "delins" and routed.event_type == "nonsense")
    )


def _unique_gene_tokens(genes: frozenset[str]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for path in (TRAIN, TEST):
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            relevant = [name for name in reader.fieldnames or () if name in genes]
            for row in reader:
                for gene in relevant:
                    cell = row[gene]
                    if not cell:
                        continue
                    for token in cell.split():
                        if token.upper() == "WT":
                            continue
                        pairs.add((gene, token))
    return pairs


def main() -> None:
    genes = _pathway_hotspot_genes()
    pairs = _unique_gene_tokens(genes)

    direction_counts: Counter[str] = Counter()
    v4_route_of_new_truncating: Counter[str] = Counter()
    v4_route_of_lost_truncating: Counter[str] = Counter()
    diffs: list[dict[str, object]] = []

    for gene, token in sorted(pairs):
        legacy = _legacy_truncating(token)
        v4 = _v4_truncating(token)
        if legacy == v4:
            direction_counts["agree"] += 1
            continue
        routed = route_protein_mutation(token)
        if v4 and not legacy:
            direction_counts["v4_only_truncating"] += 1
            v4_route_of_new_truncating[f"{routed.route}:{routed.event_type}"] += 1
        else:
            direction_counts["legacy_only_truncating"] += 1
            v4_route_of_lost_truncating[f"{routed.route}:{routed.event_type}"] += 1
        diffs.append(
            {
                "gene": gene,
                "token": token,
                "legacy_truncating": legacy,
                "v4_truncating": v4,
                "v4_route": routed.route,
                "v4_event_type": routed.event_type,
            }
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "pathway_hotspot_gene_count": len(genes),
        "unique_gene_token_pairs": len(pairs),
        "direction_counts": dict(direction_counts),
        "v4_route_of_new_truncating": dict(v4_route_of_new_truncating),
        "v4_route_of_lost_truncating": dict(v4_route_of_lost_truncating),
    }
    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUTPUT_DIR / "diffs.json").write_text(
        json.dumps(diffs, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
