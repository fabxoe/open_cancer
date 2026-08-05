"""Controlled legacy/compatibility/native feature adapters for parser N4."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

import pandas as pd
from scipy import sparse

from open_cancer.feature_family import (
    FeatureFamilyDescriptor,
    FoldFeatureBundle,
    fit_transform_family_set,
)
from open_cancer.mutation_features import MUTATION_TYPES
from open_cancer.parser_compatibility_features import ParserCompatibilityFamily
from open_cancer.parser_native_features import (
    FittedParserNativeSemanticFamily,
    ParserNativeSemanticFamily,
    native_semantic_contract_record,
)


ParserRepresentation = Literal["legacy", "compatibility", "native", "hybrid"]


def validate_controlled_parser_baseline_config(config: dict) -> ParserRepresentation:
    """Reject any setting that would confound the N4 three-arm comparison."""

    representation = str(config.get("parser_baseline", {}).get("representation", ""))
    if representation not in {"legacy", "compatibility", "native", "hybrid"}:
        raise ValueError(f"지원하지 않는 parser baseline arm: {representation}")
    if config.get("hotspots", {}).get("table") != "none":
        raise ValueError("parser baseline은 hotspot을 사용하지 않습니다.")
    features = config.get("features", {})
    if features.get("residue_position", {}).get("enabled", False):
        raise ValueError("parser baseline은 residue-position을 사용하지 않습니다.")
    if features.get("robust_aggregates", []):
        raise ValueError("parser baseline은 추가 aggregate를 사용하지 않습니다.")
    training = config.get("training", {})
    if training.get("checkpoint_selection") != "macro_f1_validation":
        raise ValueError("parser baseline checkpoint는 validation Macro F1이어야 합니다.")
    if training.get("balanced_sample_weight") is not True:
        raise ValueError("parser baseline은 balanced sample weight를 고정합니다.")
    return representation  # type: ignore[return-value]


def legacy_five_family_feature_names(
    gene_columns: tuple[str, ...],
) -> tuple[str, ...]:
    """Return the historical lexical columns replaced by C/N adapters."""

    return (
        *(f"sample__{family}_count" for family in MUTATION_TYPES),
        *(
            f"{gene}__{family}"
            for gene in gene_columns
            for family in MUTATION_TYPES
        ),
    )


class ParserBaselineFoldBuilder:
    """Build one stateless parser projection on aligned raw partitions."""

    def __init__(
        self,
        *,
        representation: ParserRepresentation,
        train_path: Path,
        test_path: Path,
    ) -> None:
        if representation == "legacy":
            raise ValueError("legacy arm은 fold feature builder를 사용하지 않습니다.")
        self.representation = representation
        self.train = pd.read_csv(train_path, dtype=str, keep_default_na=False)
        self.test = pd.read_csv(test_path, dtype=str, keep_default_na=False)
        self.gene_columns = tuple(self.train.columns[2:])
        if self.gene_columns != tuple(self.test.columns[1:]):
            raise ValueError("train/test 유전자 열 이름 또는 순서가 다릅니다.")
        self.names_to_drop = legacy_five_family_feature_names(self.gene_columns)

    def __call__(
        self,
        *,
        fold: int,
        train_indices,
        valid_indices,
        base_train,
        base_validation,
        base_test,
        base_feature_names,
        target,
    ) -> FoldFeatureBundle:
        del fold, base_validation, base_test, base_feature_names
        if self.representation == "compatibility":
            families = (ParserCompatibilityFamily(self.gene_columns),)
        elif self.representation == "native":
            families = (ParserNativeSemanticFamily(self.gene_columns),)
        else:
            families = (
                ParserCompatibilityFamily(self.gene_columns),
                ParserSupportedRangeFamily(self.gene_columns),
            )
        bundle = fit_transform_family_set(
            families,
            fold_train=self.train.iloc[train_indices],
            validation=self.train.iloc[valid_indices],
            test=self.test,
            target=pd.Series(target),
        )
        registry = dict(bundle.registry)
        if self.representation == "native":
            fitted = bundle.fitted_families[0]
            registry["parser_v4_native_semantic"]["semantic_contract"] = (
                native_semantic_contract_record(fitted)  # type: ignore[arg-type]
            )
        elif self.representation == "hybrid":
            fitted_range = bundle.fitted_families[1]
            registry["parser_v4_supported_range_replacement"][
                "semantic_contract"
            ] = supported_range_contract_record(fitted_range)  # type: ignore[arg-type]
        registry["parser_baseline_projection"] = {
            "definition_version": "1.0.0",
            "representation": self.representation,
            "replaces_historical_five_family": True,
            "preserves_mutation_presence": True,
            "target_used": False,
            "test_distribution_used_for_schema": False,
        }
        return replace(
            bundle,
            registry=registry,
            base_feature_names_to_drop=self.names_to_drop,
        )


@dataclass(frozen=True)
class FittedParserSupportedRangeFamily:
    """Train-supported v4-native range view without other native columns."""

    descriptor: FeatureFamilyDescriptor
    source: FittedParserNativeSemanticFamily
    selected_indices: tuple[int, ...]

    def transform(self, frame: pd.DataFrame) -> sparse.csr_matrix:
        matrix = self.source.transform(frame)
        return sparse.csr_matrix(matrix[:, self.selected_indices], dtype="float32")


@dataclass(frozen=True)
class ParserSupportedRangeFamily:
    gene_columns: tuple[str, ...]

    def fit(
        self, train_frame: pd.DataFrame, target: pd.Series | None = None
    ) -> FittedParserSupportedRangeFamily:
        del target
        source = ParserNativeSemanticFamily(self.gene_columns).fit(train_frame)
        selected = tuple(
            index
            for index, name in enumerate(source.descriptor.feature_names)
            if name == "sample__native_range_replacement_gene_count"
            or name.endswith("__native_range_replacement_any")
        )
        names = tuple(source.descriptor.feature_names[index] for index in selected)
        if len(names) != len(self.gene_columns) + 1:
            raise ValueError("native range feature schema가 예상과 다릅니다.")
        return FittedParserSupportedRangeFamily(
            descriptor=FeatureFamilyDescriptor(
                name="parser_v4_supported_range_replacement",
                version="1.0.0",
                fit_scope="stateless",
                feature_names=names,
            ),
            source=source,
            selected_indices=selected,
        )


def supported_range_contract_record(
    fitted: FittedParserSupportedRangeFamily,
) -> dict[str, object]:
    """Record the exact native schema from which the narrow view was selected."""

    return {
        "source_family": fitted.source.descriptor.name,
        "source_version": fitted.source.descriptor.version,
        "source_schema_sha256": fitted.source.schema_sha256,
        "selection_policy": (
            "sample native range-replacement affected-gene count plus "
            "gene-level native range-replacement presence"
        ),
        "target_used": False,
        "test_distribution_used_for_schema": False,
    }
