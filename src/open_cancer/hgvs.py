"""Protein-variant notation normalization with explicit information limits."""

from __future__ import annotations

import re
import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from open_cancer.hashing import sha256_file


AMINO_ACID_3 = {
    "A": "Ala",
    "C": "Cys",
    "D": "Asp",
    "E": "Glu",
    "F": "Phe",
    "G": "Gly",
    "H": "His",
    "I": "Ile",
    "K": "Lys",
    "L": "Leu",
    "M": "Met",
    "N": "Asn",
    "P": "Pro",
    "Q": "Gln",
    "R": "Arg",
    "S": "Ser",
    "T": "Thr",
    "V": "Val",
    "W": "Trp",
    "Y": "Tyr",
}

_SUBSTITUTION = re.compile(r"^([ACDEFGHIKLMNPQRSTVWY])([1-9][0-9]*)([ACDEFGHIKLMNPQRSTVWY*])$")
_INCOMPLETE_FRAMESHIFT = re.compile(r"^[ACDEFGHIKLMNPQRSTVWY][1-9][0-9]*fs$")


@dataclass(frozen=True)
class NormalizedToken:
    """One normalized token and whether a supported conversion was possible."""

    value: str
    status: str


def normalize_protein_token(token: str) -> NormalizedToken:
    """Normalize a one-letter protein substitution to three-letter HGVS syntax.

    The source data has no transcript accession. Therefore the returned value is
    only the protein-level description, without an ``NP_...`` reference prefix.
    Incomplete frameshift strings are preserved because a conforming frameshift
    description cannot be reconstructed from them.
    """

    match = _SUBSTITUTION.fullmatch(token)
    if match is not None:
        reference, position, alternate = match.groups()
        reference_3 = AMINO_ACID_3[reference]
        if alternate == reference:
            suffix = "="
        elif alternate == "*":
            suffix = "Ter"
        else:
            suffix = AMINO_ACID_3[alternate]
        return NormalizedToken(f"p.{reference_3}{position}{suffix}", "converted")

    if _INCOMPLETE_FRAMESHIFT.fullmatch(token):
        reference = token[0]
        position = token[1:-2]
        return NormalizedToken(
            f"p.({AMINO_ACID_3[reference]}{position}fs)",
            "converted_short_frameshift",
        )

    return NormalizedToken(token, "unsupported_unknown")


def normalize_protein_cell(value: str) -> tuple[str, list[str]]:
    """Normalize every whitespace-separated variant in one gene cell."""

    if value == "" or value == "WT":
        return value, []

    normalized = [normalize_protein_token(token) for token in value.split()]
    return " ".join(item.value for item in normalized), [item.status for item in normalized]


def normalize_train(input_path: Path, output_path: Path, report_path: Path) -> dict[str, object]:
    """Stream a train CSV into a new normalized file and return its audit report."""

    if input_path.resolve() == output_path.resolve():
        raise ValueError("원본 train.csv를 덮어쓸 수 없습니다.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    rows = 0

    with (
        input_path.open("r", encoding="utf-8", newline="") as source,
        output_path.open("w", encoding="utf-8", newline="") as destination,
    ):
        reader = csv.reader(source)
        writer = csv.writer(destination, lineterminator="\n")
        header = next(reader)
        if header[:2] != ["ID", "SUBCLASS"]:
            raise ValueError("train 앞 열은 ID,SUBCLASS여야 합니다.")
        writer.writerow(header)

        for row in reader:
            if len(row) != len(header):
                raise ValueError(f"{rows + 2}행의 열 수가 header와 다릅니다.")
            normalized_features: list[str] = []
            for value in row[2:]:
                normalized, statuses = normalize_protein_cell(value)
                normalized_features.append(normalized)
                counts.update(statuses)
            writer.writerow([row[0], row[1], *normalized_features])
            rows += 1

    report: dict[str, object] = {
        "source": {
            "path": str(input_path),
            "sha256": sha256_file(input_path),
        },
        "output": {
            "path": str(output_path),
            "sha256": sha256_file(output_path),
        },
        "rows": rows,
        "gene_columns": len(header) - 2,
        "token_counts": dict(sorted(counts.items())),
        "scope": "protein-level substitutions without transcript accession",
        "limitations": [
            "No transcript accession or version is present in the source data.",
            "Single-residue frameshifts use the predicted short protein form without a stop position.",
            "Complex or non-standard tokens are preserved unchanged.",
            "The output is not a validated genomic or coding-DNA HGVS description.",
        ],
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report
