"""Deterministic sparse features parsed directly from mutation strings."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy import sparse

from open_cancer.hashing import sha256_file, sha256_lines


FEATURE_FACTORY_VERSION = "1.1.0"
MUTATION_TYPES = ("missense", "synonymous", "nonsense", "frameshift", "complex")
GENE_FEATURES = ("mutated", *MUTATION_TYPES, "missing")
RESIDUE_POSITION_FEATURES = (
    "min_residue_position",
    "max_residue_position",
    "residue_position_span",
    "residue_position_observed",
)
POSITION_MISSING_POLICIES = ("zero", "indicator")
POSITION_TOKEN_SCOPES = ("include_complex", "exclude_complex")
POSITION_TRANSFORMS = ("raw", "coarse_bin")
GLOBAL_FEATURES = (
    "sample__mutated_gene_count",
    "sample__total_variant_count",
    "sample__multi_variant_gene_count",
    "sample__missing_gene_count",
    *(f"sample__{mutation_type}_count" for mutation_type in MUTATION_TYPES),
)
ROBUST_GLOBAL_FEATURES = (
    "sample__mutated_gene_count_log1p",
    "sample__total_variant_count_log1p",
    "sample__multi_variant_gene_count_log1p",
    *(f"sample__{mutation_type}_ratio" for mutation_type in MUTATION_TYPES),
    "sample__multi_variant_gene_ratio",
    "sample__missing_gene_ratio",
)
LOG_BURDEN_FEATURES = ROBUST_GLOBAL_FEATURES[:3]
SAMPLE_DISTRIBUTION_FEATURES = (
    *(f"sample__{mutation_type}_count_log1p" for mutation_type in MUTATION_TYPES),
    *(f"sample__{mutation_type}_gene_count" for mutation_type in MUTATION_TYPES),
    *(f"sample__{mutation_type}_gene_count_log1p" for mutation_type in MUTATION_TYPES),
    "sample__truncating_count",
    "sample__truncating_count_log1p",
    "sample__damaging_count",
    "sample__damaging_count_log1p",
    "sample__mutation_type_diversity",
    "sample__mutation_type_entropy",
    "sample__variants_per_mutated_gene_mean",
    "sample__max_variants_per_gene",
    "sample__single_variant_gene_count",
    "sample__single_variant_gene_count_log1p",
)
EXPANDED_DISTRIBUTION_FEATURES = (
    *LOG_BURDEN_FEATURES,
    *SAMPLE_DISTRIBUTION_FEATURES,
)

_SUBSTITUTION = re.compile(r"^([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]*)([ACDEFGHIKLMNPQRSTVWY*])$")
_RESIDUE_POSITION = re.compile(r"[1-9][0-9]*")
_LEADING_AMINO_ACIDS = re.compile(r"^([ACDEFGHIKLMNPQRSTVWY*]+)")
_TRAILING_AMINO_ACIDS = re.compile(r"([ACDEFGHIKLMNPQRSTVWY*]+)$")


@dataclass(frozen=True)
class ParsedMutationToken:
    """A conservative lexical parse of one protein-mutation token.

    Positions are protein residue indices written in the supplied token. They
    are not genomic coordinates, codon nucleotide positions, or transcript-
    normalized coordinates.
    """

    raw: str
    mutation_type: str
    residue_positions: tuple[int, ...]
    reference_amino_acid: str | None
    alternate_amino_acid: str | None
    token_shape: str
    is_complex: bool


@dataclass(frozen=True)
class ParsedMutationCell:
    """Structured representation of one gene cell."""

    tokens: tuple[ParsedMutationToken, ...]
    token_count: int
    residue_positions: tuple[int, ...]
    mutation_types: frozenset[str]
    has_complex_token: bool


def classify_mutation_token(token: str) -> str:
    """Classify one source token without requiring transcript information."""

    substitution = _SUBSTITUTION.fullmatch(token)
    if substitution is not None:
        reference, _, alternate = substitution.groups()
        if alternate == reference:
            return "synonymous"
        if alternate == "*":
            return "nonsense"
        return "missense"
    if token.endswith("fs"):
        return "frameshift"
    return "complex"


def parse_mutation_token(token: str) -> ParsedMutationToken:
    """Parse only information explicitly present in a mutation token."""

    raw = token.strip()
    mutation_type = classify_mutation_token(raw)
    positions = tuple(int(value) for value in _RESIDUE_POSITION.findall(raw))
    reference: str | None = None
    alternate: str | None = None

    substitution = _SUBSTITUTION.fullmatch(raw)
    if substitution is not None:
        reference, _, alternate = substitution.groups()
        token_shape = "substitution"
    elif raw.endswith("fs"):
        reference_match = _LEADING_AMINO_ACIDS.match(raw)
        reference = reference_match.group(1) if reference_match else None
        token_shape = "frameshift"
    elif ">" in raw:
        left, right = raw.split(">", maxsplit=1)
        reference_match = _TRAILING_AMINO_ACIDS.search(left)
        alternate_match = _LEADING_AMINO_ACIDS.match(right)
        reference = reference_match.group(1) if reference_match else None
        alternate = alternate_match.group(1) if alternate_match else None
        token_shape = "range_change" if len(positions) > 1 or "_" in raw else "complex_change"
    else:
        token_shape = "complex"

    return ParsedMutationToken(
        raw=raw,
        mutation_type=mutation_type,
        residue_positions=positions,
        reference_amino_acid=reference,
        alternate_amino_acid=alternate,
        token_shape=token_shape,
        is_complex=mutation_type == "complex",
    )


def parse_mutation_cell(cell: str) -> ParsedMutationCell:
    """Parse a WT/blank/multi-token gene cell without using the target."""

    parsed = tuple(
        parse_mutation_token(token)
        for token in cell.split()
        if token and token != "WT"
    )
    positions = tuple(
        position
        for token in parsed
        for position in token.residue_positions
    )
    return ParsedMutationCell(
        tokens=parsed,
        token_count=len(parsed),
        residue_positions=positions,
        mutation_types=frozenset(token.mutation_type for token in parsed),
        has_complex_token=any(token.is_complex for token in parsed),
    )


@dataclass(frozen=True)
class FeatureMatrix:
    matrix: sparse.csr_matrix
    ids: list[str]
    labels: list[str] | None
    parsing_qc: dict[str, Any]


def feature_names(
    genes: list[str],
    *,
    include_robust_aggregates: bool = False,
    selected_robust_aggregates: tuple[str, ...] | None = None,
    selected_position_features: tuple[str, ...] | None = None,
    position_missing_policy: str = "zero",
) -> list[str]:
    """Return the stable feature order shared by train and test."""

    robust_features = _resolve_robust_features(
        include_robust_aggregates=include_robust_aggregates,
        selected_robust_aggregates=selected_robust_aggregates,
    )
    position_features = _resolve_position_features(
        selected_position_features,
        missing_policy=position_missing_policy,
    )
    per_gene_features = (*GENE_FEATURES, *position_features)
    return [
        *GLOBAL_FEATURES,
        *robust_features,
        *(f"{gene}__{feature}" for gene in genes for feature in per_gene_features),
    ]


def _read_sparse_features(
    path: Path,
    *,
    genes: list[str],
    has_labels: bool,
    include_robust_aggregates: bool,
    selected_robust_aggregates: tuple[str, ...] | None,
    selected_position_features: tuple[str, ...] | None,
    position_missing_policy: str,
    position_token_scope: str,
    position_transform: str,
    position_bin_width: int,
) -> FeatureMatrix:
    robust_features = _resolve_robust_features(
        include_robust_aggregates=include_robust_aggregates,
        selected_robust_aggregates=selected_robust_aggregates,
    )
    position_features = _resolve_position_features(
        selected_position_features,
        missing_policy=position_missing_policy,
    )
    per_gene_features = (*GENE_FEATURES, *position_features)
    names = feature_names(
        genes,
        include_robust_aggregates=include_robust_aggregates,
        selected_robust_aggregates=selected_robust_aggregates,
        selected_position_features=position_features,
        position_missing_policy=position_missing_policy,
    )
    active_global_features = (
        *GLOBAL_FEATURES,
        *robust_features,
    )
    global_index = {name: index for index, name in enumerate(active_global_features)}
    gene_offset = len(active_global_features)
    gene_stride = len(per_gene_features)
    gene_feature_index = {name: index for index, name in enumerate(per_gene_features)}
    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    ids: list[str] = []
    labels: list[str] | None = [] if has_labels else None
    parsing_qc: dict[str, Any] = {
        "non_wt_gene_cells": 0,
        "mutation_tokens_total": 0,
        "tokens_with_residue_positions": 0,
        "tokens_without_residue_positions": 0,
        "complex_tokens": 0,
        "multi_position_tokens": 0,
        "token_shape_counts": {},
    }

    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        header = next(reader)
        expected_prefix = ["ID", "SUBCLASS"] if has_labels else ["ID"]
        if header[: len(expected_prefix)] != expected_prefix:
            raise ValueError(f"{path}: 앞 열은 {','.join(expected_prefix)}여야 합니다.")
        source_genes = header[len(expected_prefix) :]
        if source_genes != genes:
            raise ValueError(f"{path}: 유전자 열 이름 또는 순서가 기준과 다릅니다.")

        for row_index, row in enumerate(reader):
            if len(row) != len(header):
                raise ValueError(f"{path}: {row_index + 2}행의 열 수가 header와 다릅니다.")
            ids.append(row[0])
            feature_start = 2 if has_labels else 1
            if labels is not None:
                labels.append(row[1])

            global_counts = {name: 0 for name in GLOBAL_FEATURES}
            type_gene_counts = {mutation_type: 0 for mutation_type in MUTATION_TYPES}
            max_variants_per_gene = 0
            single_variant_gene_count = 0
            for gene_index, cell in enumerate(row[feature_start:]):
                base = gene_offset + gene_index * gene_stride
                if cell == "":
                    global_counts["sample__missing_gene_count"] += 1
                    rows.append(row_index)
                    columns.append(base + gene_feature_index["missing"])
                    values.append(1.0)
                    continue

                parsed_cell = parse_mutation_cell(cell)
                if not parsed_cell.tokens:
                    continue

                parsing_qc["non_wt_gene_cells"] += 1
                parsing_qc["mutation_tokens_total"] += parsed_cell.token_count
                global_counts["sample__mutated_gene_count"] += 1
                global_counts["sample__total_variant_count"] += parsed_cell.token_count
                max_variants_per_gene = max(
                    max_variants_per_gene,
                    parsed_cell.token_count,
                )
                if parsed_cell.token_count == 1:
                    single_variant_gene_count += 1
                if parsed_cell.token_count > 1:
                    global_counts["sample__multi_variant_gene_count"] += 1
                rows.append(row_index)
                columns.append(base + gene_feature_index["mutated"])
                values.append(1.0)

                for token in parsed_cell.tokens:
                    global_counts[f"sample__{token.mutation_type}_count"] += 1
                    shape_counts = parsing_qc["token_shape_counts"]
                    shape_counts[token.token_shape] = shape_counts.get(token.token_shape, 0) + 1
                    if token.residue_positions:
                        parsing_qc["tokens_with_residue_positions"] += 1
                    else:
                        parsing_qc["tokens_without_residue_positions"] += 1
                    if token.is_complex:
                        parsing_qc["complex_tokens"] += 1
                    if len(token.residue_positions) > 1:
                        parsing_qc["multi_position_tokens"] += 1

                for mutation_type in sorted(parsed_cell.mutation_types):
                    type_gene_counts[mutation_type] += 1
                    rows.append(row_index)
                    columns.append(base + gene_feature_index[mutation_type])
                    values.append(1.0)
                eligible_positions = _eligible_residue_positions(
                    parsed_cell,
                    token_scope=position_token_scope,
                )
                if eligible_positions:
                    transformed_positions = _transform_residue_positions(
                        eligible_positions,
                        transform=position_transform,
                        bin_width=position_bin_width,
                    )
                    position_values = {
                        "min_residue_position": min(transformed_positions),
                        "max_residue_position": max(transformed_positions),
                        "residue_position_span": (
                            max(transformed_positions) - min(transformed_positions)
                        ),
                        "residue_position_observed": 1.0,
                    }
                    for feature in position_features:
                        value = float(position_values[feature])
                        if value:
                            rows.append(row_index)
                            columns.append(base + gene_feature_index[feature])
                            values.append(value)

            for name, count in global_counts.items():
                if count:
                    rows.append(row_index)
                    columns.append(global_index[name])
                    values.append(float(count))
            if robust_features:
                robust_values = _robust_aggregate_values(
                    global_counts,
                    gene_count=len(genes),
                    type_gene_counts=type_gene_counts,
                    max_variants_per_gene=max_variants_per_gene,
                    single_variant_gene_count=single_variant_gene_count,
                )
                for name in robust_features:
                    value = robust_values[name]
                    if value:
                        rows.append(row_index)
                        columns.append(global_index[name])
                        values.append(value)

    matrix = sparse.csr_matrix(
        (np.asarray(values, dtype=np.float32), (rows, columns)),
        shape=(len(ids), len(names)),
        dtype=np.float32,
    )
    token_total = int(parsing_qc["mutation_tokens_total"])
    tokens_with_positions = int(parsing_qc["tokens_with_residue_positions"])
    parsing_qc["residue_position_parse_rate"] = (
        float(tokens_with_positions / token_total) if token_total else 1.0
    )
    parsing_qc["complex_token_ratio"] = (
        float(parsing_qc["complex_tokens"] / token_total) if token_total else 0.0
    )
    parsing_qc["token_shape_counts"] = dict(
        sorted(parsing_qc["token_shape_counts"].items())
    )
    return FeatureMatrix(
        matrix=matrix,
        ids=ids,
        labels=labels,
        parsing_qc=parsing_qc,
    )


def build_mutation_features(
    train_path: Path,
    test_path: Path,
    output_dir: Path,
    *,
    include_robust_aggregates: bool = False,
    selected_robust_aggregates: tuple[str, ...] | None = None,
    selected_position_features: tuple[str, ...] | None = None,
    position_missing_policy: str = "zero",
    position_token_scope: str = "include_complex",
    position_transform: str = "raw",
    position_bin_width: int = 100,
) -> dict[str, object]:
    """Build train/test CSR matrices with identical, target-independent features."""

    with train_path.open("r", encoding="utf-8", newline="") as file:
        train_header = next(csv.reader(file))
    with test_path.open("r", encoding="utf-8", newline="") as file:
        test_header = next(csv.reader(file))
    genes = train_header[2:]
    if genes != test_header[1:]:
        raise ValueError("train/test 유전자 열 이름 또는 순서가 다릅니다.")

    robust_features = _resolve_robust_features(
        include_robust_aggregates=include_robust_aggregates,
        selected_robust_aggregates=selected_robust_aggregates,
    )
    _validate_position_options(
        missing_policy=position_missing_policy,
        token_scope=position_token_scope,
        transform=position_transform,
        bin_width=position_bin_width,
    )
    position_features = _resolve_position_features(
        selected_position_features,
        missing_policy=position_missing_policy,
    )
    names = feature_names(
        genes,
        include_robust_aggregates=include_robust_aggregates,
        selected_robust_aggregates=selected_robust_aggregates,
        selected_position_features=position_features,
        position_missing_policy=position_missing_policy,
    )
    registry = _feature_registry(
        gene_count=len(genes),
        robust_features=robust_features,
        position_features=position_features,
        position_missing_policy=position_missing_policy,
        position_token_scope=position_token_scope,
        position_transform=position_transform,
        position_bin_width=position_bin_width,
    )
    feature_spec = {
        "factory_version": FEATURE_FACTORY_VERSION,
        "gene_order_sha256": sha256_lines(genes),
        "feature_names_sha256": sha256_lines(names),
        "families": registry,
    }
    feature_spec_sha256 = sha256_lines(
        [json.dumps(feature_spec, ensure_ascii=False, sort_keys=True)]
    )
    input_hashes = {
        "train": sha256_file(train_path),
        "test": sha256_file(test_path),
    }
    cache_key_sha256 = sha256_lines(
        [
            FEATURE_FACTORY_VERSION,
            input_hashes["train"],
            input_hashes["test"],
            feature_spec_sha256,
        ]
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    cached_report = _load_valid_cache(output_dir, cache_key_sha256)
    if cached_report is not None:
        return {
            **cached_report,
            "cache": {
                **cached_report["cache"],
                "reused": True,
            },
        }

    train = _read_sparse_features(
        train_path,
        genes=genes,
        has_labels=True,
        include_robust_aggregates=include_robust_aggregates,
        selected_robust_aggregates=selected_robust_aggregates,
        selected_position_features=position_features,
        position_missing_policy=position_missing_policy,
        position_token_scope=position_token_scope,
        position_transform=position_transform,
        position_bin_width=position_bin_width,
    )
    test = _read_sparse_features(
        test_path,
        genes=genes,
        has_labels=False,
        include_robust_aggregates=include_robust_aggregates,
        selected_robust_aggregates=selected_robust_aggregates,
        selected_position_features=position_features,
        position_missing_policy=position_missing_policy,
        position_token_scope=position_token_scope,
        position_transform=position_transform,
        position_bin_width=position_bin_width,
    )

    train_matrix_path = output_dir / "train_features.npz"
    test_matrix_path = output_dir / "test_features.npz"
    train_ids_path = output_dir / "train_ids.csv"
    test_ids_path = output_dir / "test_ids.csv"
    labels_path = output_dir / "train_labels.csv"
    names_path = output_dir / "feature_names.json"
    spec_path = output_dir / "feature_spec.json"
    registry_path = output_dir / "feature_registry.json"
    parsing_qc_path = output_dir / "parsing_qc.json"
    report_path = output_dir / "feature_report.json"

    sparse.save_npz(train_matrix_path, train.matrix, compressed=True)
    sparse.save_npz(test_matrix_path, test.matrix, compressed=True)
    _write_single_column(train_ids_path, "ID", train.ids)
    _write_single_column(test_ids_path, "ID", test.ids)
    _write_single_column(labels_path, "SUBCLASS", train.labels or [])
    names_path.write_text(json.dumps(names, ensure_ascii=False) + "\n", encoding="utf-8")
    spec_path.write_text(
        json.dumps(feature_spec, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    registry_path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    parsing_qc = {"train": train.parsing_qc, "test": test.parsing_qc}
    parsing_qc_path.write_text(
        json.dumps(parsing_qc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report: dict[str, object] = {
        "inputs": {
            "train": {"path": str(train_path), "sha256": input_hashes["train"]},
            "test": {"path": str(test_path), "sha256": input_hashes["test"]},
        },
        "cache": {
            "factory_version": FEATURE_FACTORY_VERSION,
            "key_sha256": cache_key_sha256,
            "reused": False,
        },
        "feature_contract": {
            "target_used_for_features": False,
            "gene_count": len(genes),
            "gene_order_sha256": sha256_lines(genes),
            "mutation_types": list(MUTATION_TYPES),
            "robust_aggregate_features": list(robust_features),
            "missing_policy": "separate per-gene and per-sample missing indicators",
            "position_features": list(position_features),
            "position_missing_policy": position_missing_policy,
            "position_token_scope": position_token_scope,
            "position_transform": position_transform,
            "position_bin_width": (
                position_bin_width if position_transform == "coarse_bin" else None
            ),
            "position_semantics": (
                "protein residue indices explicitly written in source tokens; "
                "no transcript, codon nucleotide, genomic coordinate, or protein-length inference"
            ),
            "feature_factory_version": FEATURE_FACTORY_VERSION,
            "feature_spec_sha256": feature_spec_sha256,
        },
        "feature_registry": registry,
        "parsing_qc": parsing_qc,
        "train": {
            "shape": list(train.matrix.shape),
            "nonzero": int(train.matrix.nnz),
        },
        "test": {
            "shape": list(test.matrix.shape),
            "nonzero": int(test.matrix.nnz),
        },
        "feature_count": len(names),
        "feature_names_sha256": sha256_lines(names),
        "outputs": {},
    }
    output_paths = (
        train_matrix_path,
        test_matrix_path,
        train_ids_path,
        test_ids_path,
        labels_path,
        names_path,
        spec_path,
        registry_path,
        parsing_qc_path,
    )
    report["outputs"] = {
        path.name: {"path": str(path), "sha256": sha256_file(path)} for path in output_paths
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _feature_registry(
    *,
    gene_count: int,
    robust_features: tuple[str, ...],
    position_features: tuple[str, ...],
    position_missing_policy: str,
    position_token_scope: str,
    position_transform: str,
    position_bin_width: int,
) -> dict[str, dict[str, Any]]:
    """Describe enabled families and their leakage/knowledge contract."""

    return {
        "mutation_type": {
            "definition_version": "1.0.0",
            "enabled": True,
            "output_dimension": len(GLOBAL_FEATURES) + gene_count * len(GENE_FEATURES),
            "fit_scope": "stateless; train and test parsed independently",
            "external_knowledge": None,
        },
        "robust_aggregate": {
            "definition_version": "1.0.0",
            "enabled": bool(robust_features),
            "features": list(robust_features),
            "output_dimension": len(robust_features),
            "fit_scope": "stateless per-sample aggregation",
            "external_knowledge": None,
        },
        "residue_position": {
            "definition_version": "1.1.0",
            "enabled": bool(position_features),
            "features": list(position_features),
            "output_dimension": gene_count * len(position_features),
            "missing_policy": position_missing_policy,
            "token_scope": position_token_scope,
            "transform": position_transform,
            "bin_width": position_bin_width if position_transform == "coarse_bin" else None,
            "fit_scope": "stateless lexical parse; no target or test-distribution fit",
            "external_knowledge": None,
        },
    }


def _load_valid_cache(
    output_dir: Path,
    cache_key_sha256: str,
) -> dict[str, Any] | None:
    """Return a complete cache only when its key and every output hash match."""

    report_path = output_dir / "feature_report.json"
    if not report_path.is_file():
        return None
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report["cache"]["key_sha256"] != cache_key_sha256:
            return None
        for metadata in report["outputs"].values():
            path = Path(metadata["path"])
            if not path.is_file() or sha256_file(path) != metadata["sha256"]:
                return None
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return report


def _robust_aggregate_values(
    counts: dict[str, int],
    *,
    gene_count: int,
    type_gene_counts: dict[str, int] | None = None,
    max_variants_per_gene: int = 0,
    single_variant_gene_count: int = 0,
) -> dict[str, float]:
    """Create finite log/count-ratio features without using the target."""

    mutated_gene_count = counts["sample__mutated_gene_count"]
    total_variant_count = counts["sample__total_variant_count"]
    multi_variant_gene_count = counts["sample__multi_variant_gene_count"]
    type_gene_counts = type_gene_counts or {
        mutation_type: 0 for mutation_type in MUTATION_TYPES
    }
    truncating_count = (
        counts["sample__nonsense_count"] + counts["sample__frameshift_count"]
    )
    damaging_count = (
        counts["sample__missense_count"]
        + counts["sample__nonsense_count"]
        + counts["sample__frameshift_count"]
    )
    type_probabilities = [
        counts[f"sample__{mutation_type}_count"] / total_variant_count
        for mutation_type in MUTATION_TYPES
        if counts[f"sample__{mutation_type}_count"] and total_variant_count
    ]
    values = {
        "sample__mutated_gene_count_log1p": float(np.log1p(mutated_gene_count)),
        "sample__total_variant_count_log1p": float(np.log1p(total_variant_count)),
        "sample__multi_variant_gene_count_log1p": float(
            np.log1p(multi_variant_gene_count)
        ),
        "sample__multi_variant_gene_ratio": (
            float(multi_variant_gene_count / mutated_gene_count)
            if mutated_gene_count
            else 0.0
        ),
        "sample__missing_gene_ratio": (
            float(counts["sample__missing_gene_count"] / gene_count)
            if gene_count
            else 0.0
        ),
        "sample__truncating_count": float(truncating_count),
        "sample__truncating_count_log1p": float(np.log1p(truncating_count)),
        "sample__damaging_count": float(damaging_count),
        "sample__damaging_count_log1p": float(np.log1p(damaging_count)),
        "sample__mutation_type_diversity": float(len(type_probabilities)),
        "sample__mutation_type_entropy": float(
            -sum(probability * np.log(probability) for probability in type_probabilities)
        ),
        "sample__variants_per_mutated_gene_mean": (
            float(total_variant_count / mutated_gene_count)
            if mutated_gene_count
            else 0.0
        ),
        "sample__max_variants_per_gene": float(max_variants_per_gene),
        "sample__single_variant_gene_count": float(single_variant_gene_count),
        "sample__single_variant_gene_count_log1p": float(
            np.log1p(single_variant_gene_count)
        ),
    }
    for mutation_type in MUTATION_TYPES:
        count = counts[f"sample__{mutation_type}_count"]
        values[f"sample__{mutation_type}_ratio"] = (
            float(count / total_variant_count) if total_variant_count else 0.0
        )
        values[f"sample__{mutation_type}_count_log1p"] = float(np.log1p(count))
        affected_gene_count = type_gene_counts[mutation_type]
        values[f"sample__{mutation_type}_gene_count"] = float(
            affected_gene_count
        )
        values[f"sample__{mutation_type}_gene_count_log1p"] = float(
            np.log1p(affected_gene_count)
        )
    return values


def _resolve_robust_features(
    *,
    include_robust_aggregates: bool,
    selected_robust_aggregates: tuple[str, ...] | None,
) -> tuple[str, ...]:
    if selected_robust_aggregates is None:
        return ROBUST_GLOBAL_FEATURES if include_robust_aggregates else ()
    supported_features = {
        *ROBUST_GLOBAL_FEATURES,
        *SAMPLE_DISTRIBUTION_FEATURES,
    }
    invalid = sorted(set(selected_robust_aggregates) - supported_features)
    if invalid:
        raise ValueError(f"지원하지 않는 robust aggregate 피처입니다: {invalid}")
    if len(set(selected_robust_aggregates)) != len(selected_robust_aggregates):
        raise ValueError("robust aggregate 피처가 중복됐습니다.")
    return selected_robust_aggregates


def _resolve_position_features(
    selected_position_features: tuple[str, ...] | None,
    *,
    missing_policy: str = "zero",
) -> tuple[str, ...]:
    if selected_position_features is None:
        return ()
    invalid = sorted(
        set(selected_position_features) - set(RESIDUE_POSITION_FEATURES)
    )
    if invalid:
        raise ValueError(f"지원하지 않는 residue position 피처입니다: {invalid}")
    if len(set(selected_position_features)) != len(selected_position_features):
        raise ValueError("residue position 피처가 중복됐습니다.")
    resolved = selected_position_features
    if missing_policy == "indicator" and resolved and "residue_position_observed" not in resolved:
        resolved = (*resolved, "residue_position_observed")
    return resolved


def resolve_position_features_from_config(config: dict[str, Any]) -> tuple[str, ...]:
    """Resolve public aggregate names from an experiment config."""

    families = config.get("features", {})
    mutation_type = families.get("mutation_type", {"enabled": True})
    if not mutation_type.get("enabled", True):
        raise ValueError("이 Feature Factory에서는 mutation_type core를 끌 수 없습니다.")
    residue_position = families.get("residue_position", {"enabled": False})
    if not residue_position.get("enabled", False):
        return ()
    aggregate_mapping = {
        "min": "min_residue_position",
        "max": "max_residue_position",
        "span": "residue_position_span",
    }
    aggregates = residue_position.get("aggregates", [])
    invalid = sorted(set(aggregates) - set(aggregate_mapping))
    if invalid:
        raise ValueError(f"지원하지 않는 residue position aggregate입니다: {invalid}")
    resolved = tuple(aggregate_mapping[name] for name in aggregates)
    if not resolved:
        raise ValueError("residue_position을 활성화하면 aggregates가 필요합니다.")
    if len(set(resolved)) != len(resolved):
        raise ValueError("residue position aggregate가 중복됐습니다.")
    return resolved


def resolve_position_options_from_config(config: dict[str, Any]) -> dict[str, Any]:
    """Resolve position ablation options while preserving EXP-047 defaults."""

    residue_position = config.get("features", {}).get(
        "residue_position", {"enabled": False}
    )
    if not residue_position.get("enabled", False):
        return {
            "position_missing_policy": "zero",
            "position_token_scope": "include_complex",
            "position_transform": "raw",
            "position_bin_width": 100,
        }
    complex_tokens = residue_position.get("complex_tokens", "include")
    token_scope_mapping = {
        "include": "include_complex",
        "exclude": "exclude_complex",
    }
    if complex_tokens not in token_scope_mapping:
        raise ValueError("complex_tokens는 include 또는 exclude여야 합니다.")
    options = {
        "position_missing_policy": residue_position.get("missing_policy", "zero"),
        "position_token_scope": token_scope_mapping[complex_tokens],
        "position_transform": residue_position.get("transform", "raw"),
        "position_bin_width": residue_position.get("bin_width", 100),
    }
    _validate_position_options(
        missing_policy=options["position_missing_policy"],
        token_scope=options["position_token_scope"],
        transform=options["position_transform"],
        bin_width=options["position_bin_width"],
    )
    return options


def _validate_position_options(
    *,
    missing_policy: str,
    token_scope: str,
    transform: str,
    bin_width: int,
) -> None:
    if missing_policy not in POSITION_MISSING_POLICIES:
        raise ValueError(f"지원하지 않는 position missing policy입니다: {missing_policy}")
    if token_scope not in POSITION_TOKEN_SCOPES:
        raise ValueError(f"지원하지 않는 position token scope입니다: {token_scope}")
    if transform not in POSITION_TRANSFORMS:
        raise ValueError(f"지원하지 않는 position transform입니다: {transform}")
    if not isinstance(bin_width, int) or bin_width < 1:
        raise ValueError("position bin width는 1 이상의 정수여야 합니다.")


def _eligible_residue_positions(
    parsed_cell: ParsedMutationCell,
    *,
    token_scope: str,
) -> tuple[int, ...]:
    return tuple(
        position
        for token in parsed_cell.tokens
        if token_scope == "include_complex" or not token.is_complex
        for position in token.residue_positions
    )


def _transform_residue_positions(
    positions: tuple[int, ...],
    *,
    transform: str,
    bin_width: int,
) -> tuple[float, ...]:
    if transform == "raw":
        return tuple(float(position) for position in positions)
    if transform == "coarse_bin":
        return tuple(float((position - 1) // bin_width + 1) for position in positions)
    raise ValueError(f"지원하지 않는 position transform입니다: {transform}")


def _write_single_column(path: Path, name: str, values: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow([name])
        writer.writerows((value,) for value in values)
