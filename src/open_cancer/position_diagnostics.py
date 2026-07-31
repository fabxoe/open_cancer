"""Diagnostics for residue-position semantics in sparse Feature Factory artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy import sparse
from scipy.stats import ks_2samp

from open_cancer.hashing import sha256_file


DIAGNOSTIC_VERSION = "1.0.0"


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _feature_indices(
    feature_names: list[str],
    suffix: str,
) -> tuple[list[str], list[int]]:
    marker = f"__{suffix}"
    pairs = [
        (name[: -len(marker)], index)
        for index, name in enumerate(feature_names)
        if name.endswith(marker)
    ]
    if not pairs:
        raise ValueError(f"피처를 찾을 수 없습니다: *{marker}")
    genes, indices = zip(*pairs, strict=True)
    return list(genes), list(indices)


def _binary_support(matrix: sparse.spmatrix) -> sparse.csr_matrix:
    support = matrix.tocsr(copy=True)
    if support.nnz:
        support.data = np.ones(support.nnz, dtype=np.int8)
    return support.astype(np.int8)


def _positive_support(matrix: sparse.spmatrix) -> sparse.csr_matrix:
    support = matrix.tocsr(copy=True)
    if support.nnz:
        support.data = (support.data > 0).astype(np.int8)
        support.eliminate_zeros()
    return support.astype(np.int8)


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    return float(numerator / denominator) if denominator else None


def _split_diagnostics(
    matrix: sparse.csr_matrix,
    *,
    mutation_indices: list[int],
    observed_indices: list[int],
    position_indices: list[int],
) -> tuple[dict[str, Any], np.ndarray]:
    mutated = _binary_support(matrix[:, mutation_indices])
    observed = _binary_support(matrix[:, observed_indices])
    position = matrix[:, position_indices].tocsr()
    positive = _positive_support(position)

    mutated_count = int(mutated.nnz)
    observed_count = int(observed.nnz)
    positive_count = int(positive.nnz)
    mutation_observed_overlap = int(mutated.multiply(observed).nnz)
    observed_positive_overlap = int(observed.multiply(positive).nnz)

    mutated_without_observed = mutated_count - mutation_observed_overlap
    observed_without_mutated = observed_count - mutation_observed_overlap
    observed_without_positive = observed_count - observed_positive_overlap
    positive_without_observed = positive_count - observed_positive_overlap
    indicator_presence_mismatches = mutated_without_observed + observed_without_mutated

    negative_count = int(np.count_nonzero(position.data < 0))
    values = position.data[position.data > 0].astype(np.float64, copy=False)
    if values.size:
        position_summary: dict[str, Any] = {
            "count": int(values.size),
            "min": float(values.min()),
            "max": float(values.max()),
            "mean": float(values.mean()),
            "quantiles": {
                "q10": float(np.quantile(values, 0.10)),
                "q50": float(np.quantile(values, 0.50)),
                "q90": float(np.quantile(values, 0.90)),
                "q99": float(np.quantile(values, 0.99)),
            },
        }
    else:
        position_summary = {
            "count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "quantiles": {"q10": None, "q50": None, "q90": None, "q99": None},
        }

    return (
        {
            "rows": int(matrix.shape[0]),
            "gene_count": len(mutation_indices),
            "gene_cells": int(matrix.shape[0] * len(mutation_indices)),
            "mutated_gene_cells": mutated_count,
            "position_observed_gene_cells": observed_count,
            "positive_position_gene_cells": positive_count,
            "negative_position_gene_cells": negative_count,
            "indicator_presence_mismatches": indicator_presence_mismatches,
            "mutated_without_position_observed": mutated_without_observed,
            "position_observed_without_mutation": observed_without_mutated,
            "position_observed_but_zero": observed_without_positive,
            "positive_position_without_observed": positive_without_observed,
            "indicator_equals_mutation_presence": indicator_presence_mismatches == 0,
            "p_position_observed_given_mutated": _safe_ratio(
                observed_count - observed_without_mutated,
                mutated_count,
            ),
            "p_zero_given_position_observed": _safe_ratio(
                observed_without_positive,
                observed_count,
            ),
            "p_positive_given_not_observed": _safe_ratio(
                positive_without_observed,
                int(matrix.shape[0] * len(mutation_indices)) - observed_count,
            ),
            "positive_position_distribution": position_summary,
        },
        values,
    )


def _parsing_summary(document: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for split in ("train", "test"):
        values = document.get(split, {})
        token_total = int(values.get("mutation_tokens_total", 0))
        result[split] = {
            "non_wt_gene_cells": int(values.get("non_wt_gene_cells", 0)),
            "mutation_tokens_total": token_total,
            "tokens_with_residue_positions": int(
                values.get("tokens_with_residue_positions", 0)
            ),
            "tokens_without_residue_positions": int(
                values.get("tokens_without_residue_positions", 0)
            ),
            "residue_position_parse_rate": float(
                values.get("residue_position_parse_rate", 0.0)
            ),
            "complex_tokens": int(values.get("complex_tokens", 0)),
            "complex_token_ratio": float(values.get("complex_token_ratio", 0.0)),
            "multi_position_tokens": int(values.get("multi_position_tokens", 0)),
            "multi_position_token_ratio": _safe_ratio(
                int(values.get("multi_position_tokens", 0)), token_total
            ),
        }
    return result


def diagnose_position_artifacts(
    feature_dir: str | Path,
    *,
    position_feature: str = "max_residue_position",
) -> dict[str, Any]:
    """Inspect existing train/test sparse artifacts without reading target labels."""

    feature_dir = Path(feature_dir)
    required_paths = {
        "feature_names": feature_dir / "feature_names.json",
        "train_matrix": feature_dir / "train_features.npz",
        "test_matrix": feature_dir / "test_features.npz",
        "parsing_qc": feature_dir / "parsing_qc.json",
    }
    missing = [str(path) for path in required_paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"필수 Feature Factory 산출물이 없습니다: {missing}")

    feature_names = json.loads(required_paths["feature_names"].read_text(encoding="utf-8"))
    if not isinstance(feature_names, list) or not all(
        isinstance(name, str) for name in feature_names
    ):
        raise ValueError("feature_names.json은 문자열 배열이어야 합니다.")

    mutation_genes, mutation_indices = _feature_indices(feature_names, "mutated")
    observed_genes, observed_indices = _feature_indices(
        feature_names, "residue_position_observed"
    )
    position_genes, position_indices = _feature_indices(feature_names, position_feature)
    if mutation_genes != observed_genes or mutation_genes != position_genes:
        raise ValueError("mutation, observed, position 피처의 유전자 또는 순서가 다릅니다.")

    matrices = {
        "train": sparse.load_npz(required_paths["train_matrix"]).tocsr(),
        "test": sparse.load_npz(required_paths["test_matrix"]).tocsr(),
    }
    split_results: dict[str, Any] = {}
    position_values: dict[str, np.ndarray] = {}
    for split, matrix in matrices.items():
        if matrix.shape[1] != len(feature_names):
            raise ValueError(
                f"{split} matrix 열 수가 feature_names 수와 다릅니다: "
                f"{matrix.shape[1]} != {len(feature_names)}"
            )
        split_results[split], position_values[split] = _split_diagnostics(
            matrix,
            mutation_indices=mutation_indices,
            observed_indices=observed_indices,
            position_indices=position_indices,
        )

    parsing_document = json.loads(
        required_paths["parsing_qc"].read_text(encoding="utf-8")
    )
    parsing = _parsing_summary(parsing_document)
    train_values = position_values["train"]
    test_values = position_values["test"]
    ks_statistic = (
        float(ks_2samp(train_values, test_values).statistic)
        if train_values.size and test_values.size
        else None
    )
    exact_duplicate = all(
        result["indicator_equals_mutation_presence"]
        for result in split_results.values()
    )

    return {
        "diagnostic_version": DIAGNOSTIC_VERSION,
        "feature_dir": _display_path(feature_dir),
        "position_feature": position_feature,
        "target_or_labels_used": False,
        "inputs": {
            name: {"path": _display_path(path), "sha256": sha256_file(path)}
            for name, path in required_paths.items()
        },
        "feature_contract": {
            "feature_count": len(feature_names),
            "gene_count": len(mutation_genes),
            "indicator_exactly_duplicates_mutation_presence": exact_duplicate,
            "indicator_interpretation": (
                "duplicate_feature_weighting_not_missingness_resolution"
                if exact_duplicate
                else "position_parseability_indicator"
            ),
        },
        "splits": split_results,
        "parsing_qc": parsing,
        "train_test_shift": {
            "complex_token_ratio_absolute_difference": abs(
                parsing["train"]["complex_token_ratio"]
                - parsing["test"]["complex_token_ratio"]
            ),
            "multi_position_token_ratio_absolute_difference": abs(
                (parsing["train"]["multi_position_token_ratio"] or 0.0)
                - (parsing["test"]["multi_position_token_ratio"] or 0.0)
            ),
            "positive_position_ks_statistic": ks_statistic,
            "interpretation_limit": (
                "QC only; test distribution must not select features, thresholds, "
                "or leaderboard candidates"
            ),
        },
    }
