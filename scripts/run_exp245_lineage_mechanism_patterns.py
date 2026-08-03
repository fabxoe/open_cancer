#!/usr/bin/env python
"""Run EXP-245: EXP-229 plus fixed lineage mechanism-pattern proxies."""

from __future__ import annotations

import json

from scipy import sparse

from open_cancer.feature_family import (
    FoldFeatureBundle,
    build_family_registry,
    find_semantically_equivalent_features,
    transform_checked,
)
from open_cancer.hashing import sha256_file
from open_cancer.lineage_mechanism_features import (
    LineageMechanismFamily,
    load_lineage_mechanism_patterns,
)
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp245_lineage_mechanism_patterns.yaml"
KNOWLEDGE_PATH = (
    ROOT / "knowledge" / "cancer_lineage_mechanism_patterns_tcga_v1.json"
)
REPORT_DIR = ROOT / "reports" / "exp245_lineage_mechanism_patterns"
MEMBERSHIP = REPORT_DIR / "lineage_mechanism_membership.json"
PREFIX = "sample__lineage_mechanism_"


class LineageMechanismFoldBuilder(PathwayMutationTypeFoldBuilder):
    """Materialize EXP-229 families and 32 mechanism-aware candidates."""

    def __init__(self) -> None:
        super().__init__(REPORT_DIR / "pathway_membership.json")

    def _prepare(self) -> None:
        if self.fitted is not None:
            return
        super()._prepare()
        family = LineageMechanismFamily(self.gene_columns, KNOWLEDGE_PATH)
        fitted = family.fit(self.train.iloc[:1])
        self.fitted = (*self.fitted, fitted)
        self.train_matrix = sparse.hstack(
            [self.train_matrix, transform_checked(fitted, self.train)], format="csr"
        )
        self.test_matrix = sparse.hstack(
            [self.test_matrix, transform_checked(fitted, self.test)], format="csr"
        )
        modules, document = load_lineage_mechanism_patterns(KNOWLEDGE_PATH)
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        MEMBERSHIP.write_text(
            json.dumps(
                {
                    "knowledge_file": str(KNOWLEDGE_PATH.relative_to(ROOT)),
                    "knowledge_sha256": sha256_file(KNOWLEDGE_PATH),
                    "version": document["version"],
                    "selection_policy": document["selection_policy"],
                    "competition_rule_basis": document["competition_rule_basis"],
                    "interpretation_limit": document["interpretation_limit"],
                    "sources": document["sources"],
                    "competition_gene_count": len(self.gene_columns),
                    "modules": {
                        name: {
                            "source": {
                                group: list(genes)
                                for group, genes in definition.items()
                            },
                            "panel_intersection": {
                                group: list(fitted.intersections[name][group])
                                for group in definition
                            },
                        }
                        for name, definition in modules.items()
                    },
                    "family_registry": build_family_registry((fitted,)),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def __call__(self, **kwargs) -> FoldFeatureBundle:
        bundle = super().__call__(**kwargs)
        candidate_indices = [
            index
            for index, name in enumerate(bundle.feature_names)
            if name.startswith(PREFIX)
        ]
        reference_indices = [
            index
            for index, name in enumerate(bundle.feature_names)
            if not name.startswith(PREFIX)
        ]
        equivalents = find_semantically_equivalent_features(
            bundle.train[:, candidate_indices],
            tuple(bundle.feature_names[index] for index in candidate_indices),
            bundle.train[:, reference_indices],
            tuple(bundle.feature_names[index] for index in reference_indices),
        )
        keep = [
            index
            for index, name in enumerate(bundle.feature_names)
            if name not in equivalents
        ]
        names = tuple(bundle.feature_names[index] for index in keep)
        registry = {
            **bundle.registry,
            "exp229_semantic_equivalence_filter": {
                "definition_version": "1.0.0",
                "enabled": True,
                "fit_scope": "fold_train",
                "output_dimension": len(names),
                "external_knowledge": None,
                "dropped": equivalents,
            },
        }
        return FoldFeatureBundle(
            train=bundle.train[:, keep],
            validation=bundle.validation[:, keep],
            test=bundle.test[:, keep],
            fitted_families=bundle.fitted_families,
            feature_names=names,
            registry=registry,
        )


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=LineageMechanismFoldBuilder(),
        runner_command="uv run python scripts/run_exp245_lineage_mechanism_patterns.py",
    )
