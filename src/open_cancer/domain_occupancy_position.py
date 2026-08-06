"""Explore-only (Issue #557, RUN_MODE=explore, no EXP-ID) transformer: does a
trusted isoform-matched residue fall inside a known Pfam domain.

Not wired into any config-resolution path (contrast
`isoform_relative_position.resolve_isoform_relative_position_from_config`,
which enforces the Track B B2 team-lead permission gate) because the Pfam
domain manifest is still `PENDING_TEAM_LEAD_APPROVAL`
(`knowledge/ensembl_protein_domain_annotation_v1.json`). This module exists
purely to get a fast, unofficial OOF signal while approval is pending; it
must not be used by an official runner until that manifest's
`competition_external_annotation_permission` is `CONFIRMED_...` and this gets
a proper `resolve_*_from_config` wrapper mirroring the isoform ones.

Mirrors `IsoformRelativePositionTransformer`'s representative-isoform
selection (MANE Select > canonical > other-isoform, tie-broken by
transcript/protein ID) exactly, so the domain check lines up with the same
representative protein and position EXP-374/392 already use.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from open_cancer.isoform_semantics import TranscriptAnnotation, resolve_substitution_eligibility
from open_cancer.mutation_features import ParsedMutationToken


def load_domain_intervals(path: Path) -> dict[str, list[tuple[int, int]]]:
    combined = json.loads(path.read_text(encoding="utf-8"))
    return {
        protein_id: [(item["start"], item["end"]) for item in features]
        for protein_id, features in combined.items()
    }


@dataclass(frozen=True)
class DomainOccupancyTransformer:
    """Map a supported simple token to a 0/1 in-known-Pfam-domain indicator."""

    annotation_index: Mapping[str, Sequence[TranscriptAnnotation]]
    domain_intervals: Mapping[str, list[tuple[int, int]]]

    def __call__(self, gene_symbol: str, token: ParsedMutationToken) -> tuple[float, ...]:
        eligibility = resolve_substitution_eligibility(token.raw)
        if eligibility is None:
            return ()
        position, reference = eligibility
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
                item for item in matches if not item.is_mane_select and not item.is_canonical
            )
        representative = min(matches, key=lambda item: (item.transcript_id, item.protein_id))
        intervals = self.domain_intervals.get(representative.protein_id, [])
        in_domain = any(start <= position <= end for start, end in intervals)
        return (1.0 if in_domain else 0.0,)
