"""Sparse patient vectors retaining parser-v4 gene, event and amino-acid meaning."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.canonical_mutation_events import parse_canonical_gene_cell
from open_cancer.feature_family import FeatureFamilyDescriptor
from open_cancer.parser_native_v2_features import native_v2_primary_family


PATIENT_SEMANTIC_VECTOR_VERSION = "1.0.0"
AMINO_ACIDS = tuple("ACDEFGHIKLMNPQRSTVWY")
ALTERNATE_SYMBOLS = (*AMINO_ACIDS, "STOP")
EVENT_FAMILIES = (
    "missense",
    "no_change",
    "nonsense",
    "start_codon_affected",
    "unknown_reference_substitution",
    "nonstandard_stop_reference",
    "frameshift",
    "deletion",
    "delins",
    "insertion",
    "duplication_candidate",
    "range_replacement",
    "range_stop",
    "range_no_change",
    "unresolved",
)


def _canonical_sequence(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.upper().replace("TER", "*")


def _family(event, *, gene_symbol: str) -> str:
    if event.route == "substitution" and event.event_type in EVENT_FAMILIES:
        return event.event_type
    if event.route in {"frameshift", "deletion", "delins"}:
        return event.route
    if event.route == "insertion":
        primary = native_v2_primary_family(event, gene_symbol=gene_symbol)
        return "duplication_candidate" if primary == "duplication_candidate" else "insertion"
    if event.route == "range_replacement":
        if event.payload.get("protein_no_change") is True:
            return "range_no_change"
        if event.payload.get("contains_stop") is True:
            return "range_stop"
        return "range_replacement"
    return "unresolved"


def _reference_sequence(event) -> str:
    payload = event.payload
    if event.route == "substitution":
        return _canonical_sequence(payload.get("reference_residue"))
    if event.route == "range_replacement":
        return _canonical_sequence(payload.get("reference_sequence"))
    return ""


def _alternate_sequence(event) -> str:
    payload = event.payload
    if event.route == "frameshift":
        candidate = _canonical_sequence(payload.get("first_new_peptide_candidate"))
        # Compact multi-letter prefixes such as SDEL133fs are candidates, not
        # a confirmed downstream peptide.  Count only one explicit first-new
        # residue and never expand the unknown shifted C-terminal sequence.
        return candidate if len(candidate) == 1 and candidate in ALTERNATE_SYMBOLS else ""
    for key in (
        "alternate_residue_canonical",
        "translated_alternate_sequence",
        "inserted_sequence",
    ):
        sequence = _canonical_sequence(payload.get(key))
        if sequence:
            return sequence
    return ""


def patient_semantic_feature_names(gene_columns: tuple[str, ...]) -> tuple[str, ...]:
    gene_event = tuple(
        f"gene__{gene}__parser_v4_{family}_token_count"
        for gene in gene_columns
        for family in EVENT_FAMILIES
    )
    reference = tuple(f"sample__parser_v4_reference_aa_count__{aa}" for aa in AMINO_ACIDS)
    alternate = tuple(
        f"sample__parser_v4_alternate_aa_count__{aa}" for aa in ALTERNATE_SYMBOLS
    )
    transitions = tuple(
        f"sample__parser_v4_substitution_count__{reference_aa}_to_{alternate_aa}"
        for reference_aa in AMINO_ACIDS
        for alternate_aa in ALTERNATE_SYMBOLS
    )
    inserted = tuple(
        f"sample__parser_v4_inserted_or_new_aa_count__{aa}" for aa in ALTERNATE_SYMBOLS
    )
    return (*gene_event, *reference, *alternate, *transitions, *inserted)


@dataclass(frozen=True)
class FittedPatientSemanticVector:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")

        gene_index = {gene: index for index, gene in enumerate(self.gene_columns)}
        family_index = {family: index for index, family in enumerate(EVENT_FAMILIES)}
        aa_index = {aa: index for index, aa in enumerate(AMINO_ACIDS)}
        alt_index = {aa: index for index, aa in enumerate(ALTERNATE_SYMBOLS)}
        gene_width = len(self.gene_columns) * len(EVENT_FAMILIES)
        reference_offset = gene_width
        alternate_offset = reference_offset + len(AMINO_ACIDS)
        transition_offset = alternate_offset + len(ALTERNATE_SYMBOLS)
        inserted_offset = transition_offset + len(AMINO_ACIDS) * len(ALTERNATE_SYMBOLS)

        row_counts: list[dict[int, float]] = [{} for _ in range(len(frame))]
        for gene in self.gene_columns:
            values = frame[gene].to_numpy(dtype=object, copy=False)
            for row_index, cell in enumerate(values):
                counts = row_counts[row_index]
                parsed = parse_canonical_gene_cell(cell)
                for event in parsed.events:
                    family = _family(event, gene_symbol=gene)
                    column = gene_index[gene] * len(EVENT_FAMILIES) + family_index[family]
                    counts[column] = counts.get(column, 0.0) + 1.0

                    reference = _reference_sequence(event)
                    alternate = _alternate_sequence(event)
                    for aa in reference:
                        if aa in aa_index:
                            key = reference_offset + aa_index[aa]
                            counts[key] = counts.get(key, 0.0) + 1.0
                    for aa in alternate:
                        symbol = "STOP" if aa == "*" else aa
                        if symbol in alt_index:
                            key = alternate_offset + alt_index[symbol]
                            counts[key] = counts.get(key, 0.0) + 1.0

                    if event.route == "substitution" and len(reference) == 1 and len(alternate) == 1:
                        alt_symbol = "STOP" if alternate == "*" else alternate
                        if reference in aa_index and alt_symbol in alt_index:
                            key = (
                                transition_offset
                                + aa_index[reference] * len(ALTERNATE_SYMBOLS)
                                + alt_index[alt_symbol]
                            )
                            counts[key] = counts.get(key, 0.0) + 1.0

                    if event.route in {"insertion", "delins", "frameshift", "range_replacement"}:
                        for aa in alternate:
                            symbol = "STOP" if aa == "*" else aa
                            if symbol in alt_index:
                                key = inserted_offset + alt_index[symbol]
                                counts[key] = counts.get(key, 0.0) + 1.0
        rows: list[int] = []
        columns: list[int] = []
        data: list[float] = []
        for row_index, counts in enumerate(row_counts):
            for column, value in sorted(counts.items()):
                rows.append(row_index)
                columns.append(column)
                data.append(value)
        return sparse.csr_matrix(
            (np.asarray(data, dtype=np.float32), (rows, columns)),
            shape=(len(frame), self.descriptor.output_dimension),
            dtype=np.float32,
        )


@dataclass(frozen=True)
class PatientSemanticVectorFamily:
    gene_columns: tuple[str, ...]
    version: str = PATIENT_SEMANTIC_VECTOR_VERSION

    def fit(self, train_frame: pd.DataFrame, target: pd.Series | None = None):
        del target
        names = patient_semantic_feature_names(self.gene_columns)
        return FittedPatientSemanticVector(
            descriptor=FeatureFamilyDescriptor(
                name="parser_v4_patient_semantic_vector",
                version=self.version,
                fit_scope="stateless",
                feature_names=names,
            ),
            gene_columns=self.gene_columns,
        )
