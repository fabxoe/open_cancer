"""Gene to pathway membership catalog built from an external literature source.

Source: Sanchez-Vega F, et al. "Oncogenic Signaling Pathways in The Cancer
Genome Atlas." Cell. 2018;173(2):321-337. doi:10.1016/j.cell.2018.03.035,
Supplementary Table S3. Ten pathway sheets, each curated for the TCGA
PanCanAtlas cohort (the same 33 tumor types our 26-class panel is drawn
from), giving OG/TSG labels and literature hotspot codons per gene.

This module only builds a reference catalog (gene, pathway, OG/TSG, hotspot
positions, panel/whitelist membership). It does not compute any per-patient
feature and is not a model experiment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import openpyxl

PATHWAY_SHEETS: tuple[str, ...] = (
    "Cell Cycle",
    "HIPPO",
    "MYC",
    "NOTCH",
    "NRF2",
    "PI3K",
    "TGF-Beta",
    "RTK RAS",
    "TP53",
    "WNT",
)

_POSITION_TOKEN = re.compile(r"(\d+)")


def parse_hotspot_positions(raw: object) -> tuple[int, ...]:
    """Extract residue-position integers from a Table S3 hotspot cell.

    Cells look like ``"R80, H83"`` (substitution hotspots), ``"X159_splice"``
    (splice-site hotspots), ``"M1"`` (single hotspot), ``"-"`` or blank (no
    hotspot). Only the numeric position is extracted; the reference amino
    acid letter and splice annotation are not retained here.
    """

    if raw is None:
        return ()
    text = str(raw).strip()
    if not text or text == "-":
        return ()
    positions: list[int] = []
    for token in text.split(","):
        token = token.strip()
        if not token:
            continue
        match = _POSITION_TOKEN.search(token)
        if match:
            positions.append(int(match.group(1)))
    return tuple(positions)


def _normalize_og_tsg(raw: object) -> str:
    if raw is None:
        return "Unknown"
    text = str(raw).strip()
    return text if text in {"OG", "TSG"} else "Unknown"


@dataclass(frozen=True)
class PathwayRow:
    gene: str
    pathway: str
    og_tsg: str
    hotspot_positions: tuple[int, ...]


def _find_header_row(rows: list[tuple[Any, ...]]) -> int:
    for index, row in enumerate(rows):
        if row and row[0] == "Gene":
            return index
    raise ValueError("'Gene' 헤더 행을 찾지 못했습니다.")


def load_pathway_rows(
    xlsx_path: Path, pathways: tuple[str, ...] = PATHWAY_SHEETS
) -> list[PathwayRow]:
    """Read the Gene / OG-TSG / Hotspots (AA #) columns from each pathway sheet."""

    workbook = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    records: list[PathwayRow] = []
    for pathway in pathways:
        worksheet = workbook[pathway]
        rows = list(worksheet.iter_rows(values_only=True))
        header_index = _find_header_row(rows)
        header = rows[header_index]
        gene_col = header.index("Gene")
        og_tsg_col = header.index("OG/TSG")
        hotspot_col = header.index("Hotspots (AA #)")
        for row in rows[header_index + 1 :]:
            if not row or not row[gene_col]:
                continue
            gene = str(row[gene_col]).strip()
            if not gene:
                continue
            records.append(
                PathwayRow(
                    gene=gene,
                    pathway=pathway,
                    og_tsg=_normalize_og_tsg(row[og_tsg_col]),
                    hotspot_positions=parse_hotspot_positions(row[hotspot_col]),
                )
            )
    return records


def build_catalog_table(
    rows: list[PathwayRow],
    panel_genes: frozenset[str],
    cosmic_whitelist_genes: frozenset[str],
) -> list[dict[str, Any]]:
    """Attach panel/whitelist membership flags to each (gene, pathway) row."""

    table: list[dict[str, Any]] = []
    for row in rows:
        table.append(
            {
                "gene": row.gene,
                "pathway": row.pathway,
                "og_tsg": row.og_tsg,
                "hotspot_positions": ";".join(str(p) for p in row.hotspot_positions),
                "in_panel": row.gene in panel_genes,
                "in_cosmic_whitelist": row.gene in cosmic_whitelist_genes,
            }
        )
    return table


def summarize_pathway_coverage(
    table: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Per-pathway gene count, panel coverage, and OG/TSG distribution."""

    summary: dict[str, dict[str, Any]] = {}
    for pathway in PATHWAY_SHEETS:
        pathway_rows = [row for row in table if row["pathway"] == pathway]
        gene_count = len(pathway_rows)
        in_panel_count = sum(1 for row in pathway_rows if row["in_panel"])
        summary[pathway] = {
            "pathway": pathway,
            "gene_count": gene_count,
            "in_panel_count": in_panel_count,
            "panel_coverage_pct": (
                round(100 * in_panel_count / gene_count, 4) if gene_count else 0.0
            ),
            "og_count": sum(1 for row in pathway_rows if row["og_tsg"] == "OG"),
            "tsg_count": sum(1 for row in pathway_rows if row["og_tsg"] == "TSG"),
            "unknown_og_tsg_count": sum(
                1 for row in pathway_rows if row["og_tsg"] == "Unknown"
            ),
            "in_cosmic_whitelist_count": sum(
                1 for row in pathway_rows if row["in_cosmic_whitelist"]
            ),
        }
    return [summary[pathway] for pathway in PATHWAY_SHEETS]


def cross_validate_hotspots(
    table: list[dict[str, Any]],
    known_hotspots: tuple[tuple[str, int, str], ...],
) -> dict[str, Any]:
    """Compare Table S3 hotspot positions against the team's adopted 34-position list.

    A match requires the same (gene, position); the reference amino acid in
    ``known_hotspots`` is reported alongside for a human to sanity-check, but
    is not required to appear verbatim in the Table S3 cell (Table S3 hotspot
    cells omit the reference letter for some entries and this catalog does
    not re-derive it).
    """

    table_s3_positions: set[tuple[str, int]] = set()
    table_s3_genes: set[str] = set()
    for row in table:
        table_s3_genes.add(row["gene"])
        if not row["hotspot_positions"]:
            continue
        for token in row["hotspot_positions"].split(";"):
            table_s3_positions.add((row["gene"], int(token)))

    matches = []
    position_unmatched = []
    gene_absent = []
    for gene, position, reference_aa in known_hotspots:
        item = {"gene": gene, "position": position, "team_reference_aa": reference_aa}
        if (gene, position) in table_s3_positions:
            matches.append(item)
        elif gene in table_s3_genes:
            position_unmatched.append(item)
        else:
            gene_absent.append(item)
    return {
        "total_known_hotspots": len(known_hotspots),
        "matched_count": len(matches),
        "position_unmatched_count": len(position_unmatched),
        "gene_absent_count": len(gene_absent),
        "matches": matches,
        "position_unmatched": position_unmatched,
        "gene_absent": gene_absent,
    }
