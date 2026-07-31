"""EXP-031 attempt 4: combine the two feature families that beat/approached EXP-005.

Attempt 2 (COSMIC protect-gene LOF count) and attempt 3 (known hotspot
positions) are independent, non-overlapping signals on top of EXP-005's base
features -- attempt 2 targets loss-of-function burden in curated cancer
genes, attempt 3 targets specific activating codons. This combines both to
check whether their effects stack.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from scipy import sparse

from open_cancer.cosmic_mutation_features import build_cosmic_cross_matrix, load_protect_genes
from open_cancer.hashing import sha256_file, sha256_lines
from open_cancer.hotspot_features import HOTSPOT_FEATURE_NAMES, build_hotspot_matrix
from open_cancer.mutation_features import build_mutation_features

LOF_CROSS_FEATURES = ("cosmic__protect_lof_count",)


def build_lof_hotspot_features(
    train_path: Path,
    test_path: Path,
    protect_genes_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    """Build EXP-005 features + COSMIC protect-gene LOF count + known hotspots."""

    base_dir = output_dir / "base_mutation_type_features"
    base_report = build_mutation_features(train_path, test_path, base_dir)

    with Path(train_path).open("r", encoding="utf-8", newline="") as file:
        genes = next(csv.reader(file))[2:]

    protect_gene_list = load_protect_genes(protect_genes_path)
    protect_gene_set = set(protect_gene_list)
    matched_protect_genes = sorted(protect_gene_set & set(genes))
    if not matched_protect_genes:
        raise ValueError("보호 유전자 화이트리스트와 train 유전자 열이 겹치지 않습니다.")

    train_base = sparse.load_npz(base_dir / "train_features.npz")
    test_base = sparse.load_npz(base_dir / "test_features.npz")

    train_lof = build_cosmic_cross_matrix(train_base, genes, protect_gene_set, LOF_CROSS_FEATURES)
    test_lof = build_cosmic_cross_matrix(test_base, genes, protect_gene_set, LOF_CROSS_FEATURES)

    train_hotspot = build_hotspot_matrix(train_path, gene_start_column=2)
    test_hotspot = build_hotspot_matrix(test_path, gene_start_column=1)

    train_matrix = sparse.hstack(
        [train_base, train_lof, train_hotspot], format="csr"
    ).astype(np.float32)
    test_matrix = sparse.hstack(
        [test_base, test_lof, test_hotspot], format="csr"
    ).astype(np.float32)

    names = [
        *json.loads((base_dir / "feature_names.json").read_text(encoding="utf-8")),
        *LOF_CROSS_FEATURES,
        *HOTSPOT_FEATURE_NAMES,
    ]

    output_dir.mkdir(parents=True, exist_ok=True)
    train_matrix_path = output_dir / "train_features.npz"
    test_matrix_path = output_dir / "test_features.npz"
    names_path = output_dir / "feature_names.json"
    report_path = output_dir / "feature_report.json"

    sparse.save_npz(train_matrix_path, train_matrix, compressed=True)
    sparse.save_npz(test_matrix_path, test_matrix, compressed=True)
    names_path.write_text(json.dumps(names, ensure_ascii=False) + "\n", encoding="utf-8")

    report: dict[str, object] = {
        "inputs": base_report["inputs"],
        "base_dir": str(base_dir),
        "feature_contract": {
            **base_report["feature_contract"],
            "cosmic_cross_features": list(LOF_CROSS_FEATURES),
            "protect_gene_whitelist_path": str(protect_genes_path),
            "protect_gene_whitelist_sha256": sha256_file(protect_genes_path),
            "protect_gene_count_in_whitelist": len(protect_gene_list),
            "protect_gene_count_matched": len(matched_protect_genes),
            "hotspot_features": list(HOTSPOT_FEATURE_NAMES),
        },
        "train": {"shape": list(train_matrix.shape), "nonzero": int(train_matrix.nnz)},
        "test": {"shape": list(test_matrix.shape), "nonzero": int(test_matrix.nnz)},
        "feature_count": len(names),
        "feature_names_sha256": sha256_lines(names),
        "outputs": {},
    }
    output_paths = (train_matrix_path, test_matrix_path, names_path)
    report["outputs"] = {
        path.name: {"path": str(path), "sha256": sha256_file(path)} for path in output_paths
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
