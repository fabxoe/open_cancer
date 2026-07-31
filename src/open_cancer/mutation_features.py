"""Deterministic sparse features parsed directly from mutation strings."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import sparse

from open_cancer.hashing import sha256_file, sha256_lines


MUTATION_TYPES = ("missense", "synonymous", "nonsense", "frameshift", "complex")
GENE_FEATURES = ("mutated", *MUTATION_TYPES, "missing")
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

_SUBSTITUTION = re.compile(r"^([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]*)([ACDEFGHIKLMNPQRSTVWY*])$")


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


@dataclass(frozen=True)
class FeatureMatrix:
    matrix: sparse.csr_matrix
    ids: list[str]
    labels: list[str] | None


def feature_names(
    genes: list[str],
    *,
    include_robust_aggregates: bool = False,
    selected_robust_aggregates: tuple[str, ...] | None = None,
) -> list[str]:
    """Return the stable feature order shared by train and test."""

    robust_features = _resolve_robust_features(
        include_robust_aggregates=include_robust_aggregates,
        selected_robust_aggregates=selected_robust_aggregates,
    )
    return [
        *GLOBAL_FEATURES,
        *robust_features,
        *(f"{gene}__{feature}" for gene in genes for feature in GENE_FEATURES),
    ]


def _read_sparse_features(
    path: Path,
    *,
    genes: list[str],
    has_labels: bool,
    include_robust_aggregates: bool,
    selected_robust_aggregates: tuple[str, ...] | None,
) -> FeatureMatrix:
    robust_features = _resolve_robust_features(
        include_robust_aggregates=include_robust_aggregates,
        selected_robust_aggregates=selected_robust_aggregates,
    )
    names = feature_names(
        genes,
        include_robust_aggregates=include_robust_aggregates,
        selected_robust_aggregates=selected_robust_aggregates,
    )
    active_global_features = (
        *GLOBAL_FEATURES,
        *robust_features,
    )
    global_index = {name: index for index, name in enumerate(active_global_features)}
    gene_offset = len(active_global_features)
    gene_stride = len(GENE_FEATURES)
    gene_feature_index = {name: index for index, name in enumerate(GENE_FEATURES)}
    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    ids: list[str] = []
    labels: list[str] | None = [] if has_labels else None

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
            for gene_index, cell in enumerate(row[feature_start:]):
                base = gene_offset + gene_index * gene_stride
                if cell == "":
                    global_counts["sample__missing_gene_count"] += 1
                    rows.append(row_index)
                    columns.append(base + gene_feature_index["missing"])
                    values.append(1.0)
                    continue

                tokens = [token for token in cell.split() if token != "WT"]
                if not tokens:
                    continue

                global_counts["sample__mutated_gene_count"] += 1
                global_counts["sample__total_variant_count"] += len(tokens)
                if len(tokens) > 1:
                    global_counts["sample__multi_variant_gene_count"] += 1
                rows.append(row_index)
                columns.append(base + gene_feature_index["mutated"])
                values.append(1.0)

                observed_types = set()
                for token in tokens:
                    mutation_type = classify_mutation_token(token)
                    observed_types.add(mutation_type)
                    global_counts[f"sample__{mutation_type}_count"] += 1
                for mutation_type in sorted(observed_types):
                    rows.append(row_index)
                    columns.append(base + gene_feature_index[mutation_type])
                    values.append(1.0)

            for name, count in global_counts.items():
                if count:
                    rows.append(row_index)
                    columns.append(global_index[name])
                    values.append(float(count))
            if robust_features:
                robust_values = _robust_aggregate_values(
                    global_counts,
                    gene_count=len(genes),
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
    return FeatureMatrix(matrix=matrix, ids=ids, labels=labels)


def build_mutation_features(
    train_path: Path,
    test_path: Path,
    output_dir: Path,
    *,
    include_robust_aggregates: bool = False,
    selected_robust_aggregates: tuple[str, ...] | None = None,
) -> dict[str, object]:
    """Build train/test CSR matrices with identical, target-independent features."""

    with train_path.open("r", encoding="utf-8", newline="") as file:
        train_header = next(csv.reader(file))
    with test_path.open("r", encoding="utf-8", newline="") as file:
        test_header = next(csv.reader(file))
    genes = train_header[2:]
    if genes != test_header[1:]:
        raise ValueError("train/test 유전자 열 이름 또는 순서가 다릅니다.")

    train = _read_sparse_features(
        train_path,
        genes=genes,
        has_labels=True,
        include_robust_aggregates=include_robust_aggregates,
        selected_robust_aggregates=selected_robust_aggregates,
    )
    test = _read_sparse_features(
        test_path,
        genes=genes,
        has_labels=False,
        include_robust_aggregates=include_robust_aggregates,
        selected_robust_aggregates=selected_robust_aggregates,
    )
    names = feature_names(
        genes,
        include_robust_aggregates=include_robust_aggregates,
        selected_robust_aggregates=selected_robust_aggregates,
    )
    robust_features = _resolve_robust_features(
        include_robust_aggregates=include_robust_aggregates,
        selected_robust_aggregates=selected_robust_aggregates,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    train_matrix_path = output_dir / "train_features.npz"
    test_matrix_path = output_dir / "test_features.npz"
    train_ids_path = output_dir / "train_ids.csv"
    test_ids_path = output_dir / "test_ids.csv"
    labels_path = output_dir / "train_labels.csv"
    names_path = output_dir / "feature_names.json"
    report_path = output_dir / "feature_report.json"

    sparse.save_npz(train_matrix_path, train.matrix, compressed=True)
    sparse.save_npz(test_matrix_path, test.matrix, compressed=True)
    _write_single_column(train_ids_path, "ID", train.ids)
    _write_single_column(test_ids_path, "ID", test.ids)
    _write_single_column(labels_path, "SUBCLASS", train.labels or [])
    names_path.write_text(json.dumps(names, ensure_ascii=False) + "\n", encoding="utf-8")

    report: dict[str, object] = {
        "inputs": {
            "train": {"path": str(train_path), "sha256": sha256_file(train_path)},
            "test": {"path": str(test_path), "sha256": sha256_file(test_path)},
        },
        "feature_contract": {
            "target_used_for_features": False,
            "gene_count": len(genes),
            "gene_order_sha256": sha256_lines(genes),
            "mutation_types": list(MUTATION_TYPES),
            "robust_aggregate_features": list(robust_features),
            "missing_policy": "separate per-gene and per-sample missing indicators",
            "position_features": "excluded because a reliable source transcript/protein length is unavailable",
        },
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
    )
    report["outputs"] = {
        path.name: {"path": str(path), "sha256": sha256_file(path)} for path in output_paths
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def _robust_aggregate_values(
    counts: dict[str, int],
    *,
    gene_count: int,
) -> dict[str, float]:
    """Create finite log/count-ratio features without using the target."""

    mutated_gene_count = counts["sample__mutated_gene_count"]
    total_variant_count = counts["sample__total_variant_count"]
    multi_variant_gene_count = counts["sample__multi_variant_gene_count"]
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
    }
    for mutation_type in MUTATION_TYPES:
        count = counts[f"sample__{mutation_type}_count"]
        values[f"sample__{mutation_type}_ratio"] = (
            float(count / total_variant_count) if total_variant_count else 0.0
        )
    return values


def _resolve_robust_features(
    *,
    include_robust_aggregates: bool,
    selected_robust_aggregates: tuple[str, ...] | None,
) -> tuple[str, ...]:
    if selected_robust_aggregates is None:
        return ROBUST_GLOBAL_FEATURES if include_robust_aggregates else ()
    invalid = sorted(set(selected_robust_aggregates) - set(ROBUST_GLOBAL_FEATURES))
    if invalid:
        raise ValueError(f"지원하지 않는 robust aggregate 피처입니다: {invalid}")
    if len(set(selected_robust_aggregates)) != len(selected_robust_aggregates):
        raise ValueError("robust aggregate 피처가 중복됐습니다.")
    return selected_robust_aggregates


def _write_single_column(path: Path, name: str, values: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow([name])
        writer.writerows((value,) for value in values)
