"""Controlled legacy/compatibility/native feature adapters for parser N4."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Literal

import pandas as pd

from open_cancer.feature_family import FoldFeatureBundle, fit_transform_family_set
from open_cancer.mutation_features import MUTATION_TYPES
from open_cancer.parser_compatibility_features import ParserCompatibilityFamily
from open_cancer.parser_native_features import (
    ParserNativeSemanticFamily,
    native_semantic_contract_record,
)


ParserRepresentation = Literal["legacy", "compatibility", "native"]


def validate_controlled_parser_baseline_config(config: dict) -> ParserRepresentation:
    """Reject any setting that would confound the N4 three-arm comparison."""

    representation = str(config.get("parser_baseline", {}).get("representation", ""))
    if representation not in {"legacy", "compatibility", "native"}:
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
        family = (
            ParserCompatibilityFamily(self.gene_columns)
            if self.representation == "compatibility"
            else ParserNativeSemanticFamily(self.gene_columns)
        )
        bundle = fit_transform_family_set(
            (family,),
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
