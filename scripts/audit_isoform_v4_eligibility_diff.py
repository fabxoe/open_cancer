"""N6 audit: diff legacy-lexical vs parser-v4 substitution eligibility across the
full train+test corpus, ahead of freezing the isoform routing swap (Task #493).

Target-independent: SUBCLASS and Public LB are not used. Reuses the frozen
Ensembl release 116 annotation cache already approved for isoform work (Track B
team-lead exception, see PROJECT_CONTEXT.md). Deduplicates by (gene, raw token)
pair -- classification is deterministic given that pair plus the frozen
annotation index, so repeated occurrences across patients do not need to be
reclassified.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pandas as pd

from open_cancer.isoform_semantics import classify_token_semantics, load_annotation_index
from open_cancer.mutation_features import parse_mutation_token
from open_cancer.mutation_parser_contract import route_protein_mutation

ROOT = Path(__file__).resolve().parents[1]
ANNOTATION_CACHE = (
    ROOT / "data/external/ensembl_release_116/competition_gene_isoform_index.json"
)
OUTPUT_DIR = ROOT / "reports/analysis/n6_isoform_parser_v4_eligibility_audit"


def _legacy_eligible(raw_token: str) -> tuple[int, str] | None:
    """Pre-N6 eligibility check (isoform_semantics.py before this Task)."""

    parsed = parse_mutation_token(raw_token)
    if (
        parsed.token_shape != "substitution"
        or len(parsed.residue_positions) != 1
        or parsed.reference_amino_acid is None
        or len(parsed.reference_amino_acid) != 1
    ):
        return None
    return parsed.residue_positions[0], parsed.reference_amino_acid


def _legacy_classify(raw_token: str, annotations) -> str:
    eligibility = _legacy_eligible(raw_token)
    if eligibility is None or not annotations:
        return "COMPLEX_OR_UNMAPPABLE"
    position, reference = eligibility
    position_valid = tuple(item for item in annotations if position <= len(item.sequence))
    matches = tuple(item for item in position_valid if item.sequence[position - 1] == reference)
    mane = tuple(item for item in matches if item.is_mane_select)
    canonical = tuple(item for item in matches if item.is_canonical)
    other = tuple(item for item in matches if not item.is_mane_select and not item.is_canonical)
    if mane:
        return "MANE_MATCH"
    if canonical:
        return "CANONICAL_MATCH"
    if other:
        return "OTHER_ISOFORM_MATCH"
    if position_valid:
        return "POSITION_VALID_REF_MISMATCH"
    return "OUTSIDE_ALL_KNOWN_ISOFORMS"


def _collect_gene_tokens(csv_path: Path) -> dict[str, set[str]]:
    frame = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    genes = [column for column in frame.columns if column not in {"ID", "SUBCLASS"}]
    gene_tokens: dict[str, set[str]] = {}
    for gene in genes:
        tokens: set[str] = set()
        for cell in frame[gene]:
            cell = cell.strip()
            if not cell or cell == "WT":
                continue
            for raw_token in cell.split():
                if raw_token != "WT":
                    tokens.add(raw_token)
        if tokens:
            gene_tokens[gene] = tokens
    return gene_tokens


def main() -> None:
    annotation_index = load_annotation_index(ANNOTATION_CACHE)

    train_tokens = _collect_gene_tokens(ROOT / "data/raw/train.csv")
    test_tokens = _collect_gene_tokens(ROOT / "data/raw/test.csv")

    merged: dict[str, set[str]] = {}
    for gene, tokens in train_tokens.items():
        merged.setdefault(gene, set()).update(tokens)
    for gene, tokens in test_tokens.items():
        merged.setdefault(gene, set()).update(tokens)

    unique_pairs = sum(len(tokens) for tokens in merged.values())
    eligibility_diff: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    category_transition: Counter[str] = Counter()
    examples: dict[str, list[str]] = {}

    for gene, tokens in merged.items():
        annotations = annotation_index.get(gene, ())
        for raw_token in tokens:
            legacy_eligible = _legacy_eligible(raw_token) is not None
            routed = route_protein_mutation(raw_token)
            v4_eligible = (
                routed.route == "substitution"
                and routed.parse_status == "complete"
                and routed.event_type in {"missense", "no_change", "nonsense"}
            )

            if legacy_eligible != v4_eligible:
                if legacy_eligible and not v4_eligible:
                    direction = "legacy_only"
                    reason = routed.event_type
                else:
                    direction = "v4_only"
                    reason = f"legacy_shape_{parse_mutation_token(raw_token).token_shape}"
                eligibility_diff[direction] += 1
                key = f"{direction}:{reason}"
                reason_counts[key] += 1
                bucket = examples.setdefault(key, [])
                if len(bucket) < 5:
                    bucket.append(f"{gene}:{raw_token}")

            legacy_category = _legacy_classify(raw_token, annotations)
            new_category = classify_token_semantics(gene, raw_token, annotations).category
            if legacy_category != new_category:
                category_transition[f"{legacy_category}->{new_category}"] += 1

    result = {
        "annotation_cache": str(ANNOTATION_CACHE.relative_to(ROOT)),
        "unique_gene_token_pairs_scanned": unique_pairs,
        "genes_with_tokens": len(merged),
        "eligibility_diff_counts": dict(eligibility_diff),
        "eligibility_diff_rate": {
            direction: count / unique_pairs for direction, count in eligibility_diff.items()
        },
        "eligibility_diff_reasons": dict(sorted(reason_counts.items())),
        "eligibility_diff_examples": examples,
        "category_transition_counts": dict(
            sorted(category_transition.items(), key=lambda kv: -kv[1])
        ),
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "eligibility_diff.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
