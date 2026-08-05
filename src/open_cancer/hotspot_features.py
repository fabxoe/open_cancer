"""Position-specific known cancer hotspot features.

Unlike gene-level presence/type features, these encode whether a mutation
lands on a specific, well-established codon (e.g. BRAF V600, PIK3CA H1047)
rather than anywhere in the gene -- information no per-gene column can
express. Both hotspot tables below are restricted to (gene, position) pairs
checked against the reference amino acid encoded in train.csv. The original
19 positions are literature-defined. The 15 additions are also
literature-defined and the official runner independently requires at least
five matching train observations for each position. Test data is transformed
with the fixed table but is not used to select or filter the official list.
A token only counts toward a hotspot if both the position AND the reference
amino acid match, which filters out rare internal annotation noise.

KRAS and NRAS hotspots (G12/G13/Q61) are intentionally omitted throughout:
those genes are not columns in this panel at all (see EXP-012).
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Callable

import numpy as np
from scipy import sparse

from open_cancer.hashing import sha256_file, sha256_lines

SUBSTITUTION = re.compile(r"^([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]*)([ACDEFGHIKLMNPQRSTVWY*])$")

HotspotTable = tuple[tuple[str, int, str], ...]
TokenNormalizer = Callable[[str], str]

KNOWN_HOTSPOTS: HotspotTable = (
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

# EXP-031 attempt 5: high-confidence additions mined from the EXP-012 COSMIC
# protect-gene whitelist (361 genes) via explore_hotspot_candidate_mining.py,
# then restricted by hand to individually well-established literature
# hotspots (see EXPERIMENT_HISTORY.md for the confidence rationale per gene).
# Genes/positions that passed the automated filters but are not classical
# point-mutation cancer drivers (HLA-A germline diversity, PABPC1, SIRPA,
# ATP1A1) or that could not be individually verified with confidence (the
# ~50-codon TP53 extension, KMT2D, PLEC, etc.) were deliberately left out.
ADDITIONAL_HOTSPOTS: HotspotTable = (
    ("PIK3CA", 542, "E"),
    ("PIK3CA", 546, "Q"),
    ("PIK3CA", 345, "N"),
    ("PTEN", 130, "R"),
    ("PTEN", 233, "R"),
    ("FBXW7", 505, "R"),
    ("AKT1", 17, "E"),
    ("U2AF1", 34, "S"),
    ("APC", 1450, "R"),
    ("APC", 876, "R"),
    ("POLE", 286, "P"),
    ("POLE", 411, "V"),
    ("KIT", 816, "D"),
    ("FGFR3", 249, "S"),
    ("RAC1", 29, "P"),
)

EXTENDED_HOTSPOTS: HotspotTable = KNOWN_HOTSPOTS + ADDITIONAL_HOTSPOTS

HOTSPOT_TABLES: dict[str, HotspotTable] = {
    "none": (),
    "extended_34": EXTENDED_HOTSPOTS,
}
HOTSPOT_EVIDENCE_TABLES: dict[str, HotspotTable] = {
    "none": (),
    # The original 19 are literature-fixed. The later 15 were mined from the
    # project train panel before manual literature review, so only those 15
    # receive the configurable train-only minimum-count guard.
    "additions_15": ADDITIONAL_HOTSPOTS,
}


def resolve_hotspot_config(
    config: dict[str, object],
) -> tuple[HotspotTable, HotspotTable, int]:
    """Resolve a fixed hotspot table and its train-only evidence contract."""

    table_name = str(config.get("table", "extended_34"))
    evidence_scope = str(config.get("evidence_scope", "additions_15"))
    try:
        hotspots = HOTSPOT_TABLES[table_name]
        evidence_hotspots = HOTSPOT_EVIDENCE_TABLES[evidence_scope]
    except KeyError as error:
        raise ValueError(f"지원하지 않는 hotspot config 값입니다: {error.args[0]}") from error
    minimum_matching_rows = int(config.get("minimum_matching_train_rows", 5))
    if minimum_matching_rows < 1:
        raise ValueError("minimum_matching_train_rows는 1 이상이어야 합니다.")
    if not set(evidence_hotspots).issubset(hotspots):
        raise ValueError("evidence_scope의 hotspot이 선택한 table에 포함되지 않습니다.")
    return hotspots, evidence_hotspots, minimum_matching_rows


def hotspot_feature_names(hotspots: HotspotTable) -> tuple[str, ...]:
    if not hotspots:
        return ()
    return (
        *(f"hotspot__{gene}_{position}" for gene, position, _ in hotspots),
        "hotspot__known_hotspot_total_count",
    )


HOTSPOT_FEATURE_NAMES: tuple[str, ...] = hotspot_feature_names(KNOWN_HOTSPOTS)
EXTENDED_HOTSPOT_FEATURE_NAMES: tuple[str, ...] = hotspot_feature_names(EXTENDED_HOTSPOTS)


def _hotspot_lookup(hotspots: HotspotTable) -> dict[tuple[str, int], tuple[int, str]]:
    return {
        (gene, position): (index, reference)
        for index, (gene, position, reference) in enumerate(hotspots)
    }


def build_hotspot_matrix(
    path: Path,
    gene_start_column: int,
    hotspots: HotspotTable = KNOWN_HOTSPOTS,
    token_normalizer: TokenNormalizer | None = None,
) -> sparse.csr_matrix:
    """Build a (n_rows, len(hotspots) + 1) matrix: per-hotspot hit + total."""

    lookup = _hotspot_lookup(hotspots)
    hotspot_genes = frozenset(gene for gene, _, _ in hotspots)
    total_features = len(hotspots)
    rows: list[int] = []
    cols: list[int] = []

    with Path(path).open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        header = next(reader)
        genes = header[gene_start_column:]
        relevant_columns = [
            (offset, gene) for offset, gene in enumerate(genes) if gene in hotspot_genes
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
                    normalized = token_normalizer(token) if token_normalizer else token
                    match = SUBSTITUTION.fullmatch(normalized)
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
    if not hotspots:
        return individual
    total_count = np.asarray(individual.sum(axis=1)).ravel().astype(np.float32)
    total_column = sparse.csr_matrix(total_count.reshape(-1, 1))
    return sparse.hstack([individual, total_column], format="csr")


def summarize_hotspot_train_evidence(
    train_path: Path,
    gene_start_column: int,
    hotspots: HotspotTable,
    include_row_indices: set[int] | None = None,
) -> list[dict[str, object]]:
    """Count reference-aware hotspot evidence using train rows only."""

    lookup = _hotspot_lookup(hotspots)
    counts = [0] * len(hotspots)
    observed_references: list[set[str]] = [set() for _ in hotspots]
    hotspot_genes = frozenset(gene for gene, _, _ in hotspots)

    with Path(train_path).open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        header = next(reader)
        genes = header[gene_start_column:]
        relevant_columns = [
            (offset, gene) for offset, gene in enumerate(genes) if gene in hotspot_genes
        ]
        for row_index, row in enumerate(reader):
            if include_row_indices is not None and row_index not in include_row_indices:
                continue
            for offset, gene in relevant_columns:
                for token in row[gene_start_column + offset].split():
                    match = SUBSTITUTION.fullmatch(token)
                    if match is None:
                        continue
                    reference, position_str, _alternate = match.groups()
                    hit = lookup.get((gene, int(position_str)))
                    if hit is None:
                        continue
                    output_index, expected_reference = hit
                    observed_references[output_index].add(reference)
                    if reference == expected_reference:
                        counts[output_index] += 1

    return [
        {
            "gene": gene,
            "position": position,
            "expected_reference_aa": expected_reference,
            "matching_train_rows": counts[index],
            "observed_reference_aas": sorted(observed_references[index]),
        }
        for index, (gene, position, expected_reference) in enumerate(hotspots)
    ]


def validate_hotspot_train_evidence(
    train_path: Path,
    gene_start_column: int,
    hotspots: HotspotTable,
    minimum_matching_rows: int,
    include_row_indices: set[int] | None = None,
) -> list[dict[str, object]]:
    """Require fixed hotspots to have consistent, sufficient train-only evidence."""

    evidence = summarize_hotspot_train_evidence(
        train_path,
        gene_start_column=gene_start_column,
        hotspots=hotspots,
        include_row_indices=include_row_indices,
    )
    failures = [
        item
        for item in evidence
        if item["matching_train_rows"] < minimum_matching_rows
        or item["observed_reference_aas"] != [item["expected_reference_aa"]]
    ]
    if failures:
        raise ValueError(
            "train-only hotspot 근거 검증에 실패했습니다: "
            + json.dumps(failures, ensure_ascii=False)
        )
    return evidence


def build_hotspot_augmented_features(
    train_path: Path,
    test_path: Path,
    output_dir: Path,
    hotspots: HotspotTable = KNOWN_HOTSPOTS,
    *,
    base_feature_options: dict[str, Any] | None = None,
    selected_position_features: tuple[str, ...] | None = None,
    position_missing_policy: str = "zero",
    position_token_scope: str = "include_complex",
    position_transform: str = "raw",
    position_bin_width: int = 100,
    hotspot_token_normalizer: TokenNormalizer | None = None,
) -> dict[str, object]:
    """Build configurable mutation features plus fixed hotspot indicators."""

    from open_cancer.mutation_features import build_mutation_features

    feature_names = hotspot_feature_names(hotspots)
    base_dir = output_dir / "base_mutation_type_features"
    mutation_options = dict(base_feature_options or {})
    if selected_position_features is not None:
        mutation_options.update(
            selected_position_features=selected_position_features,
            position_missing_policy=position_missing_policy,
            position_token_scope=position_token_scope,
            position_transform=position_transform,
            position_bin_width=position_bin_width,
        )
    base_report = build_mutation_features(
        train_path,
        test_path,
        base_dir,
        **mutation_options,
    )

    train_base = sparse.load_npz(base_dir / "train_features.npz")
    test_base = sparse.load_npz(base_dir / "test_features.npz")

    train_hotspot = build_hotspot_matrix(
        train_path,
        gene_start_column=2,
        hotspots=hotspots,
        token_normalizer=hotspot_token_normalizer,
    )
    test_hotspot = build_hotspot_matrix(
        test_path,
        gene_start_column=1,
        hotspots=hotspots,
        token_normalizer=hotspot_token_normalizer,
    )

    train_matrix = sparse.hstack([train_base, train_hotspot], format="csr").astype(np.float32)
    test_matrix = sparse.hstack([test_base, test_hotspot], format="csr").astype(np.float32)

    names = [
        *json.loads((base_dir / "feature_names.json").read_text(encoding="utf-8")),
        *feature_names,
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
            "hotspot_features": list(feature_names),
            "known_hotspots": [
                {"gene": gene, "position": position, "reference_aa": reference}
                for gene, position, reference in hotspots
            ],
            "hotspot_validation_note": (
                "The hotspot table is fixed before test transformation. The original "
                "19 and additional 15 positions are literature-defined; the config-driven "
                "runner validates the additions using train rows only. Test "
                "data is not used to select or filter the official list. A token "
                "counts only when both position and reference AA match."
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
