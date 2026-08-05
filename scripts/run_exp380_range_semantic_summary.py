#!/usr/bin/env python
"""Run EXP-380: add four range-stop/no-change summaries to EXP-369."""

from __future__ import annotations

from functools import partial

import numpy as np
from scipy import sparse

from open_cancer.abc_c_features import (
    fixed_pathway_burden_family,
    pathway_mutation_type_family,
)
from open_cancer.feature_family import (
    FoldFeatureBundle,
    build_family_registry,
    transform_checked,
)
from open_cancer.range_semantic_summary_features import RangeSemanticSummaryFamily
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
    parse_stop_notation_invariant_token,
)
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp380_range_semantic_summary.yaml"
MEMBERSHIP = ROOT / "reports" / "exp380_range_semantic_summary" / "pathway_membership.json"


class RangeSemanticFoldBuilder:
    """Append four stateless range summaries to the unchanged EXP-369 extras."""

    def __init__(self) -> None:
        burden = partial(
            fixed_pathway_burden_family,
            token_parser=parse_stop_notation_invariant_token,
            version="2.1.0",
        )
        composition = partial(
            pathway_mutation_type_family,
            token_parser=parse_stop_notation_invariant_token,
            version="2.1.0",
        )
        self.parent = PathwayMutationTypeFoldBuilder(
            membership_path=MEMBERSHIP,
            burden_factory=burden,
            composition_factory=composition,
        )
        self.range_fitted = None
        self.range_train = None
        self.range_test = None

    def _prepare_range(self) -> None:
        if self.range_fitted is not None:
            return
        family = RangeSemanticSummaryFamily(self.parent.gene_columns)
        self.range_fitted = family.fit(self.parent.train.iloc[:1])
        self.range_train = transform_checked(self.range_fitted, self.parent.train)
        self.range_test = transform_checked(self.range_fitted, self.parent.test)

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
        parent = self.parent(
            fold=fold,
            train_indices=train_indices,
            valid_indices=valid_indices,
            base_train=base_train,
            base_validation=base_validation,
            base_test=base_test,
            base_feature_names=base_feature_names,
            target=target,
        )
        self._prepare_range()
        assert self.range_fitted is not None
        assert self.range_train is not None
        assert self.range_test is not None
        range_registry = build_family_registry((self.range_fitted,))
        return FoldFeatureBundle(
            train=sparse.hstack(
                [parent.train, self.range_train[train_indices]],
                format="csr",
                dtype=np.float32,
            ),
            validation=sparse.hstack(
                [parent.validation, self.range_train[valid_indices]],
                format="csr",
                dtype=np.float32,
            ),
            test=sparse.hstack(
                [parent.test, self.range_test],
                format="csr",
                dtype=np.float32,
            ),
            fitted_families=(*parent.fitted_families, self.range_fitted),
            feature_names=(
                *parent.feature_names,
                *self.range_fitted.descriptor.feature_names,
            ),
            registry={**parent.registry, **range_registry},
            base_feature_names_to_drop=parent.base_feature_names_to_drop,
        )


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=RangeSemanticFoldBuilder(),
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        runner_command="uv run python scripts/run_exp380_range_semantic_summary.py",
    )
