"""POLE exonuclease-domain (ED) hotspot/driver features (Issue #181 pilot).

Unlike the Cell Cycle pathway aggregation family (#170/#173, which OR'd many
genes together and was rejected), this is a single-gene, position-specific
refinement of POLE's existing categorical mutation-type columns --
structurally the same shape as the team's already-adopted 34-position
hotspot table (`hotspot_features.EXTENDED_HOTSPOTS`, EXP-031->085->094), not
the gene-group-OR pattern EXP-021/107/170/173 found to add no information.

POLE hypermutator (ultramutated) phenotype is driven by specific missense
mutations in the exonuclease/proofreading domain (ED, codons 268-471); ED
literature commonly cites P286R, V411L, S297F, A456P, S459F as the
recurrent hotspots (TCGA, ESMO endometrial cancer guidelines), with UCEC and
COAD as the cancer types where POLE-proofreading-deficient tumors are most
represented. This gene list/position table is synthesized from a domain
consultation (Vera Health, 2026-08-02) plus the literature it draws on,
not a single downloadable file -- so unlike
`pathway_aggregation_features.CellCyclePathwayFamily`, there is no
`KnowledgeProvenance` file hash here, matching the existing
`hotspot_features.EXTENDED_HOTSPOTS` convention of a hardcoded, cited
literal table.

Positions are matched as exact (reference, position, alternate) triples for
`POLE_HOTSPOT5` and `POLE_ED_DRIVER_EXTENDED` -- stricter than
`hotspot_features`'s (gene, position, reference)-only match, since these
tables were pre-checked against real train.csv data as exact substitution
tokens (Issue #181 pre-check: 22 / 28 / 41 positive rows respectively).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FeatureFamilyDescriptor
from open_cancer.mutation_features import parse_mutation_token

POLE_GENE = "POLE"
POLE_ED_RANGE: tuple[int, int] = (268, 471)  # inclusive exonuclease domain codons

# (reference_aa, position, alternate_aa) triples. Exact-alt match, not just
# (gene, position, reference) -- see module docstring.
POLE_HOTSPOT5: frozenset[tuple[str, int, str]] = frozenset(
    {
        ("P", 286, "R"),
        ("V", 411, "L"),
        ("S", 297, "F"),
        ("A", 456, "P"),
        ("S", 459, "F"),
    }
)

POLE_ED_DRIVER_EXTENDED: frozenset[tuple[str, int, str]] = frozenset(
    {
        ("P", 286, "R"),
        ("P", 286, "L"),
        ("S", 297, "F"),
        ("S", 297, "Y"),
        ("N", 363, "D"),
        ("N", 363, "K"),
        ("F", 367, "S"),
        ("F", 367, "V"),
        ("D", 368, "Y"),
        ("V", 411, "L"),
        ("L", 424, "I"),
        ("L", 424, "V"),
        ("P", 436, "R"),
        ("P", 436, "S"),
        ("M", 444, "K"),
        ("A", 456, "P"),
        ("Y", 458, "*"),
        ("S", 459, "F"),
        ("S", 461, "L"),
        ("A", 463, "P"),
        ("A", 465, "V"),
    }
)

_FAMILY_KINDS = ("hotspot5", "ed_driver_extended", "ed_any_missense")


def _pole_cell_tokens(cell: object) -> list:
    if not isinstance(cell, str) or cell in ("", "WT"):
        return []
    return [
        parse_mutation_token(token)
        for token in cell.split()
        if token and token != "WT"
    ]


def _pole_flags(
    frame: pd.DataFrame, *, mode: Literal["hotspot5", "ed_driver_extended", "ed_any_missense"]
) -> np.ndarray:
    if POLE_GENE not in frame.columns:
        raise ValueError(f"패널에 없는 유전자입니다: {POLE_GENE}")
    lookup = POLE_HOTSPOT5 if mode == "hotspot5" else POLE_ED_DRIVER_EXTENDED
    lower, upper = POLE_ED_RANGE
    flags = np.zeros(len(frame), dtype=np.float32)
    for row_index, cell in enumerate(frame[POLE_GENE]):
        for token in _pole_cell_tokens(cell):
            ref = token.reference_amino_acid
            alt = token.alternate_amino_acid
            positions = token.residue_positions
            if not positions or ref is None:
                continue
            position = positions[0]
            if mode == "ed_any_missense":
                if lower <= position <= upper and token.mutation_type == "missense":
                    flags[row_index] = 1.0
                    break
            else:
                if (ref, position, alt) in lookup:
                    flags[row_index] = 1.0
                    break
    return flags


def compute_pole_hotspot5_flag(frame: pd.DataFrame) -> np.ndarray:
    """1.0 if POLE carries exactly one of the 5 canonical ED hotspot substitutions."""

    return _pole_flags(frame, mode="hotspot5")


def compute_pole_ed_driver_extended_flag(frame: pd.DataFrame) -> np.ndarray:
    """1.0 if POLE carries one of the 21 extended ED driver substitutions."""

    return _pole_flags(frame, mode="ed_driver_extended")


def compute_pole_ed_any_missense_flag(frame: pd.DataFrame) -> np.ndarray:
    """1.0 if POLE carries any missense mutation within the ED (codons 268-471)."""

    return _pole_flags(frame, mode="ed_any_missense")


def compute_pole_non_ed_missense_flag(frame: pd.DataFrame) -> np.ndarray:
    """Diagnostic-only sanity-check control: any missense outside the ED range.

    Never wired into an official experiment; used only to check the "ED
    boundary carries the signal" hypothesis when interpreting D/E/F results.
    """

    if POLE_GENE not in frame.columns:
        raise ValueError(f"패널에 없는 유전자입니다: {POLE_GENE}")
    lower, upper = POLE_ED_RANGE
    flags = np.zeros(len(frame), dtype=np.float32)
    for row_index, cell in enumerate(frame[POLE_GENE]):
        for token in _pole_cell_tokens(cell):
            positions = token.residue_positions
            if not positions:
                continue
            position = positions[0]
            if not (lower <= position <= upper) and token.mutation_type == "missense":
                flags[row_index] = 1.0
                break
    return flags


@dataclass(frozen=True)
class FittedPoleEdFamily:
    """A fitted, single-column POLE ED hotspot/driver feature."""

    descriptor: FeatureFamilyDescriptor
    kind: str  # "hotspot5"; Issues #E/#F add "ed_driver_extended" / "ed_any_missense"

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        if self.kind == "hotspot5":
            flags = compute_pole_hotspot5_flag(frame)
        elif self.kind == "ed_driver_extended":
            flags = compute_pole_ed_driver_extended_flag(frame)
        elif self.kind == "ed_any_missense":
            flags = compute_pole_ed_any_missense_flag(frame)
        else:
            raise ValueError(f"지원하지 않는 kind입니다: {self.kind}")
        return sparse.csr_matrix(flags[:, None])


@dataclass(frozen=True)
class PoleEdFamily:
    """Factory for the POLE ED hotspot/driver features (Issue #181/E/F).

    No `KnowledgeProvenance` file: this table is a hardcoded, cited literal
    (domain consultation + literature), the same provenance style as
    `hotspot_features.EXTENDED_HOTSPOTS`, not a downloadable licensed file.
    """

    kind: str  # "hotspot5" | "ed_driver_extended" | "ed_any_missense"
    version: str = "1.0.0"

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedPoleEdFamily:
        del target
        if self.kind not in _FAMILY_KINDS:
            raise ValueError(f"지원하지 않는 kind입니다: {self.kind}")
        if POLE_GENE not in train_frame.columns:
            raise ValueError(f"패널에 없는 유전자입니다: {POLE_GENE}")
        return FittedPoleEdFamily(
            descriptor=FeatureFamilyDescriptor(
                name=f"pole_{self.kind}",
                version=self.version,
                fit_scope="stateless",
                feature_names=(f"pole__{self.kind}",),
                external_knowledge=(),
            ),
            kind=self.kind,
        )


def pole_hotspot5_family() -> PoleEdFamily:
    return PoleEdFamily(kind="hotspot5")


def pole_ed_driver_extended_family() -> PoleEdFamily:
    return PoleEdFamily(kind="ed_driver_extended")


def pole_ed_any_missense_family() -> PoleEdFamily:
    return PoleEdFamily(kind="ed_any_missense")
