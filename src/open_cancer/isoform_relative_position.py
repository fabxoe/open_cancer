"""Resolve a frozen Ensembl-backed relative residue-position transform."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from open_cancer.hashing import sha256_file
from open_cancer.isoform_semantics import TranscriptAnnotation, load_annotation_index
from open_cancer.mutation_features import ParsedMutationToken, PositionTokenTransformer


APPROVAL_STATUS = "CONFIRMED_ALLOWED_TRACK_B_B2_RELATIVE_BIN_TEAM_LEAD_EXCEPTION"
BIN_COUNT = 5


@dataclass(frozen=True)
class IsoformRelativePositionTransformer:
    """Map a supported simple token to one deterministic relative-position bin."""

    annotation_index: Mapping[str, Sequence[TranscriptAnnotation]]
    bin_count: int = BIN_COUNT

    def __call__(
        self, gene_symbol: str, token: ParsedMutationToken
    ) -> tuple[float, ...]:
        if (
            token.token_shape != "substitution"
            or len(token.residue_positions) != 1
            or token.reference_amino_acid is None
            or len(token.reference_amino_acid) != 1
        ):
            return ()

        position = token.residue_positions[0]
        reference = token.reference_amino_acid
        matches = tuple(
            annotation
            for annotation in self.annotation_index.get(gene_symbol, ())
            if 1 <= position <= len(annotation.sequence)
            and annotation.sequence[position - 1] == reference
        )
        if not matches:
            return ()

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
        representative = min(
            matches, key=lambda item: (item.transcript_id, item.protein_id)
        )
        relative_position = position / len(representative.sequence)
        bin_value = min(
            self.bin_count,
            max(1, math.ceil(relative_position * self.bin_count)),
        )
        return (float(bin_value),)


def resolve_isoform_relative_position_from_config(
    config: dict[str, Any], *, root: Path
) -> tuple[PositionTokenTransformer | None, dict[str, Any] | None]:
    """Load and verify the optional Track B relative-position transform."""

    residue = config.get("features", {}).get("residue_position", {})
    transform_config = residue.get("isoform_relative_bin", {"enabled": False})
    if not transform_config.get("enabled", False):
        return None, None
    if residue.get("isoform_semantic_mask", {}).get("enabled", False):
        raise ValueError("isoform semantic mask와 relative bin을 동시에 사용할 수 없습니다.")
    if residue.get("transform", "raw") != "raw":
        raise ValueError("isoform relative bin은 추가 position transform과 함께 사용할 수 없습니다.")
    if residue.get("aggregates") != ["max"]:
        raise ValueError("첫 isoform relative-bin ablation은 aggregates: [max]로 고정합니다.")
    if residue.get("missing_policy", "zero") != "indicator":
        raise ValueError("isoform relative bin은 missing_policy: indicator로 고정합니다.")
    if transform_config.get("bin_count", BIN_COUNT) != BIN_COUNT:
        raise ValueError("첫 isoform relative-bin ablation은 5개 bin으로 고정합니다.")

    manifest_path = root / transform_config["manifest_path"]
    cache_path = root / transform_config["annotation_cache_path"]
    _verify_sha(manifest_path, transform_config["manifest_sha256"], "manifest")
    _verify_sha(cache_path, transform_config["annotation_cache_sha256"], "annotation cache")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("competition_external_annotation_permission") != APPROVAL_STATUS:
        raise ValueError("Track B B2-3 팀장 예외 승인 상태가 manifest와 일치하지 않습니다.")
    approval_reference = manifest.get("team_lead_exception_reference")
    if not approval_reference:
        raise ValueError("Track B B2-3 팀장 예외 승인 근거 링크가 없습니다.")

    transformer = IsoformRelativePositionTransformer(load_annotation_index(cache_path))
    contract = {
        "enabled": True,
        "definition_version": "1.0.0",
        "fit_scope": "stateless frozen Ensembl annotation; no target or distribution fit",
        "ensembl_release": manifest["ensembl_release"],
        "assembly": manifest["assembly"],
        "manifest_path": transform_config["manifest_path"],
        "manifest_sha256": transform_config["manifest_sha256"],
        "annotation_cache_path": transform_config["annotation_cache_path"],
        "annotation_cache_sha256": transform_config["annotation_cache_sha256"],
        "priority": ["MANE_MATCH", "CANONICAL_MATCH", "OTHER_ISOFORM_MATCH"],
        "tie_break": ["transcript_id", "protein_id"],
        "bin_count": BIN_COUNT,
        "unmapped_value": 0,
        "observed_indicator": True,
        "team_lead_exception_reference": approval_reference,
        "target_used": False,
        "test_distribution_used_for_rule": False,
        "public_leaderboard_used": False,
    }
    return transformer, contract


def _verify_sha(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Track B {label}가 없습니다: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(
            f"Track B {label} SHA-256 불일치: expected={expected}, actual={actual}"
        )
