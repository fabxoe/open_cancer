from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from open_cancer.hashing import sha256_file
from open_cancer.isoform_semantics import TranscriptAnnotation, serialise_annotation_index
from open_cancer.isoform_summary_features import (
    APPROVAL_STATUS,
    FEATURE_NAMES,
    IsoformSemanticSummaryFamily,
)


def _files(tmp_path: Path) -> tuple[Path, Path]:
    annotation = TranscriptAnnotation(
        gene_id="ENSG1", gene_symbol="GENE1", gene_biotype="protein_coding",
        transcript_id="ENST1", transcript_biotype="protein_coding",
        protein_id="ENSP1", is_mane_select=True, is_canonical=True,
        sequence="MRAA",
    )
    cache = tmp_path / "cache.json"
    serialise_annotation_index({"GENE1": (annotation,)}, cache)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "competition_external_annotation_permission": APPROVAL_STATUS,
        "team_lead_exception_reference": "https://example.test/issues/315#comment",
        "feature_contract": {
            "categories": [
                "MANE_MATCH", "CANONICAL_MATCH", "OTHER_ISOFORM_MATCH",
                "POSITION_VALID_REF_MISMATCH", "OUTSIDE_ALL_KNOWN_ISOFORMS",
                "COMPLEX_OR_UNMAPPABLE",
            ],
            "views": ["count", "any"], "output_dimension": 12,
        },
    }), encoding="utf-8")
    return manifest, cache


def _family(manifest: Path, cache: Path) -> IsoformSemanticSummaryFamily:
    return IsoformSemanticSummaryFamily(
        manifest, cache, sha256_file(manifest), sha256_file(cache)
    )


def test_summary_emits_six_counts_and_any_indicators(tmp_path: Path) -> None:
    manifest, cache = _files(tmp_path)
    fitted = _family(manifest, cache).fit(pd.DataFrame())
    frame = pd.DataFrame({
        "ID": ["A", "B"], "GENE1": ["R2H A2V 2_3RA>Q", "WT"]
    })
    result = fitted.transform(frame).toarray()
    assert result.shape == (2, 12)
    mane_count = FEATURE_NAMES.index("isoform_semantic__mane_match__count")
    mismatch_count = FEATURE_NAMES.index(
        "isoform_semantic__position_valid_ref_mismatch__count"
    )
    complex_count = FEATURE_NAMES.index("isoform_semantic__complex_or_unmappable__count")
    assert result[0, mane_count] == 1
    assert result[0, mismatch_count] == 1
    assert result[0, complex_count] == 1
    assert result[0, mane_count + 1] == 1
    assert result[1].sum() == 0


def test_summary_rejects_hash_or_approval_drift(tmp_path: Path) -> None:
    manifest, cache = _files(tmp_path)
    bad_hash = IsoformSemanticSummaryFamily(manifest, cache, "0" * 64, sha256_file(cache))
    with pytest.raises(ValueError, match="SHA-256"):
        bad_hash.fit(pd.DataFrame())
    document = json.loads(manifest.read_text(encoding="utf-8"))
    document["competition_external_annotation_permission"] = "UNCONFIRMED"
    manifest.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="예외 승인"):
        _family(manifest, cache).fit(pd.DataFrame())
