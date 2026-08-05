"""EGFR A289/G598 + NFE2L2 E79 hotspot features (Issue #440).

Position-level hotspot pilot, same pattern as `ctnnb1_hotspot_features.py`
(Issue #296): DominoEffect-style panel-wide screening backlog, burden-clean
confirmed in `reports/analysis/hotspot_screening_burden_control.md`
("결과 4 -- 대기열"). Matching is position-level: (gene, position,
reference_aa) only, alternate amino acid is irrelevant -- same convention as
`hotspot_features.EXTENDED_HOTSPOTS` and `ctnnb1_hotspot_features.py`.

Uses the stop-notation-invariant token parser (matching the EXP-374 parent
contract) even though position matching itself only touches simple
substitution tokens and is unaffected by stop-notation normalization.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FeatureFamilyDescriptor
from open_cancer.robust_mutation_parser import parse_stop_notation_invariant_token

# (gene, position, reference_aa) -- position-level match, alternate AA ignored.
CANDIDATES: tuple[tuple[str, int, str], ...] = (
    ("EGFR", 289, "A"),
    ("EGFR", 598, "G"),
    ("NFE2L2", 79, "E"),
)
_KIND_TO_CANDIDATE = {f"{gene}_{position}": (gene, position, reference_aa) for gene, position, reference_aa in CANDIDATES}


def _cell_tokens(cell: object) -> list:
    if not isinstance(cell, str) or cell in ("", "WT"):
        return []
    return [
        parse_stop_notation_invariant_token(token)
        for token in cell.split()
        if token and token != "WT"
    ]


def _position_flag(frame: pd.DataFrame, *, gene: str, position: int, reference_aa: str) -> np.ndarray:
    if gene not in frame.columns:
        raise ValueError(f"패널에 없는 유전자입니다: {gene}")
    flags = np.zeros(len(frame), dtype=np.float32)
    for row_index, cell in enumerate(frame[gene]):
        for token in _cell_tokens(cell):
            ref = token.reference_amino_acid
            positions = token.residue_positions
            if not positions or ref is None:
                continue
            if positions[0] == position and ref == reference_aa:
                flags[row_index] = 1.0
                break
    return flags


@dataclass(frozen=True)
class FittedEgfrNfe2l2Family:
    """A fitted, single-column EGFR/NFE2L2 hotspot feature."""

    descriptor: FeatureFamilyDescriptor
    kind: str  # "EGFR_289" | "EGFR_598" | "NFE2L2_79"

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        gene, position, reference_aa = _KIND_TO_CANDIDATE[self.kind]
        flags = _position_flag(frame, gene=gene, position=position, reference_aa=reference_aa)
        return sparse.csr_matrix(flags[:, None])


@dataclass(frozen=True)
class EgfrNfe2l2Family:
    """Factory for one EGFR/NFE2L2 hotspot column (Issue #440).

    No `KnowledgeProvenance` file: hardcoded, cited literal (DominoEffect-
    style panel screening + burden-confound precheck), same provenance style
    as `hotspot_features.EXTENDED_HOTSPOTS` and `ctnnb1_hotspot_features.py`.
    """

    kind: str
    version: str = "1.0.0"

    def fit(self, train_frame: pd.DataFrame, target: pd.Series | None = None) -> FittedEgfrNfe2l2Family:
        del target
        if self.kind not in _KIND_TO_CANDIDATE:
            raise ValueError(f"지원하지 않는 kind입니다: {self.kind}")
        gene, position, _reference_aa = _KIND_TO_CANDIDATE[self.kind]
        if gene not in train_frame.columns:
            raise ValueError(f"패널에 없는 유전자입니다: {gene}")
        return FittedEgfrNfe2l2Family(
            descriptor=FeatureFamilyDescriptor(
                name=f"egfr_nfe2l2_{self.kind.lower()}",
                version=self.version,
                fit_scope="stateless",
                feature_names=(f"hotspot__{gene}_{position}",),
                external_knowledge=(),
            ),
            kind=self.kind,
        )


def egfr_289_family() -> EgfrNfe2l2Family:
    return EgfrNfe2l2Family(kind="EGFR_289")


def egfr_598_family() -> EgfrNfe2l2Family:
    return EgfrNfe2l2Family(kind="EGFR_598")


def nfe2l2_79_family() -> EgfrNfe2l2Family:
    return EgfrNfe2l2Family(kind="NFE2L2_79")
