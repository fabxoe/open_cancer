"""EXP-156 target-independent compression of per-gene mutation effects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.constants import (
    CLASS_LABELS,
    EXPECTED_GENE_COLUMNS,
    EXPECTED_TEST_ROWS,
    EXPECTED_TRAIN_ROWS,
)
from open_cancer.frozen_feature_specs import materialize_frozen_feature_spec
from open_cancer.hashing import sha256_file, sha256_lines
from open_cancer.mutation_features import MUTATION_TYPES, parse_mutation_cell


DEFINITION_VERSION = "1.0.0"
COMPRESSED_FEATURES = (
    "compressed_effect_severity_max",
    "compressed_variant_count_1_or_2plus",
    "compressed_effect_diversity",
    "compressed_complex_or_unparsed",
)
KNOWN_SEVERITY = {
    "synonymous": 1.0,
    "missense": 2.0,
    "nonsense": 3.0,
    "frameshift": 3.0,
    # `complex` can contain non-standard strings. Keep it as a separate
    # indicator rather than assigning unsupported biological severity.
    "complex": 0.0,
}


class CompactEffectFeatureError(ValueError):
    """Raised when EXP-156 feature contracts are violated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CompactEffectFeatureError(message)


def compact_feature_names(gene_columns: Sequence[str]) -> tuple[str, ...]:
    """Return deterministic gene-major names for the compressed representation."""
    return tuple(
        f"{gene}__{feature}"
        for gene in gene_columns
        for feature in COMPRESSED_FEATURES
    )


def build_compact_effect_matrix(
    frame: pd.DataFrame,
    gene_columns: Sequence[str],
) -> tuple[sparse.csr_matrix, tuple[str, ...], dict[str, Any]]:
    """Transform supplied protein tokens without target or test-frequency fitting."""
    genes = tuple(gene_columns)
    _require(bool(genes), "유전자 열이 없습니다.")
    _require(
        all(gene in frame.columns for gene in genes),
        "frame에 없는 유전자 열이 있습니다.",
    )

    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    mutated_cells = 0
    multi_token_cells = 0
    complex_cells = 0
    feature_stride = len(COMPRESSED_FEATURES)

    for row_index, cells in enumerate(
        frame.loc[:, list(genes)].itertuples(index=False, name=None)
    ):
        for gene_index, cell in enumerate(cells):
            parsed = parse_mutation_cell(str(cell))
            if not parsed.tokens:
                continue
            mutated_cells += 1
            if parsed.token_count > 1:
                multi_token_cells += 1
            base = gene_index * feature_stride

            severity = max(
                (KNOWN_SEVERITY[token.mutation_type] for token in parsed.tokens),
                default=0.0,
            )
            if severity:
                rows.append(row_index)
                columns.append(base)
                values.append(severity)

            # 1 means one token; 2 means two or more.
            rows.append(row_index)
            columns.append(base + 1)
            values.append(float(min(parsed.token_count, 2)))

            rows.append(row_index)
            columns.append(base + 2)
            values.append(float(len(parsed.mutation_types)))

            if "complex" in parsed.mutation_types:
                complex_cells += 1
                rows.append(row_index)
                columns.append(base + 3)
                values.append(1.0)

    names = compact_feature_names(genes)
    matrix = sparse.csr_matrix(
        (np.asarray(values, dtype=np.float32), (rows, columns)),
        shape=(len(frame), len(names)),
        dtype=np.float32,
    )
    _require(
        matrix.shape == (len(frame), len(genes) * feature_stride),
        "압축 행렬 shape 오류",
    )
    _require(
        np.isfinite(matrix.data).all(),
        "압축 행렬에 NaN 또는 무한대가 있습니다.",
    )
    return matrix, names, {
        "definition_version": DEFINITION_VERSION,
        "fit_scope": "stateless",
        "rows": len(frame),
        "gene_count": len(genes),
        "output_dimension": len(names),
        "matrix_nnz": int(matrix.nnz),
        "mutated_gene_cells": mutated_cells,
        "multi_token_gene_cells": multi_token_cells,
        "complex_or_unparsed_gene_cells": complex_cells,
        "feature_names_sha256": sha256_lines(names),
    }


def replace_per_gene_mutation_types(
    base_train: sparse.csr_matrix,
    base_test: sparse.csr_matrix,
    base_feature_names: Sequence[str],
    compact_train: sparse.csr_matrix,
    compact_test: sparse.csr_matrix,
    compact_names: Sequence[str],
    *,
    gene_count: int,
) -> tuple[sparse.csr_matrix, sparse.csr_matrix, tuple[str, ...], tuple[str, ...]]:
    """Replace v1's five per-gene type indicators, preserving other columns."""
    names = tuple(base_feature_names)
    _require(
        base_train.shape[1] == base_test.shape[1] == len(names),
        "base 열 계약 불일치",
    )
    _require(
        compact_train.shape[1] == compact_test.shape[1] == len(compact_names),
        "압축 열 계약 불일치",
    )
    suffixes = tuple(f"__{mutation_type}" for mutation_type in MUTATION_TYPES)
    removed_indices = tuple(
        index for index, name in enumerate(names) if name.endswith(suffixes)
    )
    expected_removed = gene_count * len(MUTATION_TYPES)
    _require(
        len(removed_indices) == expected_removed,
        (
            "제거할 유전자×변이유형 열 수가 다릅니다: "
            f"{len(removed_indices)} != {expected_removed}"
        ),
    )
    removed_set = set(removed_indices)
    kept_indices = [index for index in range(len(names)) if index not in removed_set]
    removed_names = tuple(names[index] for index in removed_indices)
    final_names = (*(names[index] for index in kept_indices), *tuple(compact_names))
    _require(len(final_names) == len(set(final_names)), "최종 feature 이름이 중복됩니다.")
    final_train = sparse.hstack(
        [base_train[:, kept_indices], compact_train],
        format="csr",
        dtype=np.float32,
    )
    final_test = sparse.hstack(
        [base_test[:, kept_indices], compact_test],
        format="csr",
        dtype=np.float32,
    )
    _require(
        final_train.shape[1] == final_test.shape[1] == len(final_names),
        "최종 열 계약 불일치",
    )
    return final_train, final_test, tuple(final_names), removed_names


def materialize_compact_effect_ablation(
    *,
    root: Path,
    name: str,
    output_dir: Path,
    train_path: Path,
    test_path: Path,
) -> dict[str, Any]:
    """Materialize v1 and replace only per-gene effect representation."""
    _require(name == "v1", "EXP-156의 parent Feature Spec은 v1이어야 합니다.")
    base_dir = output_dir / "parent_feature_spec_v1"
    base_manifest = materialize_frozen_feature_spec(
        root=root,
        name="v1",
        output_dir=base_dir,
        train_path=train_path,
        test_path=test_path,
    )
    base_train = sparse.load_npz(base_dir / "train_features.npz").tocsr()
    base_test = sparse.load_npz(base_dir / "test_features.npz").tocsr()
    base_names = tuple(
        json.loads((base_dir / "feature_names.json").read_text(encoding="utf-8"))
    )

    train = pd.read_csv(train_path, dtype=str, keep_default_na=False)
    test = pd.read_csv(test_path, dtype=str, keep_default_na=False)
    _require(len(train) == EXPECTED_TRAIN_ROWS, "train 행 수가 데이터 계약과 다릅니다.")
    _require(len(test) == EXPECTED_TEST_ROWS, "test 행 수가 데이터 계약과 다릅니다.")
    genes = tuple(
        column for column in train.columns if column not in {"ID", "SUBCLASS"}
    )
    _require(len(genes) == EXPECTED_GENE_COLUMNS, "유전자 열 수가 데이터 계약과 다릅니다.")
    _require(
        tuple(test.columns[1:]) == genes,
        "train/test 유전자 열 이름 또는 순서가 다릅니다.",
    )

    compact_train, compact_names, train_qc = build_compact_effect_matrix(
        train, genes
    )
    compact_test, test_names, test_qc = build_compact_effect_matrix(test, genes)
    _require(compact_names == test_names, "train/test 압축 feature 이름이 다릅니다.")
    final_train, final_test, final_names, removed_names = (
        replace_per_gene_mutation_types(
            base_train,
            base_test,
            base_names,
            compact_train,
            compact_test,
            compact_names,
            gene_count=len(genes),
        )
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    train_output = output_dir / "train_features.npz"
    test_output = output_dir / "test_features.npz"
    names_output = output_dir / "feature_names.json"
    manifest_output = output_dir / "feature_spec_manifest.json"
    sparse.save_npz(train_output, final_train, compressed=True)
    sparse.save_npz(test_output, final_test, compressed=True)
    names_output.write_text(
        json.dumps(final_names, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    identity_lines = [
        base_manifest["base_feature_spec_sha256"],
        DEFINITION_VERSION,
        sha256_lines(removed_names),
        sha256_lines(final_names),
    ]
    manifest = {
        "name": "exp156-compact-effect-ablation",
        "parent_name": "v1",
        "parent_experiment": "EXP-094",
        "base_feature_spec_sha256": base_manifest["base_feature_spec_sha256"],
        "feature_spec_sha256": sha256_lines(identity_lines),
        "definition_version": DEFINITION_VERSION,
        "fit_scope": "stateless",
        "class_order": list(CLASS_LABELS),
        "replacement": {
            "removed_family": "per_gene_mutation_type_indicators",
            "removed_types": list(MUTATION_TYPES),
            "removed_dimension": len(removed_names),
            "removed_feature_names_sha256": sha256_lines(removed_names),
            "added_family": "compact_gene_effect",
            "added_features_per_gene": list(COMPRESSED_FEATURES),
            "added_dimension": len(compact_names),
        },
        "train_input_sha256": sha256_file(train_path),
        "test_input_sha256": sha256_file(test_path),
        "train_shape": list(final_train.shape),
        "test_shape": list(final_test.shape),
        "feature_names_sha256": sha256_lines(final_names),
        "train_qc": train_qc,
        "test_qc": test_qc,
        "outputs": {
            "train_features": {
                "path": str(train_output),
                "sha256": sha256_file(train_output),
            },
            "test_features": {
                "path": str(test_output),
                "sha256": sha256_file(test_output),
            },
            "feature_names": {
                "path": str(names_output),
                "sha256": sha256_file(names_output),
            },
        },
    }
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
