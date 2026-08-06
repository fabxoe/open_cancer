"""Task #557: fetch Ensembl release 116 Pfam protein-domain annotations for the
representative protein each trusted isoform-matched (gene, token) pair in
train+test actually resolves to.

Target-independent: SUBCLASS and Public LB are not used. Reuses the same
representative-isoform selection `isoform_relative_position.py` uses (MANE
Select > canonical > other-isoform, tie-broken by transcript/protein ID) so no
new isoform-choice logic is introduced -- only that already-frozen pick is
queried for domain annotation. This is a small, bounded set: each gene's
`competition_gene_isoform_index.json` entry lists every known isoform (avg ~26
per gene, up to 300), but only the single representative actually used by
EXP-374/392's residue-position feature per trusted token matters here.

Uses the Ensembl BioMart bulk export (`hsapiens_gene_ensembl` dataset,
`ensembl_peptide_id` filter, `pfam`/`pfam_start`/`pfam_end` attributes) in
batches, since one row-per-ID REST call for ~12-13k proteins is needlessly
slow -- BioMart returns ~500 proteins' domain calls in a single ~8s request
(measured), vs one call per protein via the row-by-row REST endpoint.

Run yourself with:

    uv run python scripts/fetch_ensembl_pfam_domain_catalog.py

Safe to interrupt and re-run: batches whose protein IDs are already present in
the combined output are skipped.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

from open_cancer.hashing import sha256_file
from open_cancer.isoform_position_mask import TRUSTED_POSITION_CATEGORIES
from open_cancer.isoform_semantics import (
    classify_token_semantics,
    load_annotation_index,
    resolve_substitution_eligibility,
)

ROOT = Path(__file__).resolve().parents[1]
ANNOTATION_CACHE = (
    ROOT / "data/external/ensembl_release_116/competition_gene_isoform_index.json"
)
OUTPUT_DIR = ROOT / "data/external/ensembl_release_116/domain_features"
RAW_BATCH_DIR = OUTPUT_DIR / "raw_batches"
COMBINED_PATH = OUTPUT_DIR / "pfam_domains_by_protein.json"
MANIFEST_PATH = ROOT / "knowledge/ensembl_protein_domain_annotation_v1.json"

BIOMART_URL = "https://www.ensembl.org/biomart/martservice"
BIOMART_DATASET = "hsapiens_gene_ensembl"
BATCH_SIZE = 400
BATCH_INTERVAL_SECONDS = 1.0
MAX_BATCH_RETRIES = 4
REQUEST_HEADERS = {
    "User-Agent": "open_cancer-research-script/1.0 (Task #557 Pfam domain precheck; "
    "target-independent, non-commercial competition research)"
}
QUERY_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE Query>
<Query virtualSchemaName="default" formatter="TSV" header="0" uniqueRows="1" count="" datasetConfigVersion="0.6">
<Dataset name="{dataset}" interface="default">
<Filter name="ensembl_peptide_id" value="{ids}"/>
<Attribute name="ensembl_peptide_id"/>
<Attribute name="pfam"/>
<Attribute name="pfam_start"/>
<Attribute name="pfam_end"/>
</Dataset>
</Query>"""


def _post_batch(query: str) -> str | None:
    """POST one BioMart query with retry/backoff. Returns None (caller skips
    this batch and retries it on the next script run) if every attempt fails,
    rather than raising and aborting the remaining batches."""

    last_error: Exception | None = None
    for attempt in range(MAX_BATCH_RETRIES):
        try:
            response = requests.post(
                BIOMART_URL, data={"query": query}, headers=REQUEST_HEADERS, timeout=60
            )
            if response.status_code == 200:
                return response.text
            last_error = requests.HTTPError(f"HTTP {response.status_code}: {response.text[:200]}")
        except requests.RequestException as exc:
            last_error = exc
        time.sleep(2.0 * (attempt + 1))
    print(f"배치 요청 {MAX_BATCH_RETRIES}회 재시도 후 실패, 건너뜀: {last_error}")
    return None


def _collect_gene_tokens(csv_path: Path) -> dict[str, set[str]]:
    frame = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    genes = [column for column in frame.columns if column not in {"ID", "SUBCLASS"}]
    gene_tokens: dict[str, set[str]] = {}
    for gene in genes:
        tokens: set[str] = set()
        for cell in frame[gene]:
            cell = cell.strip()
            if not cell or cell == "WT":
                continue
            for raw_token in cell.split():
                if raw_token != "WT":
                    tokens.add(raw_token)
        if tokens:
            gene_tokens[gene] = tokens
    return gene_tokens


def _needed_representative_protein_ids(annotation_index) -> set[str]:
    """The exact representative protein_id set the audit script will need --
    one per trusted (gene, token) pair, mirroring
    IsoformRelativePositionTransformer's selection so domain lookups line up
    with the existing relative-position bin feature 1:1."""

    train_tokens = _collect_gene_tokens(ROOT / "data/raw/train.csv")
    test_tokens = _collect_gene_tokens(ROOT / "data/raw/test.csv")
    merged: dict[str, set[str]] = {}
    for source in (train_tokens, test_tokens):
        for gene, tokens in source.items():
            merged.setdefault(gene, set()).update(tokens)

    needed: set[str] = set()
    for gene, tokens in merged.items():
        annotations = annotation_index.get(gene, ())
        for raw_token in tokens:
            category = classify_token_semantics(gene, raw_token, annotations).category
            if category not in TRUSTED_POSITION_CATEGORIES:
                continue
            eligibility = resolve_substitution_eligibility(raw_token)
            if eligibility is None:
                continue
            position, reference = eligibility
            matches = tuple(
                annotation
                for annotation in annotations
                if 1 <= position <= len(annotation.sequence)
                and annotation.sequence[position - 1] == reference
            )
            if not matches:
                continue
            if any(item.is_mane_select for item in matches):
                matches = tuple(item for item in matches if item.is_mane_select)
            elif any(item.is_canonical for item in matches):
                matches = tuple(item for item in matches if item.is_canonical)
            else:
                matches = tuple(
                    item
                    for item in matches
                    if not item.is_mane_select and not item.is_canonical
                )
            representative = min(matches, key=lambda item: (item.transcript_id, item.protein_id))
            needed.add(representative.protein_id)
    return needed


def _parse_batch_tsv(raw_text: str) -> dict[str, list[dict]]:
    by_protein: dict[str, list[dict]] = {}
    for line in raw_text.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        protein_id, pfam_id, start, end = parts
        by_protein.setdefault(protein_id, [])
        if pfam_id and start and end:
            by_protein[protein_id].append(
                {"pfam_id": pfam_id, "start": int(start), "end": int(end)}
            )
    return by_protein


def main() -> None:
    annotation_index = load_annotation_index(ANNOTATION_CACHE)
    needed_protein_ids = sorted(_needed_representative_protein_ids(annotation_index))
    print(f"실제 필요한 대표 protein_id 수: {len(needed_protein_ids)}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_BATCH_DIR.mkdir(parents=True, exist_ok=True)

    combined: dict[str, list[dict]] = {}
    if COMBINED_PATH.is_file():
        combined = json.loads(COMBINED_PATH.read_text(encoding="utf-8"))
        print(f"기존 결과 재사용: {len(combined)}건 이미 확보됨")

    pending = [pid for pid in needed_protein_ids if pid not in combined]
    batches = [pending[i : i + BATCH_SIZE] for i in range(0, len(pending), BATCH_SIZE)]
    print(f"남은 배치 수: {len(batches)} (배치당 최대 {BATCH_SIZE}개)")

    failed_batches = 0
    for batch_index, batch_ids in enumerate(batches, start=1):
        query = QUERY_TEMPLATE.format(dataset=BIOMART_DATASET, ids=",".join(batch_ids))
        raw_text = _post_batch(query)
        if raw_text is None:
            failed_batches += 1
            time.sleep(BATCH_INTERVAL_SECONDS)
            continue
        (RAW_BATCH_DIR / f"batch_{batch_index:04d}.tsv").write_text(raw_text, encoding="utf-8")

        parsed = _parse_batch_tsv(raw_text)
        missing = set(batch_ids) - set(parsed)
        for protein_id in missing:
            parsed.setdefault(protein_id, [])
        combined.update(parsed)

        COMBINED_PATH.write_text(
            json.dumps(combined, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(
            f"배치 {batch_index}/{len(batches)} 완료 "
            f"({len(batch_ids)}개 요청, {len(missing)}개 응답 누락 -> 0-domain 처리)"
        )
        time.sleep(BATCH_INTERVAL_SECONDS)

    if failed_batches:
        print(f"{failed_batches}개 배치 실패 -> 스크립트를 다시 실행하면 해당 배치만 재시도됩니다.")

    if not combined:
        print("성공한 배치가 없어 manifest를 만들지 않습니다. 다시 실행해주세요.")
        return

    proteins_with_zero = sum(1 for domains in combined.values() if not domains)
    proteins_with_any = len(combined) - proteins_with_zero
    total_domain_features = sum(len(domains) for domains in combined.values())

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
            "service": "Ensembl BioMart martservice",
            "url": BIOMART_URL,
            "dataset": BIOMART_DATASET,
            "filter": "ensembl_peptide_id",
            "attributes": ["ensembl_peptide_id", "pfam", "pfam_start", "pfam_end"],
            "protein_id_source": str(ANNOTATION_CACHE.relative_to(ROOT)),
            "protein_id_selection": "representative isoform per trusted (gene, token) pair in "
            "train+test, mirroring IsoformRelativePositionTransformer's MANE>canonical>other "
            "selection -- not every isoform listed in competition_gene_isoform_index.json",
            "protein_id_count": len(needed_protein_ids),
            "raw_batch_dir": str(RAW_BATCH_DIR.relative_to(ROOT)),
            "combined_output_path": str(COMBINED_PATH.relative_to(ROOT)),
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
            "proteins_with_zero_domains": proteins_with_zero,
            "proteins_with_at_least_one_domain": proteins_with_any,
            "total_domain_features": total_domain_features,
        },
        "combined_output_sha256": sha256_file(COMBINED_PATH),
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"완료: protein {len(combined)}개, manifest 저장: {MANIFEST_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
