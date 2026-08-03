#!/usr/bin/env python
"""Build a frozen Ensembl index and audit competition residue tokens."""

from __future__ import annotations

import argparse
import csv
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from open_cancer.hashing import sha256_file
from open_cancer.isoform_semantics import (
    ISOFORM_CATEGORIES,
    audit_mutation_csv,
    build_annotation_index,
    load_gene_biotypes,
    load_annotation_index,
    serialise_annotation_index,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "knowledge" / "ensembl_isoform_annotation_v1.json"
DEFAULT_EXTERNAL = ROOT / "data" / "external" / "ensembl_release_116"
DEFAULT_CACHE = DEFAULT_EXTERNAL / "competition_gene_isoform_index.json"
DEFAULT_OUTPUT = ROOT / "reports" / "analysis" / "isoform_residue_semantics"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--external-dir", type=Path, default=DEFAULT_EXTERNAL)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--train", type=Path, default=ROOT / "data/raw/train.csv")
    parser.add_argument("--test", type=Path, default=ROOT / "data/raw/test.csv")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--rebuild-cache", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    args.external_dir.mkdir(parents=True, exist_ok=True)
    local_sources: dict[str, Path] = {}
    for source in manifest["sources"]:
        path = args.external_dir / source["filename"]
        if args.download and not path.exists():
            _download(source["url"], path)
        if not path.exists():
            raise FileNotFoundError(f"missing {path}; rerun with --download")
        actual_sha = sha256_file(path)
        if actual_sha != source["sha256"]:
            raise ValueError(
                f"SHA-256 mismatch for {path}: expected {source['sha256']}, got {actual_sha}"
            )
        local_sources[source["role"]] = path

    genes = _gene_columns(args.train)
    if args.rebuild_cache or not args.cache.exists():
        annotation_index = build_annotation_index(
            local_sources["gene_annotation_gtf"],
            local_sources["protein_fasta"],
            allowed_genes=set(genes),
        )
        serialise_annotation_index(annotation_index, args.cache)
    else:
        annotation_index = load_annotation_index(args.cache)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    token_dir = ROOT / "data" / "processed" / "isoform_residue_semantics"
    gene_biotypes = load_gene_biotypes(
        local_sources["gene_annotation_gtf"], allowed_genes=set(genes)
    )
    train_audit = audit_mutation_csv(
        args.train,
        annotation_index,
        dataset_name="train",
        gene_biotypes=gene_biotypes,
        token_output_path=token_dir / "train_token_semantics.csv",
    )
    test_audit = audit_mutation_csv(
        args.test,
        annotation_index,
        dataset_name="test",
        gene_biotypes=gene_biotypes,
        token_output_path=token_dir / "test_token_semantics.csv",
    )

    mapped_genes = set(annotation_index)
    gtf_mapped_genes = set(gene_biotypes)
    permission = manifest["competition_external_annotation_permission"]
    audit = {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis_only": True,
        "target_used": False,
        "public_leaderboard_used": False,
        "external_annotation_permission": permission,
        "annotation_manifest_path": str(args.manifest.relative_to(ROOT)),
        "annotation_manifest_sha256": sha256_file(args.manifest),
        "annotation_release": manifest["ensembl_release"],
        "annotation_cache_sha256": sha256_file(args.cache),
        "gene_columns": len(genes),
        "gtf_mapped_gene_symbols": len(gtf_mapped_genes & set(genes)),
        "gtf_gene_symbol_coverage": len(gtf_mapped_genes & set(genes)) / len(genes),
        "protein_sequence_mapped_gene_symbols": len(mapped_genes & set(genes)),
        "protein_sequence_gene_coverage": len(mapped_genes & set(genes)) / len(genes),
        "non_protein_coding_mapped_genes": sorted(
            gene
            for gene in set(genes) & gtf_mapped_genes
            if gene_biotypes.get(gene) != "protein_coding"
        ),
        "unmapped_gene_symbols": sorted(set(genes) - gtf_mapped_genes),
        "transcript_count": sum(len(items) for items in annotation_index.values()),
        "mane_gene_count": sum(
            any(item.is_mane_select for item in items)
            for items in annotation_index.values()
        ),
        "canonical_gene_count": sum(
            any(item.is_canonical for item in items)
            for items in annotation_index.values()
        ),
        "train": train_audit,
        "test": test_audit,
        "train_test_category_rate_delta": {
            category: test_audit["category_rates"][category]
            - train_audit["category_rates"][category]
            for category in ISOFORM_CATEGORIES
        },
        "b2_blocked": permission != "CONFIRMED_ALLOWED",
        "b2_block_reason": (
            "대회 주최측의 외부 annotation 사용 허용이 확인되지 않아 분석 전용으로 제한"
            if permission != "CONFIRMED_ALLOWED"
            else None
        ),
    }
    audit_path = args.output_dir / "audit.json"
    audit_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"audit": str(audit_path), "summary": _summary(audit)}, indent=2))


def _gene_columns(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        header = next(csv.reader(handle))
    return [column for column in header if column not in {"ID", "SUBCLASS"}]


def _download(url: str, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".part")
    urllib.request.urlretrieve(url, temporary)
    temporary.replace(path)


def _summary(audit: dict[str, object]) -> dict[str, object]:
    train = audit["train"]
    test = audit["test"]
    assert isinstance(train, dict) and isinstance(test, dict)
    return {
        "gtf_gene_symbol_coverage": audit["gtf_gene_symbol_coverage"],
        "protein_sequence_gene_coverage": audit[
            "protein_sequence_gene_coverage"
        ],
        "train_tokens": train["tokens_total"],
        "test_tokens": test["tokens_total"],
        "train_category_rates": train["category_rates"],
        "test_category_rates": test["category_rates"],
        "b2_blocked": audit["b2_blocked"],
    }


if __name__ == "__main__":
    main()
