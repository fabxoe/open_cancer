#!/usr/bin/env python3
"""Validate the fixed parser-v4 native adapter against train and test CSVs."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from open_cancer.hashing import sha256_file
from open_cancer.parser_native_features import (
    NATIVE_CONSEQUENCES,
    ParserNativeSemanticFamily,
    native_semantic_contract_record,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "analysis" / "parser_v4_native_adapter_validation"


def _raw_mutated_gene_counts(frame: pd.DataFrame, genes: tuple[str, ...]) -> np.ndarray:
    counts = np.zeros(len(frame), dtype=np.int32)
    for gene in genes:
        values = frame[gene].to_numpy(dtype=object, copy=False)
        counts += np.fromiter(
            (
                isinstance(cell, str)
                and bool(cell.strip())
                and cell.strip().upper() != "WT"
                for cell in values
            ),
            dtype=np.int8,
            count=len(frame),
        )
    return counts


def _native_mutated_gene_counts(matrix, gene_count: int) -> np.ndarray:
    sample_width = 12
    block = matrix[:, sample_width:].tocoo()
    gene_indices = block.col // len(NATIVE_CONSEQUENCES)
    keys = block.row.astype(np.int64) * gene_count + gene_indices
    unique = np.unique(keys)
    return np.bincount(unique // gene_count, minlength=matrix.shape[0])


def audit_dataset(path: Path, *, has_target: bool) -> tuple[dict[str, object], tuple[str, ...]]:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    excluded = {"ID", "SUBCLASS"} if has_target else {"ID"}
    genes = tuple(column for column in frame.columns if column not in excluded)
    fitted = ParserNativeSemanticFamily(genes).fit(frame)
    matrix = fitted.transform(frame)
    raw_counts = _raw_mutated_gene_counts(frame, genes)
    native_counts = _native_mutated_gene_counts(matrix, len(genes))
    mismatch = np.flatnonzero(raw_counts != native_counts)
    return (
        {
            "path": str(path.relative_to(ROOT)),
            "sha256": sha256_file(path),
            "rows": len(frame),
            "gene_columns": len(genes),
            "matrix_shape": list(matrix.shape),
            "matrix_nnz": int(matrix.nnz),
            "mutation_presence_preserved": len(mismatch) == 0,
            "presence_mismatch_rows": mismatch[:20].tolist(),
            "contract": native_semantic_contract_record(fitted),
        },
        genes,
    )


def main() -> None:
    train, train_genes = audit_dataset(ROOT / "data" / "raw" / "train.csv", has_target=True)
    test, test_genes = audit_dataset(ROOT / "data" / "raw" / "test.csv", has_target=False)
    if train_genes != test_genes:
        raise ValueError("train/test 유전자 이름 또는 순서가 다릅니다.")
    if not train["mutation_presence_preserved"] or not test["mutation_presence_preserved"]:
        raise ValueError("native adapter가 mutation presence를 보존하지 못했습니다.")
    if train["contract"] != test["contract"]:
        raise ValueError("train/test native feature contract가 다릅니다.")
    document = {
        "schema_version": "1.0.0",
        "issue": 427,
        "analysis_only": True,
        "model_trained": False,
        "subclass_used": False,
        "public_lb_used": False,
        "train": train,
        "test": test,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "validation.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(document, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

