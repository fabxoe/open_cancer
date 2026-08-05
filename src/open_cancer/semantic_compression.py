"""Fold-safe semantic compression and dense SAINT dataset adapters.

The compressor is deliberately target independent.  It ranks parser-native
features by stable support across deterministic inner training partitions of
one outer training fold.  Validation and test matrices are transform-only and
therefore cannot influence the selected columns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence

import numpy as np
from scipy import sparse
from sklearn.model_selection import KFold

from open_cancer.hashing import sha256_lines


ColumnKind = Literal["binary", "continuous"]

SAMPLE_BURDEN_CORE = (
    "sample__mutated_gene_count",
    "sample__total_variant_count",
    "sample__multi_variant_gene_count",
    "sample__missing_gene_count",
)


class SemanticCompressionError(ValueError):
    """Raised when the semantic compression contract is violated."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SemanticCompressionError(message)


def infer_semantic_family(feature_name: str) -> str:
    """Infer an auditable family label from parser-native feature names."""

    name = str(feature_name)
    marker = "__native_v3_"
    if marker in name:
        consequence = name.split(marker, maxsplit=1)[1]
        for suffix in ("_token_count", "_any"):
            if consequence.endswith(suffix):
                consequence = consequence[: -len(suffix)]
                break
        return f"native_v3_{consequence}"
    if name.startswith("sample__"):
        return "sample_aggregate"
    if name.startswith("gene__"):
        return "gene_event"
    return name.split("__", maxsplit=1)[0] or "unclassified"


def infer_column_kind(feature_name: str) -> ColumnKind:
    """Infer whether SAINT should treat a column as binary or continuous."""

    name = str(feature_name)
    binary_suffixes = ("_any", "_indicator", "__mutated", "_presence")
    if name.endswith(binary_suffixes):
        return "binary"
    return "continuous"


def is_semantic_core(feature_name: str) -> bool:
    """Keep parser-native sample summaries before ranked gene-event columns."""

    name = str(feature_name)
    return name in SAMPLE_BURDEN_CORE or name.startswith("sample__native_v3_")


def is_semantic_gene_event(feature_name: str) -> bool:
    """Return whether a column belongs to the parser-v4 native gene-event block.

    Feature caches may also contain the compatibility mutation/missing block.
    Those columns are intentionally excluded here so that this selector cannot
    silently turn into another compatibility-model feature selector.
    """

    name = str(feature_name)
    return name.startswith("gene__") and "__native_v3_" in name


@dataclass(frozen=True)
class SemanticFeatureRecord:
    source_index: int
    name: str
    family: str
    column_kind: ColumnKind
    is_core: bool
    outer_support: int
    outer_prevalence: float
    inner_supports: tuple[int, ...]
    inner_prevalences: tuple[float, ...]
    stable_fold_count: int
    mean_rank: float

    def to_dict(self, *, output_index: int) -> dict[str, Any]:
        return {
            "output_index": int(output_index),
            "source_index": int(self.source_index),
            "name": self.name,
            "family": self.family,
            "column_kind": self.column_kind,
            "is_core": bool(self.is_core),
            "outer_support": int(self.outer_support),
            "outer_prevalence": float(self.outer_prevalence),
            "inner_supports": [int(value) for value in self.inner_supports],
            "inner_prevalences": [
                float(value) for value in self.inner_prevalences
            ],
            "stable_fold_count": int(self.stable_fold_count),
            "mean_rank": float(self.mean_rank),
        }


@dataclass(frozen=True)
class SemanticSelectionManifest:
    version: str
    fold: int
    fit_scope: str
    fit_rows: int
    input_dimension: int
    output_dimension: int
    min_support: int
    inner_splits: int
    seed: int
    input_feature_names_sha256: str
    selected_feature_names_sha256: str
    selected_source_indices_sha256: str
    selected_features: tuple[SemanticFeatureRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "fold": int(self.fold),
            "fit_scope": self.fit_scope,
            "fit_rows": int(self.fit_rows),
            "input_dimension": int(self.input_dimension),
            "output_dimension": int(self.output_dimension),
            "min_support": int(self.min_support),
            "inner_splits": int(self.inner_splits),
            "seed": int(self.seed),
            "input_feature_names_sha256": self.input_feature_names_sha256,
            "selected_feature_names_sha256": self.selected_feature_names_sha256,
            "selected_source_indices_sha256": (
                self.selected_source_indices_sha256
            ),
            "selection_policy": {
                "target_used": False,
                "validation_used": False,
                "test_used": False,
                "ranking": [
                    "semantic_core_first",
                    "stable_fold_count_desc",
                    "mean_inner_rank_asc",
                    "minimum_inner_support_desc",
                    "outer_support_desc",
                    "family_asc",
                    "feature_name_asc",
                ],
            },
            "selected_features": [
                feature.to_dict(output_index=index)
                for index, feature in enumerate(self.selected_features)
            ],
        }


@dataclass(frozen=True)
class SaintDataset:
    values: np.ndarray
    feature_names: tuple[str, ...]
    feature_families: tuple[str, ...]
    binary_indices: tuple[int, ...]
    continuous_indices: tuple[int, ...]
    estimated_dense_bytes: int


@dataclass(frozen=True)
class FittedSemanticCompressor:
    version: str
    fold: int
    fit_rows: int
    input_feature_names: tuple[str, ...]
    target_dimensions: tuple[int, ...]
    min_support: int
    inner_splits: int
    seed: int
    ranked_features: tuple[SemanticFeatureRecord, ...]

    def _records(self, dimension: int) -> tuple[SemanticFeatureRecord, ...]:
        _require(
            dimension in self.target_dimensions,
            f"지원하지 않는 semantic output dimension: {dimension}",
        )
        _require(
            len(self.ranked_features) >= dimension,
            "선택 가능한 semantic feature가 목표 차원보다 적습니다.",
        )
        return self.ranked_features[:dimension]

    def selected_indices(self, dimension: int) -> np.ndarray:
        return np.asarray(
            [record.source_index for record in self._records(dimension)],
            dtype=np.int64,
        )

    def transform(
        self, features: sparse.spmatrix, *, dimension: int
    ) -> sparse.csr_matrix:
        matrix = sparse.csr_matrix(features, dtype=np.float32)
        _require(
            matrix.shape[1] == len(self.input_feature_names),
            "transform feature dimension이 fit schema와 다릅니다.",
        )
        return sparse.csr_matrix(
            matrix[:, self.selected_indices(dimension)], dtype=np.float32
        )

    def manifest(self, dimension: int) -> SemanticSelectionManifest:
        records = self._records(dimension)
        selected_names = tuple(record.name for record in records)
        selected_indices = tuple(record.source_index for record in records)
        return SemanticSelectionManifest(
            version=self.version,
            fold=self.fold,
            fit_scope="outer_train_only_target_independent_stable_support",
            fit_rows=self.fit_rows,
            input_dimension=len(self.input_feature_names),
            output_dimension=dimension,
            min_support=self.min_support,
            inner_splits=self.inner_splits,
            seed=self.seed,
            input_feature_names_sha256=sha256_lines(self.input_feature_names),
            selected_feature_names_sha256=sha256_lines(selected_names),
            selected_source_indices_sha256=sha256_lines(
                str(index) for index in selected_indices
            ),
            selected_features=records,
        )

    def build_saint_dataset(
        self,
        features: sparse.spmatrix,
        *,
        dimension: int,
        max_dense_bytes: int = 512 * 1024 * 1024,
    ) -> SaintDataset:
        selected = self.transform(features, dimension=dimension)
        estimated_bytes = int(selected.shape[0] * selected.shape[1] * 4)
        _require(
            estimated_bytes <= max_dense_bytes,
            "SAINT dense materialization 예상 크기가 제한을 초과합니다: "
            f"{estimated_bytes} > {max_dense_bytes}",
        )
        records = self._records(dimension)
        values = np.asarray(selected.toarray(), dtype=np.float32)
        _require(np.isfinite(values).all(), "SAINT 입력에 NaN 또는 Inf가 있습니다.")
        binary_indices = tuple(
            index
            for index, record in enumerate(records)
            if record.column_kind == "binary"
        )
        continuous_indices = tuple(
            index
            for index, record in enumerate(records)
            if record.column_kind == "continuous"
        )
        return SaintDataset(
            values=values,
            feature_names=tuple(record.name for record in records),
            feature_families=tuple(record.family for record in records),
            binary_indices=binary_indices,
            continuous_indices=continuous_indices,
            estimated_dense_bytes=estimated_bytes,
        )


@dataclass(frozen=True)
class FoldSafeSemanticCompressor:
    target_dimensions: tuple[int, ...] = (128, 256, 512)
    min_support: int = 5
    inner_splits: int = 3
    seed: int = 42
    version: str = "1.0.0"

    def fit(
        self,
        outer_train_features: sparse.spmatrix,
        feature_names: Sequence[str],
        *,
        fold: int,
        feature_families: Sequence[str] | None = None,
        column_kinds: Sequence[ColumnKind] | None = None,
    ) -> FittedSemanticCompressor:
        matrix = sparse.csr_matrix(outer_train_features, dtype=np.float32)
        names = tuple(str(name) for name in feature_names)
        _require(matrix.shape[0] >= self.inner_splits, "inner split보다 학습 행이 적습니다.")
        _require(matrix.shape[1] == len(names), "feature matrix와 이름 수가 다릅니다.")
        _require(len(set(names)) == len(names), "feature 이름은 중복될 수 없습니다.")
        _require(self.min_support >= 1, "min_support는 1 이상이어야 합니다.")
        dimensions = tuple(sorted(set(int(value) for value in self.target_dimensions)))
        _require(dimensions and dimensions[0] >= 1, "target dimension은 양수여야 합니다.")

        if feature_families is None:
            families = tuple(infer_semantic_family(name) for name in names)
        else:
            families = tuple(str(value) for value in feature_families)
            _require(len(families) == len(names), "feature family 수가 다릅니다.")
        if column_kinds is None:
            kinds = tuple(infer_column_kind(name) for name in names)
        else:
            kinds = tuple(column_kinds)
            _require(len(kinds) == len(names), "column kind 수가 다릅니다.")
            _require(
                all(value in {"binary", "continuous"} for value in kinds),
                "column kind는 binary 또는 continuous여야 합니다.",
            )

        outer_support = np.asarray(matrix.getnnz(axis=0)).ravel().astype(np.int64)
        core_indices = [index for index, name in enumerate(names) if is_semantic_core(name)]
        core_index_set = set(core_indices)
        candidate_indices = [
            index
            for index in range(len(names))
            if index not in core_index_set
            and is_semantic_gene_event(names[index])
            and outer_support[index] >= self.min_support
        ]
        _require(
            len(core_indices) <= dimensions[0],
            "semantic core가 최소 목표 차원보다 큽니다.",
        )
        _require(
            len(core_indices) + len(candidate_indices) >= dimensions[-1],
            "min_support를 통과한 feature가 최대 목표 차원보다 적습니다.",
        )

        inner_supports: dict[int, list[int]] = {
            index: [] for index in (*core_indices, *candidate_indices)
        }
        inner_prevalences: dict[int, list[float]] = {
            index: [] for index in (*core_indices, *candidate_indices)
        }
        inner_ranks: dict[int, list[int]] = {index: [] for index in candidate_indices}
        splitter = KFold(
            n_splits=self.inner_splits,
            shuffle=True,
            random_state=self.seed + int(fold),
        )
        all_rows = np.arange(matrix.shape[0], dtype=np.int64)
        for inner_train, _ in splitter.split(all_rows):
            support = np.asarray(matrix[inner_train].getnnz(axis=0)).ravel().astype(np.int64)
            row_count = len(inner_train)
            for index in inner_supports:
                value = int(support[index])
                inner_supports[index].append(value)
                inner_prevalences[index].append(value / row_count)
            ordered = sorted(
                candidate_indices,
                key=lambda index: (
                    -int(support[index]),
                    families[index],
                    names[index],
                ),
            )
            for rank, index in enumerate(ordered, start=1):
                inner_ranks[index].append(rank)

        def record(index: int, *, core: bool) -> SemanticFeatureRecord:
            supports = tuple(inner_supports[index])
            prevalences = tuple(inner_prevalences[index])
            ranks = inner_ranks.get(index, [0] * self.inner_splits)
            return SemanticFeatureRecord(
                source_index=index,
                name=names[index],
                family=families[index],
                column_kind=kinds[index],
                is_core=core,
                outer_support=int(outer_support[index]),
                outer_prevalence=float(outer_support[index] / matrix.shape[0]),
                inner_supports=supports,
                inner_prevalences=prevalences,
                stable_fold_count=sum(value >= self.min_support for value in supports),
                mean_rank=float(np.mean(ranks)),
            )

        core_records = tuple(record(index, core=True) for index in core_indices)
        candidate_records = [record(index, core=False) for index in candidate_indices]
        candidate_records.sort(
            key=lambda value: (
                -value.stable_fold_count,
                value.mean_rank,
                -min(value.inner_supports),
                -value.outer_support,
                value.family,
                value.name,
            )
        )
        ranked = (*core_records, *candidate_records)
        return FittedSemanticCompressor(
            version=self.version,
            fold=int(fold),
            fit_rows=matrix.shape[0],
            input_feature_names=names,
            target_dimensions=dimensions,
            min_support=self.min_support,
            inner_splits=self.inner_splits,
            seed=self.seed,
            ranked_features=tuple(ranked),
        )
