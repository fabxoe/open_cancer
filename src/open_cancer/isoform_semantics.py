"""Target-independent protein isoform and residue-token semantic QC."""

from __future__ import annotations

import csv
import gzip
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence, TextIO

from open_cancer.mutation_features import ParsedMutationToken, parse_mutation_token


ISOFORM_CATEGORIES = (
    "MANE_MATCH",
    "CANONICAL_MATCH",
    "OTHER_ISOFORM_MATCH",
    "POSITION_VALID_REF_MISMATCH",
    "OUTSIDE_ALL_KNOWN_ISOFORMS",
    "COMPLEX_OR_UNMAPPABLE",
)


@dataclass(frozen=True)
class TranscriptAnnotation:
    gene_id: str
    gene_symbol: str
    gene_biotype: str
    transcript_id: str
    transcript_biotype: str
    protein_id: str
    is_mane_select: bool
    is_canonical: bool
    sequence: str


@dataclass(frozen=True)
class TokenSemanticResult:
    category: str
    gene_symbol: str
    raw_token: str
    position: int | None
    reference_amino_acid: str | None
    matched_transcript_ids: tuple[str, ...]
    matched_protein_ids: tuple[str, ...]


def parse_gtf_attributes(raw: str) -> dict[str, str]:
    """Parse the semicolon-delimited attribute field of an Ensembl GTF row."""

    result: dict[str, str] = {}
    for item in raw.strip().rstrip(";").split(";"):
        item = item.strip()
        if not item:
            continue
        key, _, value = item.partition(" ")
        parsed_value = value.strip().strip('"')
        if key in result:
            result[key] = f"{result[key]},{parsed_value}"
        else:
            result[key] = parsed_value
    return result


def iter_fasta(handle: TextIO) -> Iterator[tuple[str, str, dict[str, str]]]:
    """Yield identifier, sequence and Ensembl-style header key/value pairs."""

    identifier: str | None = None
    metadata: dict[str, str] = {}
    chunks: list[str] = []
    for raw_line in handle:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if identifier is not None:
                yield identifier, "".join(chunks), metadata
            fields = line[1:].split()
            identifier = fields[0].split(".", maxsplit=1)[0]
            metadata = {}
            for field in fields[1:]:
                key, separator, value = field.partition(":")
                if separator:
                    metadata[key] = value
            chunks = []
        elif identifier is not None:
            chunks.append(line)
    if identifier is not None:
        yield identifier, "".join(chunks), metadata


def _open_text(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def build_annotation_index(
    gtf_path: Path,
    peptide_fasta_path: Path,
    *,
    allowed_genes: set[str] | None = None,
) -> dict[str, tuple[TranscriptAnnotation, ...]]:
    """Build a compact gene-symbol index without materialising either source file."""

    transcript_metadata: dict[str, dict[str, str | bool]] = {}
    with _open_text(gtf_path) as handle:
        for line in handle:
            if not line or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9 or fields[2] not in {"transcript", "CDS"}:
                continue
            attributes = parse_gtf_attributes(fields[8])
            transcript_id = attributes.get("transcript_id", "").split(".", 1)[0]
            gene_symbol = attributes.get("gene_name", "")
            if not transcript_id or not gene_symbol:
                continue
            if allowed_genes is not None and gene_symbol not in allowed_genes:
                continue
            record = transcript_metadata.setdefault(
                transcript_id,
                {
                    "gene_id": attributes.get("gene_id", "").split(".", 1)[0],
                    "gene_symbol": gene_symbol,
                    "gene_biotype": attributes.get("gene_biotype", ""),
                    "transcript_biotype": attributes.get("transcript_biotype", ""),
                    "protein_id": "",
                    "is_mane_select": False,
                    "is_canonical": False,
                },
            )
            protein_id = attributes.get("protein_id", "").split(".", 1)[0]
            if protein_id:
                record["protein_id"] = protein_id
            tags = set(attributes.get("tag", "").split(","))
            record["is_mane_select"] = bool(record["is_mane_select"]) or any(
                tag.startswith("MANE_Select") for tag in tags
            )
            record["is_canonical"] = bool(record["is_canonical"]) or (
                "Ensembl_canonical" in tags
            )

    by_gene: dict[str, list[TranscriptAnnotation]] = defaultdict(list)
    with _open_text(peptide_fasta_path) as handle:
        for protein_id, sequence, fasta_metadata in iter_fasta(handle):
            transcript_id = fasta_metadata.get("transcript", "").split(".", 1)[0]
            metadata = transcript_metadata.get(transcript_id)
            if metadata is None or not sequence:
                continue
            expected_protein = str(metadata["protein_id"])
            if expected_protein and expected_protein != protein_id:
                continue
            annotation = TranscriptAnnotation(
                gene_id=str(metadata["gene_id"]),
                gene_symbol=str(metadata["gene_symbol"]),
                gene_biotype=str(metadata["gene_biotype"]),
                transcript_id=transcript_id,
                transcript_biotype=str(metadata["transcript_biotype"]),
                protein_id=protein_id,
                is_mane_select=bool(metadata["is_mane_select"]),
                is_canonical=bool(metadata["is_canonical"]),
                sequence=sequence.rstrip("*"),
            )
            by_gene[annotation.gene_symbol].append(annotation)

    return {
        gene: tuple(
            sorted(
                annotations,
                key=lambda item: (
                    not item.is_mane_select,
                    not item.is_canonical,
                    item.transcript_id,
                    item.protein_id,
                ),
            )
        )
        for gene, annotations in sorted(by_gene.items())
    }


def load_gene_biotypes(
    gtf_path: Path, *, allowed_genes: set[str] | None = None
) -> dict[str, str]:
    """Read one stable gene-symbol to biotype mapping from a GTF stream."""

    result: dict[str, str] = {}
    with _open_text(gtf_path) as handle:
        for line in handle:
            if not line or line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9 or fields[2] != "gene":
                continue
            attributes = parse_gtf_attributes(fields[8])
            gene = attributes.get("gene_name", "")
            if not gene or (allowed_genes is not None and gene not in allowed_genes):
                continue
            result.setdefault(gene, attributes.get("gene_biotype", "unknown"))
    return result


def classify_token_semantics(
    gene_symbol: str,
    raw_token: str,
    annotations: Sequence[TranscriptAnnotation],
) -> TokenSemanticResult:
    """Classify a simple residue token against all known protein isoforms."""

    parsed = parse_mutation_token(raw_token)
    if not _is_simple_reference_token(parsed) or not annotations:
        return _semantic_result("COMPLEX_OR_UNMAPPABLE", gene_symbol, parsed, ())

    position = parsed.residue_positions[0]
    reference = parsed.reference_amino_acid
    assert reference is not None
    position_valid = tuple(item for item in annotations if position <= len(item.sequence))
    matches = tuple(
        item for item in position_valid if item.sequence[position - 1] == reference
    )
    mane_matches = tuple(item for item in matches if item.is_mane_select)
    canonical_matches = tuple(item for item in matches if item.is_canonical)
    other_matches = tuple(
        item for item in matches if not item.is_mane_select and not item.is_canonical
    )

    if mane_matches:
        return _semantic_result("MANE_MATCH", gene_symbol, parsed, mane_matches)
    if canonical_matches:
        return _semantic_result(
            "CANONICAL_MATCH", gene_symbol, parsed, canonical_matches
        )
    if other_matches:
        return _semantic_result(
            "OTHER_ISOFORM_MATCH", gene_symbol, parsed, other_matches
        )
    if position_valid:
        return _semantic_result(
            "POSITION_VALID_REF_MISMATCH", gene_symbol, parsed, position_valid
        )
    return _semantic_result(
        "OUTSIDE_ALL_KNOWN_ISOFORMS", gene_symbol, parsed, annotations
    )


def _is_simple_reference_token(parsed: ParsedMutationToken) -> bool:
    return (
        parsed.token_shape == "substitution"
        and len(parsed.residue_positions) == 1
        and parsed.reference_amino_acid is not None
        and len(parsed.reference_amino_acid) == 1
    )


def _semantic_result(
    category: str,
    gene_symbol: str,
    parsed: ParsedMutationToken,
    matches: Sequence[TranscriptAnnotation],
) -> TokenSemanticResult:
    return TokenSemanticResult(
        category=category,
        gene_symbol=gene_symbol,
        raw_token=parsed.raw,
        position=parsed.residue_positions[0]
        if len(parsed.residue_positions) == 1
        else None,
        reference_amino_acid=parsed.reference_amino_acid,
        matched_transcript_ids=tuple(item.transcript_id for item in matches),
        matched_protein_ids=tuple(item.protein_id for item in matches),
    )


def audit_mutation_csv(
    csv_path: Path,
    annotation_index: Mapping[str, Sequence[TranscriptAnnotation]],
    *,
    dataset_name: str,
    gene_biotypes: Mapping[str, str] | None = None,
    token_output_path: Path | None = None,
) -> dict[str, object]:
    """Stream one competition CSV and aggregate target-independent token semantics."""

    category_counts: Counter[str] = Counter()
    gene_category_counts: dict[str, Counter[str]] = defaultdict(Counter)
    sample_category_presence: Counter[str] = Counter()
    mutated_gene_cells = 0
    tokens_total = 0
    simple_tokens = 0
    mapped_gene_cells = 0
    non_protein_coding_gene_cells = 0
    other_match_beyond_primary_length = 0
    max_position_low_confidence_cells = 0

    output_handle: TextIO | None = None
    writer: csv.DictWriter[str] | None = None
    if token_output_path is not None:
        token_output_path.parent.mkdir(parents=True, exist_ok=True)
        output_handle = token_output_path.open("w", encoding="utf-8", newline="")
        writer = csv.DictWriter(
            output_handle,
            fieldnames=(
                "dataset",
                "ID",
                "gene",
                "token",
                "category",
                "position",
                "reference_amino_acid",
                "matched_transcript_ids",
                "matched_protein_ids",
            ),
        )
        writer.writeheader()

    try:
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None or "ID" not in reader.fieldnames:
                raise ValueError(f"{csv_path} must contain an ID column")
            genes = [
                column
                for column in reader.fieldnames
                if column not in {"ID", "SUBCLASS"}
            ]
            rows = 0
            for row in reader:
                rows += 1
                sample_categories: set[str] = set()
                for gene in genes:
                    cell = (row.get(gene) or "").strip()
                    if not cell or cell == "WT":
                        continue
                    mutated_gene_cells += 1
                    annotations = annotation_index.get(gene, ())
                    gene_biotype = (gene_biotypes or {}).get(gene)
                    if gene_biotype and gene_biotype != "protein_coding":
                        non_protein_coding_gene_cells += 1
                    if annotations:
                        mapped_gene_cells += 1
                    cell_results: list[TokenSemanticResult] = []
                    for raw_token in cell.split():
                        if raw_token == "WT":
                            continue
                        result = classify_token_semantics(
                            gene, raw_token, annotations
                        )
                        cell_results.append(result)
                        tokens_total += 1
                        if parse_mutation_token(raw_token).token_shape == "substitution":
                            simple_tokens += 1
                        category_counts[result.category] += 1
                        gene_category_counts[gene][result.category] += 1
                        sample_categories.add(result.category)
                        if (
                            result.category == "OTHER_ISOFORM_MATCH"
                            and result.position is not None
                        ):
                            primary = tuple(
                                item
                                for item in annotations
                                if item.is_mane_select or item.is_canonical
                            )
                            if primary and result.position > max(
                                len(item.sequence) for item in primary
                            ):
                                other_match_beyond_primary_length += 1
                        if writer is not None:
                            writer.writerow(
                                {
                                    "dataset": dataset_name,
                                    "ID": row["ID"],
                                    "gene": gene,
                                    "token": raw_token,
                                    "category": result.category,
                                    "position": result.position or "",
                                    "reference_amino_acid": result.reference_amino_acid
                                    or "",
                                    "matched_transcript_ids": ";".join(
                                        result.matched_transcript_ids
                                    ),
                                    "matched_protein_ids": ";".join(
                                        result.matched_protein_ids
                                    ),
                                }
                            )
                    if cell_results:
                        max_result = max(
                            cell_results,
                            key=lambda result: result.position or -1,
                        )
                        if max_result.category in {
                            "POSITION_VALID_REF_MISMATCH",
                            "OUTSIDE_ALL_KNOWN_ISOFORMS",
                            "COMPLEX_OR_UNMAPPABLE",
                        }:
                            max_position_low_confidence_cells += 1
                sample_category_presence.update(sample_categories)
    finally:
        if output_handle is not None:
            output_handle.close()

    return {
        "dataset": dataset_name,
        "rows": rows,
        "gene_columns": len(genes),
        "mutated_gene_cells": mutated_gene_cells,
        "mapped_gene_cells": mapped_gene_cells,
        "mapped_gene_cell_rate": _ratio(mapped_gene_cells, mutated_gene_cells),
        "non_protein_coding_gene_cells": non_protein_coding_gene_cells,
        "tokens_total": tokens_total,
        "simple_substitution_tokens": simple_tokens,
        "simple_substitution_rate": _ratio(simple_tokens, tokens_total),
        "category_counts": {
            category: category_counts[category] for category in ISOFORM_CATEGORIES
        },
        "category_rates": {
            category: _ratio(category_counts[category], tokens_total)
            for category in ISOFORM_CATEGORIES
        },
        "other_isoform_match_beyond_mane_or_canonical_length": (
            other_match_beyond_primary_length
        ),
        "other_isoform_match_beyond_mane_or_canonical_length_rate": _ratio(
            other_match_beyond_primary_length, tokens_total
        ),
        "sample_category_presence_counts": {
            category: sample_category_presence[category]
            for category in ISOFORM_CATEGORIES
        },
        "max_position_low_confidence_cells": max_position_low_confidence_cells,
        "max_position_low_confidence_rate": _ratio(
            max_position_low_confidence_cells, mutated_gene_cells
        ),
        "top_genes_by_token_count": [
            {
                "gene": gene,
                "token_count": sum(counts.values()),
                "category_counts": {
                    category: counts[category] for category in ISOFORM_CATEGORIES
                },
            }
            for gene, counts in sorted(
                gene_category_counts.items(),
                key=lambda item: (-sum(item[1].values()), item[0]),
            )[:100]
        ],
    }


def serialise_annotation_index(
    annotation_index: Mapping[str, Sequence[TranscriptAnnotation]], path: Path
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        gene: [asdict(item) for item in annotations]
        for gene, annotations in annotation_index.items()
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def load_annotation_index(
    path: Path,
) -> dict[str, tuple[TranscriptAnnotation, ...]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        gene: tuple(TranscriptAnnotation(**item) for item in items)
        for gene, items in payload.items()
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None
