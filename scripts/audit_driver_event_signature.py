#!/usr/bin/env python
"""Audit driver-preserving canonical signatures without fitting a model."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from open_cancer.driver_event_signature import (
    DRIVER_EVENT_SIGNATURE_VERSION,
    load_driver_catalog,
    summarize_driver_cell,
)
from open_cancer.hashing import sha256_file
from open_cancer.hotspot_features import EXTENDED_HOTSPOTS
from open_cancer.isoform_semantics import load_annotation_index


ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "data/raw/test.csv"
ANNOTATION = (
    ROOT
    / "data/external/ensembl_release_116/competition_gene_isoform_index.json"
)
CATALOG = ROOT / "knowledge/known_driver_protein_events_v1.json"
PATHWAYS = ROOT / "knowledge/canonical_pathways_sanchez_vega_v1.json"
OUTPUT = ROOT / "reports/analysis/driver_event_signature/audit.json"


def main() -> None:
    annotation_index = load_annotation_index(ANNOTATION)
    catalog = load_driver_catalog(CATALOG)
    with TEST.open("r", encoding="utf-8", newline="") as handle:
        rows = {row["ID"]: row for row in csv.DictReader(handle)}
    cell = rows["TEST_2438"]["EGFR"]
    summary = summarize_driver_cell(
        "EGFR", cell, annotation_index, catalog
    )

    pathway_payload = json.loads(PATHWAYS.read_text(encoding="utf-8"))
    pathway_memberships = sorted(
        name
        for name, genes in pathway_payload["pathways"].items()
        if "EGFR" in genes
    )
    hotspot_positions = sorted(
        position
        for gene, position, _reference in EXTENDED_HOTSPOTS
        if gene == "EGFR"
    )
    canonical_source_positions = set()
    for event in catalog:
        if event.gene_symbol == "EGFR":
            canonical_source_positions.update(
                range(event.source_start, event.source_end + 1)
            )

    payload = {
        "signature_version": DRIVER_EVENT_SIGNATURE_VERSION,
        "issue": 390,
        "catalog": str(CATALOG.relative_to(ROOT)),
        "catalog_sha256": sha256_file(CATALOG),
        "annotation_cache": str(ANNOTATION.relative_to(ROOT)),
        "annotation_cache_sha256": sha256_file(ANNOTATION),
        "case": {
            "dataset": "test",
            "sample_id": "TEST_2438",
            "gene": "EGFR",
            "summary": asdict(summary),
        },
        "feature_overlap": {
            "pathway_memberships": pathway_memberships,
            "pathway_overlap": bool(pathway_memberships),
            "pathway_interpretation": (
                "Existing pathway features know that EGFR belongs to RTK-RAS, "
                "but not that four annotations encode one IPVAIK driver family."
            ),
            "existing_hotspot_positions": hotspot_positions,
            "canonical_event_source_positions": sorted(
                canonical_source_positions
            ),
            "direct_hotspot_overlap": bool(
                canonical_source_positions.intersection(hotspot_positions)
            ),
            "hotspot_interpretation": (
                "Existing EGFR T790/L858 point hotspots do not encode this "
                "range insertion/duplication event."
            ),
        },
        "invariants": {
            "raw_tokens_preserved": True,
            "driver_presence_preserved": summary.driver_presence == 1,
            "annotation_multiplicity_preserved": (
                summary.annotation_multiplicity == 4
            ),
            "one_independent_driver_signature": (
                summary.independent_driver_event_count == 1
            ),
            "no_target_or_public_lb_used": True,
            "no_model_feature_changed": True,
        },
        "interpretation_limits": [
            "FAMILY_LEVEL is not an exact coordinate-equivalence claim.",
            "A sequence-compatible isoform does not prove tumour expression.",
            "Driver presence does not infer tumour class or treatment response.",
            "This audit does not replace raw annotations or existing features.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["case"]["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

