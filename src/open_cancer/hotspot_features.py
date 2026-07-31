"""Position-specific known cancer hotspot features.

Unlike gene-level presence/type features, these encode whether a mutation
lands on a specific, well-established codon (e.g. BRAF V600, PIK3CA H1047)
rather than anywhere in the gene -- information no per-gene column can
express. The table below is restricted to (gene, position) pairs that were
verified against this dataset's own internal numbering consistency
(see scripts/explore_hotspot_numbering_consistency.py): every occurrence in
train+test agrees on a single reference amino acid, and that amino acid
matches the published canonical hotspot residue. A token only counts toward
a hotspot if both the position AND the reference amino acid match, which
filters out the rare (~1-2 per position) internal annotation noise found by
that check.

KRAS and NRAS hotspots (G12/G13/Q61) are intentionally omitted: those genes
are not columns in this panel at all (see EXP-012).
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import numpy as np
from scipy import sparse

from open_cancer.hashing import sha256_file, sha256_lines

SUBSTITUTION = re.compile(r"^([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]*)([ACDEFGHIKLMNPQRSTVWY*])$")

KNOWN_HOTSPOTS: tuple[tuple[str, int, str], ...] = (
    ("BRAF", 600, "V"),
    ("CTNNB1", 37, "S"),
    ("CTNNB1", 45, "S"),
    ("EGFR", 790, "T"),
    ("EGFR", 858, "L"),
    ("GNAS", 201, "R"),
    ("HRAS", 12, "G"),
    ("HRAS", 13, "G"),
    ("HRAS", 61, "Q"),
    ("IDH1", 132, "R"),
    ("IDH2", 140, "R"),
    ("IDH2", 172, "R"),
    ("PIK3CA", 545, "E"),
    ("PIK3CA", 1047, "H"),
    ("TP53", 175, "R"),
    ("TP53", 245, "G"),
    ("TP53", 248, "R"),
    ("TP53", 273, "R"),
    ("TP53", 282, "R"),
)

HOTSPOT_GENES: frozenset[str] = frozenset(gene for gene, _, _ in KNOWN_HOTSPOTS)
HOTSPOT_FEATURE_NAMES: tuple[str, ...] = (
    *(f"hotspot__{gene}_{position}" for gene, position, _ in KNOWN_HOTSPOTS),
    "hotspot__known_hotspot_total_count",
)


def _hotspot_lookup() -> dict[tuple[str, int], tuple[int, str]]:
    return {
        (gene, position): (index, reference)
        for index, (gene, position, reference) in enumerate(KNOWN_HOTSPOTS)
    }


def build_hotspot_matrix(path: Path, gene_start_column: int) -> sparse.csr_matrix:
    """Build a (n_rows, len(KNOWN_HOTSPOTS) + 1) matrix: per-hotspot hit + total."""

    lookup = _hotspot_lookup()
    total_features = len(KNOWN_HOTSPOTS)
    rows: list[int] = []
    cols: list[int] = []

    with Path(path).open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        header = next(reader)
        genes = header[gene_start_column:]
        relevant_columns = [
            (offset, gene) for offset, gene in enumerate(genes) if gene in HOTSPOT_GENES
        ]
        row_index = 0
        for row in reader:
            for offset, gene in relevant_columns:
                cell = row[gene_start_column + offset]
                if not cell:
                    continue
                for token in cell.split():
                    if token == "WT":
                        continue
                    match = SUBSTITUTION.fullmatch(token)
                    if match is None:
                        continue
                    reference, position_str, _alternate = match.groups()
                    hit = lookup.get((gene, int(position_str)))
                    if hit is None:
                        continue
                    output_index, expected_reference = hit
                    if reference != expected_reference:
                        continue
                    rows.append(row_index)
                    cols.append(output_index)
            row_index += 1

    individual = sparse.csr_matrix(
        (np.ones(len(rows), dtype=np.float32), (rows, cols)),
        shape=(row_index, total_features),
        dtype=np.float32,
    )
    total_count = np.asarray(individual.sum(axis=1)).ravel().astype(np.float32)
    total_column = sparse.csr_matrix(total_count.reshape(-1, 1))
    return sparse.hstack([individual, total_column], format="csr")


def build_hotspot_augmented_features(
    train_path: Path,
    test_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    """Build EXP-005 gene x type features plus known-hotspot indicator features."""

    from open_cancer.mutation_features import build_mutation_features

    base_dir = output_dir / "base_mutation_type_features"
    base_report = build_mutation_features(train_path, test_path, base_dir)

    train_base = sparse.load_npz(base_dir / "train_features.npz")
    test_base = sparse.load_npz(base_dir / "test_features.npz")

    train_hotspot = build_hotspot_matrix(train_path, gene_start_column=2)
    test_hotspot = build_hotspot_matrix(test_path, gene_start_column=1)

    train_matrix = sparse.hstack([train_base, train_hotspot], format="csr").astype(np.float32)
    test_matrix = sparse.hstack([test_base, test_hotspot], format="csr").astype(np.float32)

    names = [
        *json.loads((base_dir / "feature_names.json").read_text(encoding="utf-8")),
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
            "hotspot_features": list(HOTSPOT_FEATURE_NAMES),
            "known_hotspots": [
                {"gene": gene, "position": position, "reference_aa": reference}
                for gene, position, reference in KNOWN_HOTSPOTS
            ],
            "hotspot_validation_note": (
                "positions verified via scripts/explore_hotspot_numbering_consistency.py: "
                "single consistent reference AA across train+test, matching published "
                "canonical hotspot residues; a token counts only if both position and "
                "reference AA match."
            ),
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
