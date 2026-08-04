"""Resolve a frozen Ensembl-backed residue-position semantic mask."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from open_cancer.hashing import sha256_file
from open_cancer.isoform_semantics import (
    TranscriptAnnotation,
    classify_token_semantics,
    load_annotation_index,
)
from open_cancer.mutation_features import ParsedMutationToken, PositionTokenFilter


TRUSTED_POSITION_CATEGORIES = frozenset(
    {"MANE_MATCH", "CANONICAL_MATCH", "OTHER_ISOFORM_MATCH"}
)
MASKED_POSITION_CATEGORIES = frozenset(
    {
        "POSITION_VALID_REF_MISMATCH",
        "OUTSIDE_ALL_KNOWN_ISOFORMS",
        "COMPLEX_OR_UNMAPPABLE",
    }
)
APPROVAL_STATUS = "CONFIRMED_ALLOWED_TRACK_B_B2_TEAM_LEAD_EXCEPTION"


@dataclass(frozen=True)
class IsoformPositionMask:
    annotation_index: Mapping[str, Sequence[TranscriptAnnotation]]

    def __call__(self, gene_symbol: str, token: ParsedMutationToken) -> bool:
        result = classify_token_semantics(
            gene_symbol,
            token.raw,
            self.annotation_index.get(gene_symbol, ()),
        )
        return result.category in TRUSTED_POSITION_CATEGORIES


def resolve_isoform_position_mask_from_config(
    config: dict[str, Any], *, root: Path
) -> tuple[PositionTokenFilter | None, dict[str, Any] | None]:
    """Load and verify the optional Track B semantic mask from config."""

    residue = config.get("features", {}).get("residue_position", {})
    mask_config = residue.get("isoform_semantic_mask", {"enabled": False})
    if not mask_config.get("enabled", False):
        return None, None

    required_categories = frozenset(mask_config.get("trusted_categories", ()))
    if required_categories != TRUSTED_POSITION_CATEGORIES:
        raise ValueError(
            "Track B trusted categories는 사전 고정 MANE/CANONICAL/OTHER와 같아야 합니다."
        )
    requested_masked = frozenset(mask_config.get("masked_categories", ()))
    if requested_masked != MASKED_POSITION_CATEGORIES:
        raise ValueError("Track B masked categories가 사전 고정 계약과 다릅니다.")

    manifest_path = root / mask_config["manifest_path"]
    cache_path = root / mask_config["annotation_cache_path"]
    _verify_sha(manifest_path, mask_config["manifest_sha256"], "manifest")
    _verify_sha(cache_path, mask_config["annotation_cache_sha256"], "annotation cache")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("competition_external_annotation_permission") != APPROVAL_STATUS:
        raise ValueError("Track B B2 팀장 예외 승인 상태가 manifest와 일치하지 않습니다.")
    approval_reference = manifest.get("team_lead_exception_reference")
    if not approval_reference:
        raise ValueError("Track B B2 팀장 예외 승인 근거 링크가 없습니다.")

    index = load_annotation_index(cache_path)
    contract = {
        "enabled": True,
        "definition_version": "1.0.0",
        "fit_scope": "stateless frozen Ensembl annotation; no target or distribution fit",
        "ensembl_release": manifest["ensembl_release"],
        "assembly": manifest["assembly"],
        "manifest_path": mask_config["manifest_path"],
        "manifest_sha256": mask_config["manifest_sha256"],
        "annotation_cache_path": mask_config["annotation_cache_path"],
        "annotation_cache_sha256": mask_config["annotation_cache_sha256"],
        "trusted_categories": sorted(TRUSTED_POSITION_CATEGORIES),
        "masked_categories": sorted(MASKED_POSITION_CATEGORIES),
        "team_lead_exception_reference": approval_reference,
        "target_used": False,
        "test_distribution_used_for_rule": False,
        "public_leaderboard_used": False,
    }
    return IsoformPositionMask(index), contract


def _verify_sha(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Track B {label}가 없습니다: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(
            f"Track B {label} SHA-256 불일치: expected={expected}, actual={actual}"
        )
