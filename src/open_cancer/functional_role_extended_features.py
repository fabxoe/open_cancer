"""Functional-role (oncogene/TSG) mutated-gene count family with fold-train gating.

Issue #257 extension of #176: instead of a single raw mutated-gene count per
functional role (`FixedGroupBurdenFamily`, already in `abc_c_features.py`),
this offers four derived views per role -- raw count, fraction of the role's
gene panel, burden-residualized count, and log1p(count) -- and decides which
survive per fold using fold-train-only statistics. This mirrors EXP-229's
finding that splitting a single burden count into several views can add
signal, applied to the functional-role axis instead of pathway axis, with
explicit degeneracy gates because oncogene(29)/TSG(39) panels are much
smaller than a typical pathway gene set.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.abc_c_features import functional_role_burden_family
from open_cancer.feature_family import FeatureFamilyDescriptor, KnowledgeProvenance

CANDIDATE_KINDS: tuple[str, ...] = ("raw", "frac", "resid", "log1p")

# Fold-train-only gate thresholds (Issue #257 design, fixed before execution).
SATURATION_MAX_ZERO_RATE = 0.05  # P(count_raw == 0) below this -> drop raw/log1p
SPARSE_MIN_NONZERO_RATE = 0.01  # P(count_raw > 0) below this -> drop the whole group
DOMINANCE_MAX_SHARE = 0.8  # single-class share among count_raw>0 rows -> drop raw/frac


class FunctionalRoleBurdenExtendedError(ValueError):
    """Raised when the extended functional-role family cannot be fit or applied."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FunctionalRoleBurdenExtendedError(message)


def _total_mutated_gene_count(frame: pd.DataFrame, gene_columns: tuple[str, ...]) -> np.ndarray:
    """Raw (non-log) count of genes with a non-WT call, across the full panel."""
    missing = [gene for gene in gene_columns if gene not in frame.columns]
    _require(not missing, f"입력에 유전자 열이 없습니다: {missing[:5]}")
    non_missing = ~frame.loc[:, list(gene_columns)].isin(["", "WT"])
    return non_missing.sum(axis=1).to_numpy(dtype=np.float64)


def _fit_resid_regression(count_raw: np.ndarray, total: np.ndarray) -> tuple[float, float]:
    """Simple OLS of count_raw ~ total, fold-train only. Falls back on degeneracy."""
    if total.var() <= 0.0 or len(total) < 2:
        return 0.0, float(count_raw.mean()) if len(count_raw) else 0.0
    slope, intercept = np.polyfit(total, count_raw, 1)
    return float(slope), float(intercept)


def _evaluate_gate(
    count_raw_train: np.ndarray, target_train: np.ndarray | None
) -> dict[str, Any]:
    """Decide which of the 4 candidate kinds survive, using fold-train stats only."""
    n = len(count_raw_train)
    p_zero = float(np.mean(count_raw_train == 0)) if n else 1.0
    p_nonzero = 1.0 - p_zero
    nonzero_mask = count_raw_train > 0
    dominance: float | None = None
    dominant_class_index: int | None = None
    if target_train is not None and nonzero_mask.sum() > 0:
        classes, counts = np.unique(np.asarray(target_train)[nonzero_mask], return_counts=True)
        top = int(np.argmax(counts))
        dominance = float(counts[top] / counts.sum())
        dominant_class_index = int(classes[top])

    if p_nonzero < SPARSE_MIN_NONZERO_RATE:
        allowed: frozenset[str] = frozenset()
        gate_triggered = "sparse"
    else:
        allowed = frozenset(CANDIDATE_KINDS)
        gate_triggered = None
        if p_zero < SATURATION_MAX_ZERO_RATE:
            allowed &= {"frac", "resid"}
            gate_triggered = "saturation"
        if dominance is not None and dominance >= DOMINANCE_MAX_SHARE:
            allowed &= {"resid", "log1p"}
            gate_triggered = (
                f"{gate_triggered}+dominance" if gate_triggered else "dominance"
            )

    return {
        "p_zero": p_zero,
        "p_nonzero": p_nonzero,
        "dominance_at_nonzero": dominance,
        "dominant_class_index": dominant_class_index,
        "gate_triggered": gate_triggered,
        "allowed_kinds": sorted(allowed),
    }


@dataclass(frozen=True)
class FittedFunctionalRoleBurdenExtendedFamily:
    """Fold-train-fit gating decisions + resid coefficients, safe to transform any partition."""

    descriptor: FeatureFamilyDescriptor
    gene_columns: tuple[str, ...]
    role_burden_fitted: Any  # FittedFixedGroupBurdenFamily, reused for raw-count parsing
    group_names: tuple[str, ...]  # ("oncogene", "tumor_suppressor")
    group_sizes: dict[str, int]
    allowed_kinds: dict[str, tuple[str, ...]]
    resid_coefficients: dict[str, tuple[float, float]]
    gate_summary: dict[str, dict[str, Any]]

    def _raw_counts(self, frame: pd.DataFrame) -> dict[str, np.ndarray]:
        role_matrix = self.role_burden_fitted.transform(frame).toarray()
        role_names = self.role_burden_fitted.descriptor.feature_names
        return {
            group: role_matrix[:, role_names.index(f"sample__role_{group}__mutated_gene_count")]
            for group in self.group_names
        }

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        total = _total_mutated_gene_count(frame, self.gene_columns)
        raw_counts = self._raw_counts(frame)
        columns: list[np.ndarray] = []
        for group in self.group_names:
            kinds = self.allowed_kinds[group]
            if not kinds:
                continue
            raw = raw_counts[group]
            group_size = self.group_sizes[group]
            slope, intercept = self.resid_coefficients[group]
            values_by_kind = {
                "raw": raw,
                "frac": raw / group_size if group_size else np.zeros_like(raw),
                "resid": raw - (slope * total + intercept),
                "log1p": np.log1p(raw),
            }
            for kind in kinds:
                columns.append(values_by_kind[kind])
        if not columns:
            return sparse.csr_matrix((len(frame), 0), dtype=np.float32)
        matrix = np.stack(columns, axis=1).astype(np.float32)
        return sparse.csr_matrix(matrix)


@dataclass(frozen=True)
class FunctionalRoleBurdenExtendedFamily:
    """Factory: fold-train-only fit of gated oncogene/TSG mutated-gene count views."""

    gene_columns: tuple[str, ...]
    knowledge_path: Path
    version: str = "1.0.0"

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | np.ndarray | None = None,
    ) -> FittedFunctionalRoleBurdenExtendedFamily:
        _require(target is not None, "functional_role_burden_extended은 fold-train target이 필요합니다.")
        role_family = functional_role_burden_family(self.gene_columns, self.knowledge_path)
        role_fitted = role_family.fit(train_frame.iloc[:1] if len(train_frame) else train_frame)
        group_names = tuple(
            name
            for name in ("oncogene", "tumor_suppressor")
            if f"sample__role_{name}__mutated_gene_count" in role_fitted.descriptor.feature_names
        )
        _require(len(group_names) == 2, "oncogene/tumor_suppressor functional_roles가 모두 필요합니다.")
        group_sizes = {name: len(role_fitted.intersections[name]) for name in group_names}

        role_matrix_train = role_fitted.transform(train_frame).toarray()
        role_names = role_fitted.descriptor.feature_names
        target_array = np.asarray(target)

        allowed_kinds: dict[str, tuple[str, ...]] = {}
        resid_coefficients: dict[str, tuple[float, float]] = {}
        gate_summary: dict[str, dict[str, Any]] = {}
        total_train = _total_mutated_gene_count(train_frame, self.gene_columns)

        for group in group_names:
            raw_train = role_matrix_train[:, role_names.index(f"sample__role_{group}__mutated_gene_count")]
            gate = _evaluate_gate(raw_train, target_array)
            allowed_kinds[group] = tuple(k for k in CANDIDATE_KINDS if k in gate["allowed_kinds"])
            resid_coefficients[group] = _fit_resid_regression(raw_train, total_train)
            gate_summary[group] = gate

        _require(
            any(allowed_kinds[group] for group in group_names),
            "모든 functional_role 그룹이 게이트에서 제외됐습니다(표본 확인 필요).",
        )

        feature_names = tuple(
            f"sample__role_{group}__count_{kind}"
            for group in group_names
            for kind in allowed_kinds[group]
        )

        document_text = (self.knowledge_path).read_text(encoding="utf-8")
        import json

        document = json.loads(document_text)
        provenance = KnowledgeProvenance.from_file(
            self.knowledge_path,
            source=str(document["source"]),
            version=str(document["version"]),
            license=str(document["license"]),
            uri=str(document.get("source_url", "")) or None,
        )

        descriptor = FeatureFamilyDescriptor(
            name="functional_role_burden_extended",
            version=self.version,
            fit_scope="fold_train",
            feature_names=feature_names,
            external_knowledge=(provenance,),
        )
        return FittedFunctionalRoleBurdenExtendedFamily(
            descriptor=descriptor,
            gene_columns=self.gene_columns,
            role_burden_fitted=role_fitted,
            group_names=group_names,
            group_sizes=group_sizes,
            allowed_kinds=allowed_kinds,
            resid_coefficients=resid_coefficients,
            gate_summary=gate_summary,
        )


def functional_role_burden_extended_family(
    gene_columns: tuple[str, ...], knowledge_path: Path
) -> FunctionalRoleBurdenExtendedFamily:
    return FunctionalRoleBurdenExtendedFamily(gene_columns, knowledge_path)
