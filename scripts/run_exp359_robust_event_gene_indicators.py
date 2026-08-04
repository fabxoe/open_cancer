#!/usr/bin/env python
"""Run EXP-359: replace generic gene complex with semantic event indicators."""

from __future__ import annotations

from scipy import sparse

from open_cancer.feature_family import FoldFeatureBundle, build_family_registry
from open_cancer.robust_mutation_parser import RobustNonSimpleGeneIndicatorFamily
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp359_robust_event_gene_indicators.yaml"


class RobustEventGeneIndicatorFoldBuilder:
    """Compose EXP-229 with the isolated R2 gene-level replacement."""

    def __init__(self) -> None:
        self.pathway_builder = PathwayMutationTypeFoldBuilder()
        self.robust_fitted = RobustNonSimpleGeneIndicatorFamily(
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
                "drop_pattern": "<gene>__complex",
                "drop_count": len(self.robust_fitted.base_feature_names_to_drop),
                "add_pattern": "<gene>__robust_<non_simple_event_family>_any",
                "add_count": self.robust_fitted.descriptor.output_dimension,
                "preserve_sample_complex_count": True,
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
        fold_feature_builder=RobustEventGeneIndicatorFoldBuilder(),
        runner_command=(
            "uv run python scripts/run_exp359_robust_event_gene_indicators.py"
        ),
    )
