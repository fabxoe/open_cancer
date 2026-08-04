from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_cancer.hashing import sha256_file
from open_cancer.isoform_relative_position import (
    APPROVAL_STATUS,
    IsoformRelativePositionTransformer,
    resolve_isoform_relative_position_from_config,
)
from open_cancer.isoform_semantics import TranscriptAnnotation, serialise_annotation_index
from open_cancer.mutation_features import parse_mutation_token


def _annotation(
    transcript_id: str,
    length: int,
    *,
    mane: bool = False,
    canonical: bool = False,
) -> TranscriptAnnotation:
    return TranscriptAnnotation(
        gene_id="ENSG1",
        gene_symbol="GENE1",
        gene_biotype="protein_coding",
        transcript_id=transcript_id,
        transcript_biotype="protein_coding",
        protein_id=transcript_id.replace("ENST", "ENSP"),
        is_mane_select=mane,
        is_canonical=canonical,
        sequence="R" * length,
    )


def test_transformer_uses_mane_then_canonical_then_other() -> None:
    token = parse_mutation_token("R2H")
    transformer = IsoformRelativePositionTransformer(
        {"GENE1": (_annotation("ENST2", 4, canonical=True), _annotation("ENST1", 10, mane=True))}
    )
    assert transformer("GENE1", token) == (1.0,)

    transformer = IsoformRelativePositionTransformer(
        {"GENE1": (_annotation("ENST2", 10), _annotation("ENST1", 4, canonical=True))}
    )
    assert transformer("GENE1", token) == (3.0,)


def test_transformer_tie_break_and_bin_boundaries_are_deterministic() -> None:
    transformer = IsoformRelativePositionTransformer(
        {"GENE1": (_annotation("ENST2", 10), _annotation("ENST1", 4))}
    )
    assert transformer("GENE1", parse_mutation_token("R2H")) == (3.0,)

    boundary = IsoformRelativePositionTransformer(
        {"GENE1": (_annotation("ENST1", 10, mane=True),)}
    )
    assert boundary("GENE1", parse_mutation_token("R2H")) == (1.0,)
    assert boundary("GENE1", parse_mutation_token("R4H")) == (2.0,)
    assert boundary("GENE1", parse_mutation_token("R10H")) == (5.0,)


def test_transformer_maps_unsupported_or_mismatched_tokens_to_unobserved() -> None:
    transformer = IsoformRelativePositionTransformer(
        {"GENE1": (_annotation("ENST1", 10, mane=True),)}
    )
    assert transformer("GENE1", parse_mutation_token("A2H")) == ()
    assert transformer("GENE1", parse_mutation_token("R20H")) == ()
    assert transformer("GENE1", parse_mutation_token("2_3RA>Q")) == ()
    assert transformer("UNKNOWN", parse_mutation_token("R2H")) == ()


def _config(root: Path, manifest: Path, cache: Path) -> dict[str, object]:
    return {
        "features": {
            "residue_position": {
                "enabled": True,
                "aggregates": ["max"],
                "missing_policy": "indicator",
                "transform": "raw",
                "isoform_relative_bin": {
                    "enabled": True,
                    "bin_count": 5,
                    "manifest_path": str(manifest.relative_to(root)),
                    "manifest_sha256": sha256_file(manifest),
                    "annotation_cache_path": str(cache.relative_to(root)),
                    "annotation_cache_sha256": sha256_file(cache),
                },
            }
        }
    }


def test_resolver_verifies_frozen_contract(tmp_path: Path) -> None:
    cache = tmp_path / "index.json"
    serialise_annotation_index(
        {"GENE1": (_annotation("ENST1", 10, mane=True),)}, cache
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "ensembl_release": 116,
                "assembly": "GRCh38",
                "competition_external_annotation_permission": APPROVAL_STATUS,
                "team_lead_exception_reference": "https://example.test/issues/307#comment",
            }
        ),
        encoding="utf-8",
    )
    transformer, contract = resolve_isoform_relative_position_from_config(
        _config(tmp_path, manifest, cache), root=tmp_path
    )
    assert transformer is not None and contract is not None
    assert transformer("GENE1", parse_mutation_token("R2H")) == (1.0,)
    assert contract["bin_count"] == 5
    assert contract["target_used"] is False


def test_resolver_rejects_contract_drift(tmp_path: Path) -> None:
    cache = tmp_path / "index.json"
    serialise_annotation_index(
        {"GENE1": (_annotation("ENST1", 10, mane=True),)}, cache
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "ensembl_release": 116,
                "assembly": "GRCh38",
                "competition_external_annotation_permission": APPROVAL_STATUS,
                "team_lead_exception_reference": "https://example.test/issues/307#comment",
            }
        ),
        encoding="utf-8",
    )
    config = _config(tmp_path, manifest, cache)
    config["features"]["residue_position"]["aggregates"] = ["min"]
    with pytest.raises(ValueError, match="aggregates"):
        resolve_isoform_relative_position_from_config(config, root=tmp_path)

    config = _config(tmp_path, manifest, cache)
    config["features"]["residue_position"]["isoform_relative_bin"]["bin_count"] = 4
    with pytest.raises(ValueError, match="5개 bin"):
        resolve_isoform_relative_position_from_config(config, root=tmp_path)
