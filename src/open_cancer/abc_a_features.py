"""ABC-Stack A families: recurrent exact tokens and amino-acid changes."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FeatureFamilyDescriptor, KnowledgeProvenance
from open_cancer.mutation_features import parse_mutation_token

AminoAcidChange = Literal[
    "conservative",
    "nonconservative",
    "stop_gain",
    "not_simple_substitution",
]

AMINO_ACID_FEATURES = (
    "sample__aa_conservative_substitution_count",
    "sample__aa_nonconservative_substitution_count",
    "sample__aa_charge_change_count",
    "sample__aa_polarity_change_count",
)


class ABCFeatureError(ValueError):
    """Raised when an ABC A-family configuration or input is invalid."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ABCFeatureError(message)


def _tokens(cell: Any) -> tuple[str, ...]:
    if not isinstance(cell, str) or cell == "" or cell == "WT":
        return ()
    return tuple(token for token in cell.split() if token and token != "WT")


def _validate_gene_columns(frame: pd.DataFrame, gene_columns: tuple[str, ...]) -> None:
    _require(bool(gene_columns), "유전자 열이 하나 이상 필요합니다.")
    missing = [gene for gene in gene_columns if gene not in frame.columns]
    _require(not missing, f"입력에 유전자 열이 없습니다: {missing[:5]}")


@dataclass(frozen=True)
class FittedExactTokenFamily:
    """Vocabulary learned only from the outer fold-train partition."""

    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    vocabulary: tuple[tuple[str, str], ...]
    support: tuple[int, ...]

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        _validate_gene_columns(frame, self.gene_columns)
        index = {item: column for column, item in enumerate(self.vocabulary)}
        rows: list[int] = []
        columns: list[int] = []
        for row_index, row in enumerate(frame.loc[:, self.gene_columns].itertuples(index=False, name=None)):
            observed: set[int] = set()
            for gene, cell in zip(self.gene_columns, row, strict=True):
                for token in _tokens(cell):
                    column = index.get((gene, token))
                    if column is not None:
                        observed.add(column)
            for column in sorted(observed):
                rows.append(row_index)
                columns.append(column)
        values = np.ones(len(rows), dtype=np.float32)
        return sparse.csr_matrix(
            (values, (rows, columns)),
            shape=(len(frame), len(self.vocabulary)),
            dtype=np.float32,
        )


@dataclass(frozen=True)
class RecurrentExactTokenFamily:
    """Select deterministic recurrent ``(gene, raw token)`` events."""

    gene_columns: tuple[str, ...]
    min_support: int = 5
    max_features: int = 512
    version: str = "1.0.0"

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedExactTokenFamily:
        del target
        _validate_gene_columns(train_frame, self.gene_columns)
        _require(self.min_support >= 1, "min_support는 1 이상이어야 합니다.")
        _require(self.max_features >= 1, "max_features는 1 이상이어야 합니다.")
        counts: Counter[tuple[str, str]] = Counter()
        for row in train_frame.loc[:, self.gene_columns].itertuples(index=False, name=None):
            row_events: set[tuple[str, str]] = set()
            for gene, cell in zip(self.gene_columns, row, strict=True):
                row_events.update((gene, token) for token in _tokens(cell))
            counts.update(row_events)
        selected = tuple(
            item
            for item, count in sorted(
                counts.items(),
                key=lambda entry: (-entry[1], entry[0][0], entry[0][1]),
            )
            if count >= self.min_support
        )[: self.max_features]
        _require(bool(selected), "support 조건을 만족하는 exact-token이 없습니다.")
        supports = tuple(counts[item] for item in selected)
        descriptor = FeatureFamilyDescriptor(
            name="recurrent_exact_token",
            version=self.version,
            fit_scope="fold_train",
            feature_names=tuple(
                f"exact_token__{gene}__{token}" for gene, token in selected
            ),
        )
        return FittedExactTokenFamily(
            descriptor=descriptor,
            gene_columns=self.gene_columns,
            vocabulary=selected,
            support=supports,
        )


def load_amino_acid_properties(path: str | Path) -> dict[str, dict[str, str]]:
    """Load and validate the committed 20-residue property rule."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    properties = document.get("amino_acids")
    _require(isinstance(properties, dict), "amino_acids 객체가 필요합니다.")
    expected = set("ACDEFGHIKLMNPQRSTVWY")
    _require(set(properties) == expected, "표준 20개 아미노산 물성표가 필요합니다.")
    for amino_acid, values in properties.items():
        _require(
            isinstance(values, dict)
            and all(isinstance(values.get(key), str) for key in ("group", "charge", "polarity")),
            f"{amino_acid}: group/charge/polarity가 필요합니다.",
        )
    return properties


def classify_amino_acid_change(
    token: str,
    properties: dict[str, dict[str, str]],
) -> AminoAcidChange:
    """Classify a simple substitution using only explicit token residues."""
    parsed = parse_mutation_token(token)
    reference = parsed.reference_amino_acid
    alternate = parsed.alternate_amino_acid
    if alternate == "*" and reference in properties:
        return "stop_gain"
    if (
        parsed.token_shape != "substitution"
        or reference not in properties
        or alternate not in properties
        or reference == alternate
    ):
        return "not_simple_substitution"
    if properties[reference]["group"] == properties[alternate]["group"]:
        return "conservative"
    return "nonconservative"


@dataclass(frozen=True)
class FittedAminoAcidChangeFamily:
    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    properties: dict[str, dict[str, str]]

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        _validate_gene_columns(frame, self.gene_columns)
        matrix = np.zeros((len(frame), len(AMINO_ACID_FEATURES)), dtype=np.float32)
        for row_index, row in enumerate(frame.loc[:, self.gene_columns].itertuples(index=False, name=None)):
            for cell in row:
                for token in _tokens(cell):
                    parsed = parse_mutation_token(token)
                    reference = parsed.reference_amino_acid
                    alternate = parsed.alternate_amino_acid
                    change = classify_amino_acid_change(token, self.properties)
                    if change == "conservative":
                        matrix[row_index, 0] += 1
                    elif change == "nonconservative":
                        matrix[row_index, 1] += 1
                    else:
                        continue
                    if self.properties[reference]["charge"] != self.properties[alternate]["charge"]:
                        matrix[row_index, 2] += 1
                    if self.properties[reference]["polarity"] != self.properties[alternate]["polarity"]:
                        matrix[row_index, 3] += 1
        return sparse.csr_matrix(matrix)


@dataclass(frozen=True)
class AminoAcidChangeFamily:
    """Stateless sample-level amino-acid property transition counts."""

    gene_columns: tuple[str, ...]
    property_path: Path
    version: str = "1.0.0"

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedAminoAcidChangeFamily:
        del target
        _validate_gene_columns(train_frame, self.gene_columns)
        document = json.loads(self.property_path.read_text(encoding="utf-8"))
        properties = load_amino_acid_properties(self.property_path)
        provenance = KnowledgeProvenance.from_file(
            self.property_path,
            source=str(document["source"]),
            version=str(document["version"]),
            license=str(document["license"]),
        )
        descriptor = FeatureFamilyDescriptor(
            name="amino_acid_change",
            version=self.version,
            fit_scope="stateless",
            feature_names=AMINO_ACID_FEATURES,
            external_knowledge=(provenance,),
        )
        return FittedAminoAcidChangeFamily(
            descriptor=descriptor,
            gene_columns=self.gene_columns,
            properties=properties,
        )
