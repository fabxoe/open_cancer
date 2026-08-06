"""Task #557: target-independent coverage and redundancy precheck for a candidate
"residue falls inside a known Pfam domain" indicator.

Reuses the same trusted isoform-matched (gene, token) population EXP-374/392
already rely on (`TRUSTED_POSITION_CATEGORIES` from `isoform_position_mask.py`)
and the same representative-isoform selection `isoform_relative_position.py`
uses, so both the domain check and the existing relative-position bin are
computed from the identical representative protein and position per token.

Depends on `knowledge/ensembl_protein_domain_annotation_v1.json` and
`data/external/ensembl_release_116/domain_features/pfam_domains_by_protein.json`,
produced by `scripts/fetch_ensembl_pfam_domain_catalog.py` -- run that first.

SUBCLASS and Public LB are not used anywhere in this script.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

import pandas as pd

from open_cancer.isoform_semantics import (
    TranscriptAnnotation,
    load_annotation_index,
    resolve_substitution_eligibility,
)
from open_cancer.isoform_position_mask import TRUSTED_POSITION_CATEGORIES
from open_cancer.isoform_semantics import classify_token_semantics

ROOT = Path(__file__).resolve().parents[1]
ANNOTATION_CACHE = (
    ROOT / "data/external/ensembl_release_116/competition_gene_isoform_index.json"
)
DOMAIN_COMBINED_PATH = (
    ROOT / "data/external/ensembl_release_116/domain_features/pfam_domains_by_protein.json"
)
DOMAIN_MANIFEST = ROOT / "knowledge/ensembl_protein_domain_annotation_v1.json"
OUTPUT_DIR = ROOT / "reports/analysis/pfam_domain_residue_coverage_precheck"
BIN_COUNT = 5


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


def _representative(
    gene_symbol: str,
    raw_token: str,
    annotation_index: dict[str, tuple[TranscriptAnnotation, ...]],
) -> tuple[str, int, int] | None:
    """Mirror IsoformRelativePositionTransformer's representative-isoform pick.

    Returns (protein_id, position, bin_value) for the same representative
    sequence the EXP-374/392 relative-position bin feature already uses, or
    None if the token is not in the trusted (MANE/canonical/other-isoform)
    population.
    """

    eligibility = resolve_substitution_eligibility(raw_token)
    if eligibility is None:
        return None
    position, reference = eligibility
    matches = tuple(
        annotation
        for annotation in annotation_index.get(gene_symbol, ())
        if 1 <= position <= len(annotation.sequence)
        and annotation.sequence[position - 1] == reference
    )
    if not matches:
        return None
    if any(item.is_mane_select for item in matches):
        matches = tuple(item for item in matches if item.is_mane_select)
    elif any(item.is_canonical for item in matches):
        matches = tuple(item for item in matches if item.is_canonical)
    else:
        matches = tuple(
            item for item in matches if not item.is_mane_select and not item.is_canonical
        )
    representative = min(matches, key=lambda item: (item.transcript_id, item.protein_id))
    relative_position = position / len(representative.sequence)
    bin_value = min(BIN_COUNT, max(1, math.ceil(relative_position * BIN_COUNT)))
    return representative.protein_id, position, bin_value


def _load_domain_intervals() -> dict[str, list[tuple[int, int]]]:
    combined = json.loads(DOMAIN_COMBINED_PATH.read_text(encoding="utf-8"))
    return {
        protein_id: [(item["start"], item["end"]) for item in features]
        for protein_id, features in combined.items()
    }


def _in_domain(position: int, intervals: list[tuple[int, int]]) -> bool:
    return any(start <= position <= end for start, end in intervals)


def main() -> None:
    if not DOMAIN_MANIFEST.is_file() or not DOMAIN_COMBINED_PATH.is_file():
        raise SystemExit(
            "먼저 uv run python scripts/fetch_ensembl_pfam_domain_catalog.py 를 실행하세요."
        )

    annotation_index = load_annotation_index(ANNOTATION_CACHE)
    domain_intervals = _load_domain_intervals()

    train_tokens = _collect_gene_tokens(ROOT / "data/raw/train.csv")
    test_tokens = _collect_gene_tokens(ROOT / "data/raw/test.csv")
    merged: dict[str, set[str]] = {}
    for source in (train_tokens, test_tokens):
        for gene, tokens in source.items():
            merged.setdefault(gene, set()).update(tokens)

    trusted_total = 0
    protein_has_domain_data = 0
    protein_missing_domain_data = 0
    in_domain_count = 0
    bin_by_domain: Counter[tuple[int, bool]] = Counter()
    examples_in_domain: list[str] = []
    examples_out_domain: list[str] = []

    for gene, tokens in merged.items():
        annotations = annotation_index.get(gene, ())
        for raw_token in tokens:
            category = classify_token_semantics(gene, raw_token, annotations).category
            if category not in TRUSTED_POSITION_CATEGORIES:
                continue
            resolved = _representative(gene, raw_token, annotation_index)
            if resolved is None:
                continue
            protein_id, position, bin_value = resolved
            trusted_total += 1
            intervals = domain_intervals.get(protein_id)
            if intervals is None:
                protein_missing_domain_data += 1
                continue
            protein_has_domain_data += 1
            hit = _in_domain(position, intervals)
            bin_by_domain[(bin_value, hit)] += 1
            if hit:
                in_domain_count += 1
                if len(examples_in_domain) < 8:
                    examples_in_domain.append(f"{gene}:{raw_token}")
            elif len(examples_out_domain) < 8:
                examples_out_domain.append(f"{gene}:{raw_token}")

    redundancy_table = {
        f"bin_{bin_value}": {
            "in_domain": bin_by_domain.get((bin_value, True), 0),
            "not_in_domain": bin_by_domain.get((bin_value, False), 0),
        }
        for bin_value in range(1, BIN_COUNT + 1)
    }

    result = {
        "trusted_gene_token_pairs": trusted_total,
        "pairs_with_domain_catalog_coverage": protein_has_domain_data,
        "pairs_missing_domain_catalog_coverage": protein_missing_domain_data,
        "domain_catalog_coverage_rate": (
            protein_has_domain_data / trusted_total if trusted_total else None
        ),
        "in_domain_count": in_domain_count,
        "in_domain_rate_among_covered": (
            in_domain_count / protein_has_domain_data if protein_has_domain_data else None
        ),
        "relative_position_bin_vs_in_domain_crosstab": redundancy_table,
        "examples_in_domain": examples_in_domain,
        "examples_not_in_domain": examples_out_domain,
        "interpretation_note": (
            "각 bin 안에 in_domain True/False가 모두 상당수 섞여 있으면 기존 "
            "isoform_relative_position bin으로 예측 불가능한 신규 정보가 있다는 뜻이다. "
            "반대로 bin 값이 in_domain을 거의 결정한다면(한쪽으로 쏠리면) #241 PIK3CA "
            "사례처럼 기존 피처와 중복일 가능성이 높다."
        ),
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "coverage_redundancy_precheck.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
