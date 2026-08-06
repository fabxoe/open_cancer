"""Fold-safe compact clinical mutation features built on parser v4.

This module reproduces a useful *feature architecture* shared by another team
without reproducing its incomplete regular-expression parser.  Parser v4 is
the semantic authority; this adapter deliberately compresses its output into
mutation presence, truncating presence, recurrent exact missense and a small
patient-summary block.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.canonical_mutation_events import parse_canonical_gene_cell
from open_cancer.feature_family import FeatureFamilyDescriptor
from open_cancer.parser_native_v2_features import native_v2_primary_family


COMPACT_CLINICAL_FEATURE_VERSION = "1.0.0"
SUMMARY_NAMES = (
    "summary__mutated_gene_count",
    "summary__total_event_count",
    "summary__multi_event_gene_count",
    "summary__truncating_gene_count",
    "summary__missense_event_count",
    "summary__synonymous_event_count",
    "summary__nonsense_event_count",
    "summary__frameshift_event_count",
    "summary__deletion_event_count",
    "summary__delins_event_count",
    "summary__insertion_event_count",
    "summary__duplication_candidate_event_count",
    "summary__range_replacement_event_count",
    "summary__other_event_count",
)


def _is_non_wt(cell: object) -> bool:
    return isinstance(cell, str) and bool(cell.strip()) and cell.strip().upper() != "WT"


def _is_truncating(event: Any) -> bool:
    return (
        event.route == "frameshift"
        or (event.route == "substitution" and event.event_type == "nonsense")
        or (event.route == "delins" and event.event_type == "nonsense")
        or (
            event.route == "range_replacement"
            and event.payload.get("contains_stop") is True
        )
    )


def _exact_missense_key(gene: str, event: Any) -> str | None:
    if event.route != "substitution" or event.event_type != "missense":
        return None
    payload = event.payload
    reference = payload.get("reference_residue")
    position = payload.get("position")
    alternate = payload.get("alternate_residue_canonical")
    if not reference or not position or not alternate:
        return None
    return f"{gene}:{reference}{int(position)}{alternate}"


def _feature_hash(names: tuple[str, ...]) -> str:
    payload = "\n".join(names).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class FittedCompactClinicalMutationFamily:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    mutated_genes: tuple[str, ...]
    truncating_genes: tuple[str, ...]
    recurrent_missense_keys: tuple[str, ...]
    recurrent_missense_support: tuple[tuple[str, int], ...]
    recurrent_missense_genes: tuple[str, ...]
    hotspot_min_patient_count: int

    def metadata(self) -> dict[str, Any]:
        return {
            "version": COMPACT_CLINICAL_FEATURE_VERSION,
            "fit_scope": "fold_train",
            "hotspot_min_patient_count": self.hotspot_min_patient_count,
            "mutated_gene_count": len(self.mutated_genes),
            "truncating_gene_count": len(self.truncating_genes),
            "recurrent_missense_gene_count": len(self.recurrent_missense_genes),
            "recurrent_missense_key_count": len(self.recurrent_missense_keys),
            "recurrent_missense_support": dict(self.recurrent_missense_support),
            "feature_count": len(self.descriptor.feature_names),
            "feature_names_sha256": _feature_hash(self.descriptor.feature_names),
            "test_distribution_used_for_fit": False,
            "target_used_for_fit": False,
        }

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        missing = [gene for gene in self.gene_columns if gene not in frame.columns]
        if missing:
            raise ValueError(f"입력에 유전자 열이 없습니다: {missing[:5]}")

        mutated_index = {gene: i for i, gene in enumerate(self.mutated_genes)}
        truncating_offset = len(self.mutated_genes)
        truncating_index = {
            gene: truncating_offset + i for i, gene in enumerate(self.truncating_genes)
        }
        recurrent_offset = truncating_offset + len(self.truncating_genes)
        recurrent_index = {
            gene: recurrent_offset + i
            for i, gene in enumerate(self.recurrent_missense_genes)
        }
        summary_offset = recurrent_offset + len(self.recurrent_missense_genes)
        recurrent_keys = set(self.recurrent_missense_keys)

        rows: list[int] = []
        columns: list[int] = []
        values: list[float] = []
        summary = np.zeros((len(frame), len(SUMMARY_NAMES)), dtype=np.float32)

        for gene in self.gene_columns:
            gene_values = frame[gene].to_numpy(dtype=object, copy=False)
            for row_index in np.flatnonzero(
                np.fromiter((_is_non_wt(value) for value in gene_values), bool, len(frame))
            ):
                cell = parse_canonical_gene_cell(gene_values[row_index])
                if gene in mutated_index:
                    rows.append(int(row_index)); columns.append(mutated_index[gene]); values.append(1.0)
                summary[row_index, 0] += 1.0
                summary[row_index, 1] += len(cell.events)
                if len(cell.events) > 1:
                    summary[row_index, 2] += 1.0

                has_truncating = False
                has_recurrent = False
                for event in cell.events:
                    family = native_v2_primary_family(event, gene_symbol=gene)
                    if family == "substitution:missense": summary[row_index, 4] += 1.0
                    elif family == "substitution:no_change": summary[row_index, 5] += 1.0
                    elif family in {"substitution:nonsense", "range_stop"}: summary[row_index, 6] += 1.0
                    elif family == "frameshift": summary[row_index, 7] += 1.0
                    elif family == "deletion": summary[row_index, 8] += 1.0
                    elif family == "delins": summary[row_index, 9] += 1.0
                    elif family == "insertion": summary[row_index, 10] += 1.0
                    elif family == "duplication_candidate": summary[row_index, 11] += 1.0
                    elif family in {"range_replacement", "range_no_change"}: summary[row_index, 12] += 1.0
                    else: summary[row_index, 13] += 1.0
                    has_truncating = has_truncating or _is_truncating(event)
                    key = _exact_missense_key(gene, event)
                    has_recurrent = has_recurrent or (key is not None and key in recurrent_keys)

                if has_truncating:
                    summary[row_index, 3] += 1.0
                    if gene in truncating_index:
                        rows.append(int(row_index)); columns.append(truncating_index[gene]); values.append(1.0)
                if has_recurrent and gene in recurrent_index:
                    rows.append(int(row_index)); columns.append(recurrent_index[gene]); values.append(1.0)

        for row_index, column_index in zip(*np.nonzero(summary)):
            rows.append(int(row_index)); columns.append(summary_offset + int(column_index))
            values.append(float(summary[row_index, column_index]))
        return sparse.csr_matrix(
            (values, (rows, columns)),
            shape=(len(frame), len(self.descriptor.feature_names)),
            dtype=np.float32,
        )


@dataclass(frozen=True)
class CompactClinicalMutationFamily:
    gene_columns: tuple[str, ...]
    hotspot_min_patient_count: int = 5
    version: str = COMPACT_CLINICAL_FEATURE_VERSION

    def fit(
        self, train_frame: pd.DataFrame, target: pd.Series | None = None
    ) -> FittedCompactClinicalMutationFamily:
        del target
        if self.hotspot_min_patient_count < 1:
            raise ValueError("hotspot_min_patient_count는 1 이상이어야 합니다.")
        missing = [gene for gene in self.gene_columns if gene not in train_frame.columns]
        if missing:
            raise ValueError(f"학습 입력에 유전자 열이 없습니다: {missing[:5]}")

        mutated: set[str] = set()
        truncating: set[str] = set()
        patient_support: Counter[str] = Counter()
        for gene in self.gene_columns:
            values = train_frame[gene].to_numpy(dtype=object, copy=False)
            for value in values:
                if not _is_non_wt(value):
                    continue
                mutated.add(gene)
                parsed = parse_canonical_gene_cell(value)
                if any(_is_truncating(event) for event in parsed.events):
                    truncating.add(gene)
                keys = {
                    key for event in parsed.events
                    if (key := _exact_missense_key(gene, event)) is not None
                }
                patient_support.update(keys)

        selected_keys = tuple(sorted(
            key for key, support in patient_support.items()
            if support >= self.hotspot_min_patient_count
        ))
        recurrent_genes = tuple(sorted({key.split(":", 1)[0] for key in selected_keys}))
        mutated_genes = tuple(sorted(mutated))
        truncating_genes = tuple(sorted(truncating))
        names = (
            *(f"mutated__{gene}" for gene in mutated_genes),
            *(f"truncating__{gene}" for gene in truncating_genes),
            *(f"recurrent_missense__{gene}" for gene in recurrent_genes),
            *SUMMARY_NAMES,
        )
        return FittedCompactClinicalMutationFamily(
            descriptor=FeatureFamilyDescriptor(
                name="compact_clinical_mutation",
                version=self.version,
                fit_scope="fold_train",
                feature_names=tuple(names),
            ),
            gene_columns=self.gene_columns,
            mutated_genes=mutated_genes,
            truncating_genes=truncating_genes,
            recurrent_missense_keys=selected_keys,
            recurrent_missense_support=tuple(
                (key, patient_support[key]) for key in selected_keys
            ),
            recurrent_missense_genes=recurrent_genes,
            hotspot_min_patient_count=self.hotspot_min_patient_count,
        )


def metadata_json(fitted: FittedCompactClinicalMutationFamily) -> str:
    return json.dumps(fitted.metadata(), ensure_ascii=False, sort_keys=True, indent=2)
