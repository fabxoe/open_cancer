"""Stateless sample summaries of frozen Ensembl isoform semantic categories."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import FeatureFamilyDescriptor, KnowledgeProvenance
from open_cancer.hashing import sha256_file
from open_cancer.isoform_semantics import (
    ISOFORM_CATEGORIES,
    TranscriptAnnotation,
    classify_token_semantics,
    load_annotation_index,
)
from open_cancer.mutation_features import parse_mutation_cell


APPROVAL_STATUS = "CONFIRMED_ALLOWED_TRACK_B_B2_SAMPLE_SUMMARY_TEAM_LEAD_EXCEPTION"
FEATURE_NAMES = tuple(
    f"isoform_semantic__{category.lower()}__{view}"
    for category in ISOFORM_CATEGORIES
    for view in ("count", "any")
)


@dataclass(frozen=True)
class FittedIsoformSemanticSummary:
    annotation_index: dict[str, tuple[TranscriptAnnotation, ...]]
    provenance: tuple[KnowledgeProvenance, ...]

    @property
    def descriptor(self) -> FeatureFamilyDescriptor:
        return FeatureFamilyDescriptor(
            name="isoform_semantic_sample_summary",
            version="1.0.0",
            fit_scope="stateless",
            feature_names=FEATURE_NAMES,
            external_knowledge=self.provenance,
        )

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        counts = np.zeros((len(frame), len(ISOFORM_CATEGORIES)), dtype=np.float32)
        category_index = {name: index for index, name in enumerate(ISOFORM_CATEGORIES)}
        genes = [column for column in frame.columns if column not in {"ID", "SUBCLASS"}]
        for gene in genes:
            values = frame[gene].fillna("").astype(str).to_numpy()
            present = np.flatnonzero((values != "") & (values != "WT"))
            annotations = self.annotation_index.get(gene, ())
            for row_index in present:
                parsed = parse_mutation_cell(values[row_index])
                for token in parsed.tokens:
                    category = classify_token_semantics(gene, token.raw, annotations).category
                    counts[row_index, category_index[category]] += 1.0
        output = np.empty((len(frame), len(FEATURE_NAMES)), dtype=np.float32)
        output[:, 0::2] = counts
        output[:, 1::2] = (counts > 0).astype(np.float32)
        return sparse.csr_matrix(output)


@dataclass(frozen=True)
class IsoformSemanticSummaryFamily:
    manifest_path: Path
    annotation_cache_path: Path
    expected_manifest_sha256: str
    expected_annotation_cache_sha256: str

    def fit(
        self, train_frame: pd.DataFrame, target: pd.Series | None = None
    ) -> FittedIsoformSemanticSummary:
        del train_frame, target
        self._verify(self.manifest_path, self.expected_manifest_sha256, "manifest")
        self._verify(
            self.annotation_cache_path,
            self.expected_annotation_cache_sha256,
            "annotation cache",
        )
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if manifest.get("competition_external_annotation_permission") != APPROVAL_STATUS:
            raise ValueError("B2-2 팀장 예외 승인 상태가 manifest와 일치하지 않습니다.")
        if not manifest.get("team_lead_exception_reference"):
            raise ValueError("B2-2 팀장 예외 승인 근거 링크가 없습니다.")
        contract = manifest.get("feature_contract", {})
        if tuple(contract.get("categories", ())) != tuple(ISOFORM_CATEGORIES):
            raise ValueError("B2-2 의미 범주 순서가 사전 고정 계약과 다릅니다.")
        if contract.get("views") != ["count", "any"] or contract.get(
            "output_dimension"
        ) != 12:
            raise ValueError("B2-2 count/any 12개 피처 계약이 올바르지 않습니다.")
        provenance = (
            KnowledgeProvenance.from_file(
                self.manifest_path,
                source="Ensembl isoform semantic manifest",
                version="release-116-b2-summary-v1",
                license="Ensembl data disclaimer",
                uri=manifest["team_lead_exception_reference"],
            ),
            KnowledgeProvenance(
                source="Ensembl competition-gene isoform sequence cache",
                version="release-116",
                license="Ensembl data disclaimer",
                sha256=self.expected_annotation_cache_sha256,
            ),
        )
        return FittedIsoformSemanticSummary(
            annotation_index=load_annotation_index(self.annotation_cache_path),
            provenance=provenance,
        )

    @staticmethod
    def _verify(path: Path, expected: str, label: str) -> None:
        if not path.is_file():
            raise FileNotFoundError(f"B2-2 {label}가 없습니다: {path}")
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError(
                f"B2-2 {label} SHA-256 불일치: expected={expected}, actual={actual}"
            )
