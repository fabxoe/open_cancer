"""EXP-005-style gene-by-mutation-type features crossed with COSMIC protect genes.

Instead of summarizing COSMIC knowledge into a single weighted burden scalar
(EXP-021), this keeps the mutation-type distinction from EXP-005 and adds a
handful of *typed* counts restricted to the COSMIC protect-gene whitelist
(EXP-012), e.g. "how many protect genes carry a loss-of-function mutation".
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from scipy import sparse

from open_cancer.hashing import sha256_file, sha256_lines
from open_cancer.mutation_features import GENE_FEATURES, GLOBAL_FEATURES, build_mutation_features

LOF_TYPES = ("nonsense", "frameshift")
COSMIC_CROSS_TYPES = GENE_FEATURES
COSMIC_CROSS_FEATURES = (
    *(f"cosmic__protect_{feature_type}_count" for feature_type in COSMIC_CROSS_TYPES),
    "cosmic__protect_lof_count",
)


def load_protect_genes(path: Path) -> list[str]:
    """Read the COSMIC-informed protect gene whitelist (local-only, see EXP-012)."""

    with Path(path).open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None or "gene" not in reader.fieldnames:
            raise ValueError(f"{path}: 'gene' 열이 필요합니다.")
        genes = [row["gene"] for row in reader]
    if not genes:
        raise ValueError(f"{path}: 보호 유전자 목록이 비어 있습니다.")
    return genes


def _protect_gene_indices(genes: list[str], protect_genes: set[str]) -> list[int]:
    indices = [index for index, gene in enumerate(genes) if gene in protect_genes]
    if not indices:
        raise ValueError("train 유전자 열과 겹치는 보호 유전자가 없습니다.")
    return indices


def _cross_feature_type_offsets(feature_name: str, type_index: dict[str, int]) -> list[int]:
    if feature_name == "cosmic__protect_lof_count":
        return [type_index[lof_type] for lof_type in LOF_TYPES]
    feature_type = feature_name.removeprefix("cosmic__protect_").removesuffix("_count")
    return [type_index[feature_type]]


def build_cosmic_cross_matrix(
    matrix: sparse.csr_matrix,
    genes: list[str],
    protect_genes: set[str],
    cross_features: tuple[str, ...] = COSMIC_CROSS_FEATURES,
) -> sparse.csr_matrix:
    """Sum per-gene mutation-type indicators over protect genes via one sparse matmul."""

    protect_indices = _protect_gene_indices(genes, protect_genes)
    gene_offset = len(GLOBAL_FEATURES)
    gene_stride = len(GENE_FEATURES)
    type_index = {name: index for index, name in enumerate(GENE_FEATURES)}

    selector_rows: list[int] = []
    selector_cols: list[int] = []
    for output_index, feature_name in enumerate(cross_features):
        offsets = _cross_feature_type_offsets(feature_name, type_index)
        for gene_index in protect_indices:
            for offset in offsets:
                selector_rows.append(gene_offset + gene_index * gene_stride + offset)
                selector_cols.append(output_index)

    selector = sparse.csr_matrix(
        (
            np.ones(len(selector_rows), dtype=np.float32),
            (selector_rows, selector_cols),
        ),
        shape=(matrix.shape[1], len(cross_features)),
        dtype=np.float32,
    )
    return (matrix @ selector).tocsr()


def build_cosmic_mutation_features(
    train_path: Path,
    test_path: Path,
    protect_genes_path: Path,
    output_dir: Path,
    cross_features: tuple[str, ...] = COSMIC_CROSS_FEATURES,
) -> dict[str, object]:
    """Build EXP-005 gene x type features plus COSMIC protect-gene cross features."""

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

    train_cross = build_cosmic_cross_matrix(train_base, genes, protect_gene_set, cross_features)
    test_cross = build_cosmic_cross_matrix(test_base, genes, protect_gene_set, cross_features)

    train_matrix = sparse.hstack([train_base, train_cross], format="csr").astype(np.float32)
    test_matrix = sparse.hstack([test_base, test_cross], format="csr").astype(np.float32)

    names = [
        *json.loads((base_dir / "feature_names.json").read_text(encoding="utf-8")),
        *cross_features,
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
            "cosmic_cross_features": list(cross_features),
            "cosmic_lof_types": list(LOF_TYPES),
            "protect_gene_whitelist_path": str(protect_genes_path),
            "protect_gene_whitelist_sha256": sha256_file(protect_genes_path),
            "protect_gene_count_in_whitelist": len(protect_gene_list),
            "protect_gene_count_matched": len(matched_protect_genes),
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
