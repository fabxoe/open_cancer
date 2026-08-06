"""Task #557: fetch Ensembl release 116 Pfam protein-domain annotations for every
representative protein already selected by the frozen competition isoform index.

Target-independent: SUBCLASS and Public LB are not used. Reuses the same Ensembl
release 116 protein IDs already frozen in
`data/external/ensembl_release_116/competition_gene_isoform_index.json`
(Track B team-lead exception lineage, see PROJECT_CONTEXT.md and Issue #557) so no
new UniProt/Ensembl identity mapping is introduced. Queries the Ensembl REST
`overlap/translation` endpoint per protein ID (Pfam feature type only) and caches
the raw response per protein plus a provenance manifest mirroring the schema of
`knowledge/ensembl_isoform_annotation_v1.json`.

This is a long-running network fetch (one call per distinct protein ID, several
thousand total) -- run it yourself with:

    uv run python scripts/fetch_ensembl_pfam_domain_catalog.py

Safe to interrupt and re-run: already-cached per-protein response files are
skipped on resume.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from open_cancer.hashing import sha256_file
from open_cancer.isoform_semantics import load_annotation_index

ROOT = Path(__file__).resolve().parents[1]
ANNOTATION_CACHE = (
    ROOT / "data/external/ensembl_release_116/competition_gene_isoform_index.json"
)
RAW_DIR = ROOT / "data/external/ensembl_release_116/domain_features"
MANIFEST_PATH = ROOT / "knowledge/ensembl_protein_domain_annotation_v1.json"

REST_URL_TEMPLATE = (
    "https://rest.ensembl.org/overlap/translation/{protein_id}"
    "?type=Pfam;content-type=application/json"
)
REQUEST_INTERVAL_SECONDS = 0.15
MAX_RETRIES = 3


def _fetch_one(protein_id: str) -> list[dict]:
    url = REST_URL_TEMPLATE.format(protein_id=protein_id)
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, timeout=20)
            if response.status_code == 200:
                payload = response.json()
                return [item for item in payload if item.get("type") == "Pfam"]
            if response.status_code == 404:
                return []
            last_error = RuntimeError(f"HTTP {response.status_code} for {protein_id}")
        except requests.RequestException as exc:  # network hiccup, retry
            last_error = exc
        time.sleep(1.0 + attempt)
    raise RuntimeError(f"{protein_id} 조회 실패 (최대 재시도 초과): {last_error}")


def main() -> None:
    annotation_index = load_annotation_index(ANNOTATION_CACHE)
    protein_ids = sorted(
        {annotation.protein_id for entries in annotation_index.values() for annotation in entries}
    )

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    fetched = 0
    skipped_cached = 0
    for protein_id in protein_ids:
        cache_path = RAW_DIR / f"{protein_id}.json"
        if cache_path.is_file():
            skipped_cached += 1
            continue
        features = _fetch_one(protein_id)
        cache_path.write_text(
            json.dumps(features, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        fetched += 1
        if fetched % 200 == 0:
            print(f"...{fetched}건 신규 조회, {skipped_cached}건 캐시 재사용")
        time.sleep(REQUEST_INTERVAL_SECONDS)

    print(f"완료: 전체 protein {len(protein_ids)}개, 신규 조회 {fetched}건, 캐시 재사용 {skipped_cached}건")

    domain_count_by_protein = {}
    for protein_id in protein_ids:
        cache_path = RAW_DIR / f"{protein_id}.json"
        features = json.loads(cache_path.read_text(encoding="utf-8"))
        domain_count_by_protein[protein_id] = len(features)

    manifest = {
        "schema_version": "1.0.0",
        "snapshot_name": "ensembl_grch38_release_116_pfam_protein_domain_v1",
        "species": "Homo sapiens",
        "assembly": "GRCh38",
        "ensembl_release": 116,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "competition_external_annotation_permission": "PENDING_TEAM_LEAD_APPROVAL",
        "permission_scope": "Issue #557 target-independent coverage/redundancy precheck only; "
        "not yet approved for use in an Experiment feature",
        "permission_recorded_at": None,
        "permission_authority": None,
        "team_lead_exception_reference": None,
        "analysis_scope": "target-independent Pfam domain coverage and residue-position "
        "semantic redundancy precheck (Issue #557)",
        "source": {
            "role": "protein_domain_features",
            "endpoint": "https://rest.ensembl.org/overlap/translation/:id?type=Pfam",
            "documentation_url": "https://rest.ensembl.org/documentation/info/overlap_translation",
            "protein_id_source": str(ANNOTATION_CACHE.relative_to(ROOT)),
            "protein_id_count": len(protein_ids),
            "raw_response_dir": str(RAW_DIR.relative_to(ROOT)),
        },
        "license": {
            "data_terms": "Ensembl data generated by project members are available without "
            "restriction; third-party constraints may still apply.",
            "disclaimer_url": "https://www.ensembl.org/info/about/legal/disclaimer.html",
        },
        "interpretation_limits": [
            "Pfam domain calls describe the representative Ensembl protein sequence only; "
            "they are not patient-specific and do not encode SUBCLASS or any clinical label.",
            "Domain boundaries are static per protein_id and were not chosen or filtered by "
            "SUBCLASS, test distribution, or Public LB.",
        ],
        "domain_count_by_protein_summary": {
            "proteins_with_zero_domains": sum(
                1 for count in domain_count_by_protein.values() if count == 0
            ),
            "proteins_with_at_least_one_domain": sum(
                1 for count in domain_count_by_protein.values() if count > 0
            ),
            "total_domain_features": sum(domain_count_by_protein.values()),
        },
        "raw_response_files_sha256": {
            protein_id: sha256_file(RAW_DIR / f"{protein_id}.json") for protein_id in protein_ids
        },
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"manifest 저장: {MANIFEST_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
