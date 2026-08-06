#!/usr/bin/env python
"""Benchmark Issue #607 vectorized scan/cache and verify full-matrix identity."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.canonical_mutation_events import (
    canonical_event_cache_info,
    clear_canonical_event_caches,
    parse_canonical_gene_cell,
)
from open_cancer.parser_v4_semantic_counts import (
    FEATURE_NAMES,
    ParserV4SemanticCountFamily,
    _increment_event,
)
from open_cancer.patient_semantic_vector import PatientSemanticVectorFamily
from open_cancer.sparse_gene_cells import extract_non_wt_gene_cells, is_non_wt_cell


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, default=ROOT / "data/raw/train.csv")
    parser.add_argument("--test", type=Path, default=ROOT / "data/raw/test.csv")
    parser.add_argument("--legacy-patient-cache-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def timed(function):
    started = time.perf_counter()
    value = function()
    return value, float(time.perf_counter() - started)


def legacy_scan(frame: pd.DataFrame, genes: tuple[str, ...]):
    rows: list[int] = []
    columns: list[int] = []
    values: list[str] = []
    for gene_index, gene in enumerate(genes):
        gene_values = frame[gene].to_numpy(dtype=object, copy=False)
        for row_index, cell in enumerate(gene_values):
            if is_non_wt_cell(cell):
                rows.append(row_index)
                columns.append(gene_index)
                values.append(cell)
    return (
        np.asarray(rows, dtype=np.int32),
        np.asarray(columns, dtype=np.int32),
        tuple(values),
    )


def legacy_semantic_counts(frame: pd.DataFrame, genes: tuple[str, ...]):
    matrix = np.zeros((len(frame), len(FEATURE_NAMES)), dtype=np.float32)
    for gene in genes:
        values = frame[gene].to_numpy(dtype=object, copy=False)
        for row_index, cell in enumerate(values):
            if not is_non_wt_cell(cell):
                continue
            parsed = parse_canonical_gene_cell(cell)
            for event in parsed.events:
                _increment_event(matrix[row_index], event, gene_symbol=gene)
    return sparse.csr_matrix(matrix)


def sparse_equal(left: sparse.spmatrix, right: sparse.spmatrix) -> bool:
    left_csr = left.tocsr()
    right_csr = right.tocsr()
    return left_csr.shape == right_csr.shape and (left_csr != right_csr).nnz == 0


def sparse_sha256(matrix: sparse.spmatrix) -> str:
    csr = matrix.tocsr()
    digest = hashlib.sha256()
    digest.update(np.asarray(csr.shape, dtype=np.int64).tobytes())
    digest.update(csr.indptr.astype(np.int64, copy=False).tobytes())
    digest.update(csr.indices.astype(np.int64, copy=False).tobytes())
    digest.update(csr.data.astype(np.float32, copy=False).tobytes())
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    train = pd.read_csv(args.train, dtype=str, keep_default_na=False)
    test = pd.read_csv(args.test, dtype=str, keep_default_na=False)
    genes = tuple(column for column in train if column not in {"ID", "SUBCLASS"})

    legacy_cells, legacy_scan_seconds = timed(lambda: legacy_scan(train, genes))
    new_cells, vector_scan_seconds = timed(
        lambda: extract_non_wt_gene_cells(
            train, genes, feature_version="benchmark"
        )
    )
    scan_equal = (
        np.array_equal(legacy_cells[0], new_cells.row_indices)
        and np.array_equal(legacy_cells[1], new_cells.gene_indices)
        and legacy_cells[2] == new_cells.values
    )

    fitted_counts = ParserV4SemanticCountFamily(genes).fit(train.iloc[:1])
    clear_canonical_event_caches()
    legacy_counts, legacy_counts_seconds = timed(
        lambda: legacy_semantic_counts(train, genes)
    )
    clear_canonical_event_caches()
    new_counts, new_counts_cold_seconds = timed(lambda: fitted_counts.transform(train))
    warm_counts, new_counts_warm_seconds = timed(lambda: fitted_counts.transform(train))
    counts_equal = sparse_equal(legacy_counts, new_counts) and sparse_equal(
        new_counts, warm_counts
    )

    fitted_patient = PatientSemanticVectorFamily(genes).fit(train.iloc[:1])
    clear_canonical_event_caches()
    patient_train, patient_train_cold_seconds = timed(
        lambda: fitted_patient.transform(train)
    )
    patient_train_warm, patient_train_warm_seconds = timed(
        lambda: fitted_patient.transform(train)
    )
    patient_test, patient_test_warm_seconds = timed(lambda: fitted_patient.transform(test))
    patient_internal_equal = sparse_equal(patient_train, patient_train_warm)

    legacy_patient = {"available": False}
    if args.legacy_patient_cache_dir is not None:
        legacy_train = sparse.load_npz(
            args.legacy_patient_cache_dir / "train_features.npz"
        )
        legacy_test = sparse.load_npz(
            args.legacy_patient_cache_dir / "test_features.npz"
        )
        legacy_patient = {
            "available": True,
            "train_equal": sparse_equal(legacy_train, patient_train),
            "test_equal": sparse_equal(legacy_test, patient_test),
            "legacy_train_sha256": sparse_sha256(legacy_train),
            "legacy_test_sha256": sparse_sha256(legacy_test),
        }

    result = {
        "issue": 607,
        "rows": {"train": len(train), "test": len(test)},
        "genes": len(genes),
        "non_wt_cells": len(new_cells),
        "scan": {
            "legacy_seconds": legacy_scan_seconds,
            "vectorized_seconds": vector_scan_seconds,
            "speedup": legacy_scan_seconds / vector_scan_seconds,
            "coordinate_and_value_identity": scan_equal,
            "cache_key": new_cells.cache_key,
            "gene_columns_sha256": new_cells.gene_columns_sha256,
        },
        "semantic_counts": {
            "legacy_seconds": legacy_counts_seconds,
            "new_cold_seconds": new_counts_cold_seconds,
            "new_warm_seconds": new_counts_warm_seconds,
            "legacy_new_warm_identity": counts_equal,
            "matrix_sha256": sparse_sha256(new_counts),
        },
        "patient_semantic_vector": {
            "train_cold_seconds": patient_train_cold_seconds,
            "train_warm_seconds": patient_train_warm_seconds,
            "test_warm_seconds": patient_test_warm_seconds,
            "cold_warm_identity": patient_internal_equal,
            "train_sha256": sparse_sha256(patient_train),
            "test_sha256": sparse_sha256(patient_test),
            "legacy_reference": legacy_patient,
        },
        "cache_info_after_warm_runs": canonical_event_cache_info(),
    }
    required = [scan_equal, counts_equal, patient_internal_equal]
    if legacy_patient["available"]:
        required.extend([legacy_patient["train_equal"], legacy_patient["test_equal"]])
    if not all(required):
        raise RuntimeError("full-matrix identity verification failed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
