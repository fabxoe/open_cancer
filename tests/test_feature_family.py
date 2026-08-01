from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from scipy import sparse

from open_cancer.feature_family import (
    FeatureContractError,
    FeatureFamilyDescriptor,
    KnowledgeProvenance,
    assert_feature_spec_identity,
    build_feature_spec,
    fit_transform_family_set,
    find_semantically_equivalent_features,
    transform_checked,
)
from open_cancer.validation import validate_json_document


@dataclass
class DummyFittedFamily:
    descriptor: FeatureFamilyDescriptor
    values: np.ndarray

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        return sparse.csr_matrix(self.values[: len(frame)])


def test_family_descriptor_records_fold_scope_and_provenance() -> None:
    provenance = KnowledgeProvenance(
        source="curated-pathways.tsv",
        version="2026-08-01",
        license="CC-BY-4.0",
        sha256="a" * 64,
    )
    descriptor = FeatureFamilyDescriptor(
        name="fixed_pathway",
        version="1.0.0",
        fit_scope="fold_train",
        feature_names=("path_any__rtk_ras", "path_lof__rtk_ras"),
        external_knowledge=(provenance,),
    )

    record = descriptor.to_registry_record()

    assert record["output_dimension"] == 2
    assert record["fit_scope"] == "fold_train"
    assert record["external_knowledge"][0]["sha256"] == "a" * 64


def test_transform_checked_rejects_wrong_dimension() -> None:
    family = DummyFittedFamily(
        FeatureFamilyDescriptor(
            name="bad",
            version="1.0.0",
            fit_scope="stateless",
            feature_names=("one", "two"),
        ),
        np.ones((2, 1)),
    )
    with pytest.raises(FeatureContractError, match="shape"):
        transform_checked(family, pd.DataFrame({"ID": ["A", "B"]}))


def test_feature_spec_binds_base_fold_class_and_family(tmp_path) -> None:
    family = DummyFittedFamily(
        FeatureFamilyDescriptor(
            name="exact_token",
            version="1.0.0",
            fit_scope="fold_train",
            feature_names=("token__TP53_R175H",),
        ),
        np.ones((2, 1)),
    )
    document, digest = build_feature_spec(
        base_feature_spec_sha256="1" * 64,
        families=[family],
        fold_sha256="2" * 64,
        class_labels=("A", "B"),
    )

    assert document["abc_output_dimension"] == 1
    assert document["families"]["exact_token"]["fit_scope"] == "fold_train"
    assert len(digest) == 64
    assert_feature_spec_identity(digest, digest)
    document_path = tmp_path / "feature_spec.json"
    document_path.write_text(json.dumps(document), encoding="utf-8")
    validate_json_document(
        document_path,
        Path(__file__).resolve().parents[1] / "schemas" / "abc_feature_spec.schema.json",
    )


def test_semantic_equivalence_finds_exact_duplicate_without_densifying() -> None:
    reference = sparse.csr_matrix([[1, 0], [0, 2], [1, 0]], dtype=np.float32)
    candidate = sparse.csr_matrix([[0, 1], [2, 0], [0, 1]], dtype=np.float32)

    matches = find_semantically_equivalent_features(
        candidate,
        ["candidate_second", "candidate_first"],
        reference,
        ["reference_first", "reference_second"],
    )

    assert matches == {
        "candidate_second": "reference_second",
        "candidate_first": "reference_first",
    }


def test_exp094_feature_spec_v1_remains_frozen() -> None:
    root = Path(__file__).resolve().parents[1]
    resolved = yaml.safe_load(
        (root / "reproducibility/exp094_feature_spec_v1/config.resolved.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert resolved["features"]["feature_spec_sha256"] == (
        "1fba3a7dac9f9b2a76deb5bec4c1099f650153b82c64d48e476dc1f2f84f3ed3"
    )


def test_family_set_rejects_reference_duplicates() -> None:
    class DummyFamily:
        def fit(self, train_frame, target=None):
            del target
            return DummyFittedFamily(
                FeatureFamilyDescriptor(
                    name="candidate",
                    version="1.0.0",
                    fit_scope="fold_train",
                    feature_names=("candidate_one",),
                ),
                train_frame[["value"]].to_numpy(),
            )

    frame = pd.DataFrame({"value": [1.0, 0.0]})
    with pytest.raises(FeatureContractError, match="의미가 같은"):
        fit_transform_family_set(
            [DummyFamily()],
            fold_train=frame,
            validation=frame,
            test=frame,
            reference_train=sparse.csr_matrix([[1.0], [0.0]]),
            reference_names=["base_one"],
        )
