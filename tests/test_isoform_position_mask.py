from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_cancer.hashing import sha256_file
from open_cancer.isoform_position_mask import (
    APPROVAL_STATUS,
    MASKED_POSITION_CATEGORIES,
    TRUSTED_POSITION_CATEGORIES,
    resolve_isoform_position_mask_from_config,
)
from open_cancer.isoform_semantics import TranscriptAnnotation, serialise_annotation_index
from open_cancer.mutation_features import parse_mutation_token


def _annotation(sequence: str) -> TranscriptAnnotation:
    return TranscriptAnnotation(
        gene_id="ENSG1",
        gene_symbol="GENE1",
        gene_biotype="protein_coding",
        transcript_id="ENST1",
        transcript_biotype="protein_coding",
        protein_id="ENSP1",
        is_mane_select=True,
        is_canonical=True,
        sequence=sequence,
    )


def _contract_files(tmp_path: Path) -> tuple[Path, Path]:
    cache = tmp_path / "index.json"
    serialise_annotation_index({"GENE1": (_annotation("MRAA"),)}, cache)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "ensembl_release": 116,
                "assembly": "GRCh38",
                "competition_external_annotation_permission": APPROVAL_STATUS,
                "team_lead_exception_reference": "https://example.test/issues/311#comment",
            }
        ),
        encoding="utf-8",
    )
    return manifest, cache


def _config(root: Path, manifest: Path, cache: Path) -> dict[str, object]:
    return {
        "features": {
            "residue_position": {
                "isoform_semantic_mask": {
                    "enabled": True,
                    "manifest_path": str(manifest.relative_to(root)),
                    "manifest_sha256": sha256_file(manifest),
                    "annotation_cache_path": str(cache.relative_to(root)),
                    "annotation_cache_sha256": sha256_file(cache),
                    "trusted_categories": sorted(TRUSTED_POSITION_CATEGORIES),
                    "masked_categories": sorted(MASKED_POSITION_CATEGORIES),
                }
            }
        }
    }


def test_resolver_is_disabled_by_default(tmp_path: Path) -> None:
    assert resolve_isoform_position_mask_from_config({}, root=tmp_path) == (None, None)


def test_resolver_keeps_only_sequence_supported_simple_tokens(tmp_path: Path) -> None:
    manifest, cache = _contract_files(tmp_path)
    token_filter, contract = resolve_isoform_position_mask_from_config(
        _config(tmp_path, manifest, cache), root=tmp_path
    )
    assert token_filter is not None and contract is not None
    assert token_filter("GENE1", parse_mutation_token("R2H")) is True
    assert token_filter("GENE1", parse_mutation_token("A2H")) is False
    assert token_filter("GENE1", parse_mutation_token("R20H")) is False
    assert token_filter("GENE1", parse_mutation_token("2_3RA>Q")) is False
    assert token_filter("UNKNOWN", parse_mutation_token("R2H")) is False
    assert contract["ensembl_release"] == 116
    assert contract["target_used"] is False
    assert contract["test_distribution_used_for_rule"] is False


def test_resolver_rejects_category_or_hash_drift(tmp_path: Path) -> None:
    manifest, cache = _contract_files(tmp_path)
    config = _config(tmp_path, manifest, cache)
    mask = config["features"]["residue_position"]["isoform_semantic_mask"]
    mask["trusted_categories"] = ["MANE_MATCH"]
    with pytest.raises(ValueError, match="trusted categories"):
        resolve_isoform_position_mask_from_config(config, root=tmp_path)

    config = _config(tmp_path, manifest, cache)
    config["features"]["residue_position"]["isoform_semantic_mask"][
        "annotation_cache_sha256"
    ] = "0" * 64
    with pytest.raises(ValueError, match="SHA-256"):
        resolve_isoform_position_mask_from_config(config, root=tmp_path)


def test_resolver_rejects_missing_exception_approval(tmp_path: Path) -> None:
    manifest, cache = _contract_files(tmp_path)
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["competition_external_annotation_permission"] = "UNCONFIRMED"
    manifest.write_text(json.dumps(document), encoding="utf-8")
    config = _config(tmp_path, manifest, cache)
    with pytest.raises(ValueError, match="예외 승인"):
        resolve_isoform_position_mask_from_config(config, root=tmp_path)
