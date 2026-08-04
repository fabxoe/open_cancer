#!/usr/bin/env python
"""Run EXP-355: replace raw complex-token count with robust unique-gene count."""

from __future__ import annotations

from scipy import sparse

from open_cancer.feature_family import FoldFeatureBundle, build_family_registry
from open_cancer.robust_mutation_parser import RobustNonSimpleGeneCountFamily
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp355_robust_complex_gene_count.yaml"


class RobustComplexGeneCountFoldBuilder:
    """Compose EXP-229 pathway families with one explicit base replacement."""

    def __init__(self) -> None:
        self.pathway_builder = PathwayMutationTypeFoldBuilder()
        self.robust_fitted = RobustNonSimpleGeneCountFamily(
            self.pathway_builder.gene_columns
        ).fit(self.pathway_builder.train.iloc[:1])
        self.robust_train = self.robust_fitted.transform(self.pathway_builder.train)
        self.robust_test = self.robust_fitted.transform(self.pathway_builder.test)

    def __call__(self, **kwargs) -> FoldFeatureBundle:
        pathway = self.pathway_builder(**kwargs)
        train_indices = kwargs["train_indices"]
        valid_indices = kwargs["valid_indices"]
        registry = {
            **pathway.registry,
            **build_family_registry((self.robust_fitted,)),
            "base_feature_replacement": {
                "definition_version": "1.0.0",
                "enabled": True,
                "fit_scope": "stateless",
                "output_dimension": 1,
                "drop": ["sample__complex_count"],
                "add": ["sample__robust_non_simple_event_gene_count"],
                "selection_uses_target": False,
                "selection_uses_test_prevalence": False,
            },
        }
        return FoldFeatureBundle(
            train=sparse.hstack(
                [pathway.train, self.robust_train[train_indices]], format="csr"
            ),
            validation=sparse.hstack(
                [pathway.validation, self.robust_train[valid_indices]], format="csr"
            ),
            test=sparse.hstack([pathway.test, self.robust_test], format="csr"),
            fitted_families=(*pathway.fitted_families, self.robust_fitted),
            feature_names=(
                *pathway.feature_names,
                *self.robust_fitted.descriptor.feature_names,
            ),
            registry=registry,
            base_feature_names_to_drop=self.robust_fitted.base_feature_names_to_drop,
        )


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=RobustComplexGeneCountFoldBuilder(),
        runner_command=(
            "uv run python scripts/run_exp355_robust_complex_gene_count.py"
        ),
    )
