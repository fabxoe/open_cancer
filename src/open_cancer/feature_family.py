"""Common contracts for independently switchable ABC feature families."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.hashing import sha256_file, sha256_lines

FitScope = Literal["stateless", "fold_train"]

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class FeatureContractError(ValueError):
    """Raised when a feature family violates the shared ABC contract."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FeatureContractError(message)


@dataclass(frozen=True)
class KnowledgeProvenance:
    """Immutable provenance for an external list or rule used by a family."""

    source: str
    version: str
    license: str
    sha256: str
    uri: str | None = None

    def __post_init__(self) -> None:
        _require(bool(self.source.strip()), "외부 지식 source가 필요합니다.")
        _require(bool(self.version.strip()), "외부 지식 version이 필요합니다.")
        _require(bool(self.license.strip()), "외부 지식 license가 필요합니다.")
        _require(
            _SHA256_PATTERN.fullmatch(self.sha256) is not None,
            "외부 지식 SHA-256은 64자리 소문자 16진수여야 합니다.",
        )

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        source: str,
        version: str,
        license: str,
        uri: str | None = None,
    ) -> KnowledgeProvenance:
        """Create provenance from the exact bytes of a committed knowledge file."""
        return cls(
            source=source,
            version=version,
            license=license,
            sha256=sha256_file(path),
            uri=uri,
        )

    def to_dict(self) -> dict[str, str | None]:
        return {
            "source": self.source,
            "version": self.version,
            "license": self.license,
            "sha256": self.sha256,
            "uri": self.uri,
        }


@dataclass(frozen=True)
class FeatureFamilyDescriptor:
    """Resolved identity and output schema of one fitted feature family."""

    name: str
    version: str
    fit_scope: FitScope
    feature_names: tuple[str, ...]
    external_knowledge: tuple[KnowledgeProvenance, ...] = ()

    def __post_init__(self) -> None:
        _require(bool(self.name.strip()), "family 이름이 필요합니다.")
        _require(bool(self.version.strip()), "family 버전이 필요합니다.")
        _require(self.fit_scope in {"stateless", "fold_train"}, "fit_scope가 올바르지 않습니다.")
        _require(bool(self.feature_names), "family 출력 피처가 하나 이상 필요합니다.")
        _require(
            len(self.feature_names) == len(set(self.feature_names)),
            f"{self.name}: feature 이름이 중복됩니다.",
        )
        _require(
            all(name.strip() for name in self.feature_names),
            f"{self.name}: 빈 feature 이름을 사용할 수 없습니다.",
        )

    @property
    def output_dimension(self) -> int:
        return len(self.feature_names)

    @property
    def feature_names_sha256(self) -> str:
        return sha256_lines(self.feature_names)

    def to_registry_record(self, *, enabled: bool = True) -> dict[str, Any]:
        return {
            "definition_version": self.version,
            "enabled": enabled,
            "output_dimension": self.output_dimension,
            "feature_names_sha256": self.feature_names_sha256,
            "fit_scope": self.fit_scope,
            "external_knowledge": [item.to_dict() for item in self.external_knowledge] or None,
        }


@runtime_checkable
class FittedFeatureFamily(Protocol):
    """A family fitted on one fold-train partition and safe to transform others."""

    @property
    def descriptor(self) -> FeatureFamilyDescriptor: ...

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix: ...


@runtime_checkable
class FeatureFamily(Protocol):
    """Factory interface used by ABC feature families."""

    def fit(
        self,
        train_frame: pd.DataFrame,
        target: pd.Series | None = None,
    ) -> FittedFeatureFamily: ...


def transform_checked(
    family: FittedFeatureFamily,
    frame: pd.DataFrame,
) -> sparse.csr_matrix:
    """Transform a partition and enforce row and output-dimension contracts."""
    matrix = sparse.csr_matrix(family.transform(frame), dtype=np.float32)
    _require(
        matrix.shape == (len(frame), family.descriptor.output_dimension),
        (
            f"{family.descriptor.name}: transform shape {matrix.shape}가 "
            f"예상 {(len(frame), family.descriptor.output_dimension)}와 다릅니다."
        ),
    )
    _require(np.isfinite(matrix.data).all(), f"{family.descriptor.name}: NaN 또는 무한대가 있습니다.")
    return matrix


def build_family_registry(
    families: list[FittedFeatureFamily] | tuple[FittedFeatureFamily, ...],
) -> dict[str, dict[str, Any]]:
    """Build a deterministic registry and reject colliding family identities."""
    names = [family.descriptor.name for family in families]
    _require(len(names) == len(set(names)), "family 이름이 중복됩니다.")
    return {
        family.descriptor.name: family.descriptor.to_registry_record()
        for family in sorted(families, key=lambda item: item.descriptor.name)
    }


def build_feature_spec(
    *,
    base_feature_spec_sha256: str,
    families: list[FittedFeatureFamily] | tuple[FittedFeatureFamily, ...],
    fold_sha256: str,
    class_labels: tuple[str, ...],
) -> tuple[dict[str, Any], str]:
    """Resolve the immutable feature/fold/class contract for one fitted fold."""
    for label, value in (
        ("base Feature Spec", base_feature_spec_sha256),
        ("fold", fold_sha256),
    ):
        _require(
            _SHA256_PATTERN.fullmatch(value) is not None,
            f"{label} SHA-256이 올바르지 않습니다.",
        )
    _require(bool(class_labels), "고정 클래스 순서가 필요합니다.")
    _require(len(class_labels) == len(set(class_labels)), "고정 클래스가 중복됩니다.")

    registry = build_family_registry(families)
    feature_names = tuple(
        feature_name
        for family in families
        for feature_name in family.descriptor.feature_names
    )
    _require(
        len(feature_names) == len(set(feature_names)),
        "서로 다른 family 사이에 feature 이름이 중복됩니다.",
    )
    document = {
        "base_feature_spec_sha256": base_feature_spec_sha256,
        "fold_sha256": fold_sha256,
        "class_labels": list(class_labels),
        "class_order_sha256": sha256_lines(class_labels),
        "abc_feature_names_sha256": sha256_lines(feature_names),
        "abc_output_dimension": len(feature_names),
        "families": registry,
    }
    digest = sha256_lines([json.dumps(document, ensure_ascii=False, sort_keys=True)])
    return document, digest


def assert_feature_spec_identity(actual_sha256: str, expected_sha256: str) -> None:
    """Fail fast when a frozen Feature Spec changes unexpectedly."""
    _require(
        actual_sha256 == expected_sha256,
        f"Feature Spec SHA-256이 변경됐습니다: {actual_sha256} != {expected_sha256}",
    )


def _column_fingerprint(matrix: sparse.csc_matrix, column: int) -> bytes:
    start, end = matrix.indptr[column], matrix.indptr[column + 1]
    indices = np.asarray(matrix.indices[start:end], dtype=np.int64)
    values = np.asarray(matrix.data[start:end], dtype=np.float64)
    digest = hashlib.sha256()
    digest.update(indices.tobytes())
    digest.update(values.tobytes())
    return digest.digest()


def find_semantically_equivalent_features(
    candidate_matrix: sparse.spmatrix | np.ndarray,
    candidate_names: tuple[str, ...] | list[str],
    reference_matrix: sparse.spmatrix | np.ndarray,
    reference_names: tuple[str, ...] | list[str],
) -> dict[str, str]:
    """Find byte-equivalent columns so a new family cannot silently duplicate v1."""
    candidate = sparse.csc_matrix(candidate_matrix, dtype=np.float64)
    reference = sparse.csc_matrix(reference_matrix, dtype=np.float64)
    candidate.eliminate_zeros()
    reference.eliminate_zeros()
    candidate.sort_indices()
    reference.sort_indices()
    _require(candidate.shape[0] == reference.shape[0], "비교할 feature matrix의 행 수가 다릅니다.")
    _require(candidate.shape[1] == len(candidate_names), "candidate 이름 수와 열 수가 다릅니다.")
    _require(reference.shape[1] == len(reference_names), "reference 이름 수와 열 수가 다릅니다.")

    reference_by_hash: dict[bytes, list[int]] = {}
    for index in range(reference.shape[1]):
        reference_by_hash.setdefault(_column_fingerprint(reference, index), []).append(index)

    matches: dict[str, str] = {}
    for candidate_index, candidate_name in enumerate(candidate_names):
        fingerprint = _column_fingerprint(candidate, candidate_index)
        for reference_index in reference_by_hash.get(fingerprint, []):
            difference = candidate[:, candidate_index] != reference[:, reference_index]
            if difference.nnz == 0:
                matches[candidate_name] = reference_names[reference_index]
                break
    return matches
