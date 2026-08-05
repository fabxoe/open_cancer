"""Lossless handling for unresolved signed and bilateral-stop tokens."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


PARTIAL_TERMINAL_SEMANTICS_VERSION = "4.0.0"
PartialKind = Literal[
    "signed_nonstandard_frameshift",
    "bilateral_stop_unresolved",
    "not_applicable",
]

_SIGNED_FS = re.compile(r"^(?P<position>-[1-9][0-9]*)FS$", re.IGNORECASE)
_BILATERAL_STOP = re.compile(r"^\*(?P<position>[1-9][0-9]*)\*$")


@dataclass(frozen=True)
class PartialTerminalSemanticResult:
    raw_token: str
    normalized_token: str
    parse_status: str
    semantic_kind: PartialKind
    source_position: int | None = None
    source_position_text: str | None = None
    position_eligible: bool = False
    event_family_for_existing_adapter: str = "other_unmappable"
    frameshift_marker_present: bool = False
    stop_markers_present: int = 0
    coordinate_domain: str = "unresolved"
    interpretation_limit: str = ""


def parse_partial_terminal_token(raw_token: str) -> PartialTerminalSemanticResult:
    raw = raw_token.strip()
    normalized = raw.upper()
    signed = _SIGNED_FS.fullmatch(normalized)
    if signed is not None:
        text = signed.group("position")
        return PartialTerminalSemanticResult(
            raw_token=raw,
            normalized_token=normalized,
            parse_status="partial",
            semantic_kind="signed_nonstandard_frameshift",
            source_position=int(text),
            source_position_text=text,
            frameshift_marker_present=True,
            interpretation_limit=(
                "signed number is not eligible as a protein residue coordinate; "
                "protein token alone cannot prove 5-prime UTR or extension"
            ),
        )
    bilateral = _BILATERAL_STOP.fullmatch(normalized)
    if bilateral is not None:
        text = bilateral.group("position")
        return PartialTerminalSemanticResult(
            raw_token=raw,
            normalized_token=normalized,
            parse_status="partial",
            semantic_kind="bilateral_stop_unresolved",
            source_position=int(text),
            source_position_text=text,
            stop_markers_present=2,
            interpretation_limit=(
                "not enough syntax to classify as nonsense, stop-loss, or "
                "N/C-terminal extension"
            ),
        )
    return PartialTerminalSemanticResult(
        raw_token=raw,
        normalized_token=normalized,
        parse_status="not_applicable",
        semantic_kind="not_applicable",
        event_family_for_existing_adapter="other_unmappable",
    )

