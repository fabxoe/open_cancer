"""CTNNB1 D32/S33 phosphodegron hotspot features (Issue #296 pilot).

Position-specific refinement of CTNNB1's existing categorical mutation-type
columns -- structurally the same shape as the team's already-adopted
34-position hotspot table (`hotspot_features.EXTENDED_HOTSPOTS`, which
already includes CTNNB1 S37/S45), not the gene-group-OR pattern the Cell
Cycle pathway family (#170/#173) was rejected for.

D32/S33/S37/S45 are all residues of the same beta-catenin N-terminal
phosphodegron motif (the GSK3-beta/CK1 phosphorylation cluster degraded via
the destruction complex); S37/S45 are already in `EXTENDED_HOTSPOTS`, D32/S33
were found by a DominoEffect-style panel-wide screening (Issue #292 backlog)
and precheck confirmed via Vera Health gates A/B/C, with zero sample-ID
overlap against S37/S45 (see Issue #296 precheck discussion) -- so unlike
EXP-058 (APC/CTNNB1 positions collapsed into one flag and lost information),
these two are added as separate columns, matching `EXTENDED_HOTSPOTS`'s own
per-position convention.

Matching is position-level: (gene, position, reference_aa) only, same as
`hotspot_features.py` (NOT the exact (ref, position, alt)-triple convention
`pole_ed_features.py` uses) -- the alternate amino acid is irrelevant.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FeatureFamilyDescriptor
from open_cancer.mutation_features import parse_mutation_token

CTNNB1_GENE = "CTNNB1"

# (position, reference_aa) pairs -- position-level match, alternate AA ignored.
CTNNB1_D32_S33: tuple[tuple[int, str], ...] = (
    (32, "D"),
    (33, "S"),
)

_FAMILY_KINDS = ("d32", "s33")
_KIND_TO_POSITION_REF = {"d32": (32, "D"), "s33": (33, "S")}


def _ctnnb1_cell_tokens(cell: object) -> list:
    if not isinstance(cell, str) or cell in ("", "WT"):
        return []
    return [
        parse_mutation_token(token)
        for token in cell.split()
        if token and token != "WT"
    ]


def _ctnnb1_position_flag(frame: pd.DataFrame, *, position: int, reference_aa: str) -> np.ndarray:
    if CTNNB1_GENE not in frame.columns:
        raise ValueError(f"패널에 없는 유전자입니다: {CTNNB1_GENE}")
    flags = np.zeros(len(frame), dtype=np.float32)
    for row_index, cell in enumerate(frame[CTNNB1_GENE]):
        for token in _ctnnb1_cell_tokens(cell):
            ref = token.reference_amino_acid
            positions = token.residue_positions
            if not positions or ref is None:
                continue
            if positions[0] == position and ref == reference_aa:
                flags[row_index] = 1.0
                break
    return flags


def compute_ctnnb1_d32_flag(frame: pd.DataFrame) -> np.ndarray:
    """1.0 if CTNNB1 carries a substitution at position 32 with reference D."""

    return _ctnnb1_position_flag(frame, position=32, reference_aa="D")


def compute_ctnnb1_s33_flag(frame: pd.DataFrame) -> np.ndarray:
    """1.0 if CTNNB1 carries a substitution at position 33 with reference S."""

    return _ctnnb1_position_flag(frame, position=33, reference_aa="S")


@dataclass(frozen=True)
class FittedCtnnb1Family:
    """A fitted, single-column CTNNB1 D32/S33 hotspot feature."""

    descriptor: FeatureFamilyDescriptor
    kind: str  # "d32" | "s33"

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        position, reference_aa = _KIND_TO_POSITION_REF[self.kind]
        flags = _ctnnb1_position_flag(frame, position=position, reference_aa=reference_aa)
        return sparse.csr_matrix(flags[:, None])


@dataclass(frozen=True)
class Ctnnb1Family:
    """Factory for the CTNNB1 D32/S33 hotspot features (Issue #296).

    No `KnowledgeProvenance` file: this table is a hardcoded, cited literal
    (DominoEffect-style panel screening + Vera Health gate precheck), the
    same provenance style as `hotspot_features.EXTENDED_HOTSPOTS` and
    `pole_ed_features.PoleEdFamily`, not a downloadable licensed file.
    """

    kind: str  # "d32" | "s33"
    version: str = "1.0.0"

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedCtnnb1Family:
        del target
        if self.kind not in _FAMILY_KINDS:
            raise ValueError(f"지원하지 않는 kind입니다: {self.kind}")
        if CTNNB1_GENE not in train_frame.columns:
            raise ValueError(f"패널에 없는 유전자입니다: {CTNNB1_GENE}")
        return FittedCtnnb1Family(
            descriptor=FeatureFamilyDescriptor(
                name=f"ctnnb1_{self.kind}",
                version=self.version,
                fit_scope="stateless",
                feature_names=(f"hotspot__CTNNB1_{_KIND_TO_POSITION_REF[self.kind][0]}",),
                external_knowledge=(),
            ),
            kind=self.kind,
        )


def ctnnb1_d32_family() -> Ctnnb1Family:
    return Ctnnb1Family(kind="d32")


def ctnnb1_s33_family() -> Ctnnb1Family:
    return Ctnnb1Family(kind="s33")
