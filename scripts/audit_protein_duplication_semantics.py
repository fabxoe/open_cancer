#!/usr/bin/env python
"""Audit protein insertion and tandem-duplication semantics without targets."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from open_cancer.hashing import sha256_file
from open_cancer.isoform_semantics import TranscriptAnnotation, load_annotation_index
from open_cancer.protein_duplication_semantics import (
    PROTEIN_DUPLICATION_SEMANTICS_VERSION,
    ProteinDuplicationSemanticResult,
    classify_protein_duplication,
    parse_protein_insertion_token,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRAIN = ROOT / "data" / "raw" / "train.csv"
DEFAULT_TEST = ROOT / "data" / "raw" / "test.csv"
DEFAULT_ANNOTATION = (
    ROOT
    / "data"
    / "external"
    / "ensembl_release_116"
    / "competition_gene_isoform_index.json"
)
DEFAULT_MANIFEST = (
    ROOT / "knowledge" / "ensembl_protein_duplication_semantics_v1.json"
)
DEFAULT_OUTPUT = ROOT / "reports" / "analysis" / "protein_duplication_semantics"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--test", type=Path, default=DEFAULT_TEST)
    parser.add_argument("--annotation-cache", type=Path, default=DEFAULT_ANNOTATION)
    parser.add_argument("--annotation-manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def _result_record(result: ProteinDuplicationSemanticResult) -> dict[str, Any]:
    payload = asdict(result)
    return {
        key: value
        for key, value in payload.items()
        if value is not None and value != () and value is not False
    }


def _audit_dataset(
    path: Path,
    annotation_index: dict[str, tuple[TranscriptAnnotation, ...]],
    *,
    dataset: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    parse_status_counts: Counter[str] = Counter()
    duplication_status_counts: Counter[str] = Counter()
    semantic_event_counts: Counter[str] = Counter()
    pure_insertion_tokens: Counter[str] = Counter()
    insertion_genes: Counter[str] = Counter()
    insertion_samples: set[str] = set()
    status_samples: dict[str, set[str]] = defaultdict(set)
    candidate_records: dict[tuple[Any, ...], dict[str, Any]] = {}
    rows = 0
    source_tokens = 0

    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or "ID" not in reader.fieldnames:
            raise ValueError(f"{path} must contain an ID column")
        genes = [
            field for field in reader.fieldnames if field not in {"ID", "SUBCLASS"}
        ]
        for row in reader:
            rows += 1
            sample_id = row["ID"]
            for gene in genes:
                cell = (row.get(gene) or "").strip()
                if not cell or cell.upper() == "WT":
                    continue
                for token in cell.split():
                    if not token or token.upper() == "WT":
                        continue
                    source_tokens += 1
                    upper = token.upper()
                    if "INS" not in upper or "DELINS" in upper:
                        continue
                    parsed = parse_protein_insertion_token(token)
                    result = classify_protein_duplication(
                        gene, token, annotation_index.get(gene, ())
                    )
                    parse_status_counts[parsed.parse_status] += 1
                    duplication_status_counts[result.duplication_status] += 1
                    semantic_event_counts[result.semantic_event_type] += 1
                    pure_insertion_tokens[result.normalized_token] += 1
                    insertion_genes[gene] += 1
                    insertion_samples.add(sample_id)
                    status_samples[result.duplication_status].add(sample_id)

                    key = (
                        result.normalized_token,
                        gene,
                        result.duplication_status,
                        result.duplication_source_start,
                        result.duplication_source_end,
                        result.three_prime_shift,
                    )
                    if key not in candidate_records:
                        candidate_records[key] = {
                            "dataset": dataset,
                            "gene": gene,
                            **_result_record(result),
                            "occurrences": 0,
                        }
                    candidate_records[key]["occurrences"] += 1

    records = sorted(
        candidate_records.values(),
        key=lambda item: (
            -int(item["occurrences"]),
            str(item["gene"]),
            str(item["normalized_token"]),
        ),
    )
    summary = {
        "dataset": dataset,
        "rows": rows,
        "gene_columns": len(genes),
        "source_tokens": source_tokens,
        "pure_insertion_occurrences": sum(pure_insertion_tokens.values()),
        "pure_insertion_unique_tokens": len(pure_insertion_tokens),
        "pure_insertion_genes": len(insertion_genes),
        "pure_insertion_samples": len(insertion_samples),
        "parse_status_counts": dict(sorted(parse_status_counts.items())),
        "duplication_status_counts": dict(
            sorted(duplication_status_counts.items())
        ),
        "semantic_event_counts": dict(sorted(semantic_event_counts.items())),
        "status_sample_counts": {
            status: len(samples) for status, samples in sorted(status_samples.items())
        },
        "top_tokens": [
            {"token": token, "occurrences": count}
            for token, count in sorted(
                pure_insertion_tokens.items(), key=lambda item: (-item[1], item[0])
            )[:100]
        ],
        "top_genes": [
            {"gene": gene, "occurrences": count}
            for gene, count in sorted(
                insertion_genes.items(), key=lambda item: (-item[1], item[0])
            )[:100]
        ],
    }
    return summary, records


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_args()
    if not args.annotation_cache.exists():
        raise FileNotFoundError(
            f"fixed annotation cache is required: {args.annotation_cache}"
        )
    annotation_index = load_annotation_index(args.annotation_cache)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    train_summary, train_records = _audit_dataset(
        args.train, annotation_index, dataset="train"
    )
    test_summary, test_records = _audit_dataset(
        args.test, annotation_index, dataset="test"
    )
    all_records = train_records + test_records
    single = [
        item for item in all_records if int(item.get("inserted_length", 0)) == 1
    ]
    multiple = [
        item for item in all_records if int(item.get("inserted_length", 0)) > 1
    ]
    shifted = [
        item
        for item in all_records
        if item.get("duplication_status") == "REFERENCE_CONFIRMED"
        and int(item.get("three_prime_shift", 0)) > 0
    ]
    reference_validation = {
        "parser_version": PROTEIN_DUPLICATION_SEMANTICS_VERSION,
        "annotation_cache": str(args.annotation_cache.relative_to(ROOT)),
        "annotation_cache_sha256": sha256_file(args.annotation_cache),
        "annotation_manifest": str(args.annotation_manifest.relative_to(ROOT)),
        "annotation_manifest_sha256": sha256_file(args.annotation_manifest),
        "train_status_counts": train_summary["duplication_status_counts"],
        "test_status_counts": test_summary["duplication_status_counts"],
        "reference_confirmed": [
            item
            for item in all_records
            if item.get("duplication_status") == "REFERENCE_CONFIRMED"
        ],
        "interpretation_limits": [
            "Competition rows do not identify the expressed transcript.",
            "MANE Select is preferred, then Ensembl canonical, then other isoforms.",
            "An unresolved isoform is never promoted by majority vote.",
            "SUBCLASS, test prevalence, and leaderboard results are not used.",
        ],
    }
    vocabulary = {
        "parser_version": PROTEIN_DUPLICATION_SEMANTICS_VERSION,
        "target_used": False,
        "test_distribution_used_for_rule": False,
        "train": train_summary,
        "test": test_summary,
    }
    three_prime = {
        "parser_version": PROTEIN_DUPLICATION_SEMANTICS_VERSION,
        "rule": "most C-terminal equivalent protein representation",
        "shifted_reference_confirmed_count": sum(
            int(item["occurrences"]) for item in shifted
        ),
        "shifted_records": shifted,
    }

    _write_json(args.output_dir / "vocabulary_audit.json", vocabulary)
    _write_json(args.output_dir / "single_residue_candidates.json", single)
    _write_json(args.output_dir / "multi_residue_candidates.json", multiple)
    _write_json(args.output_dir / "reference_validation.json", reference_validation)
    _write_json(args.output_dir / "three_prime_rule_audit.json", three_prime)
    print(json.dumps(vocabulary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
