#!/usr/bin/env python
"""Run EXP-302: EXP-229 plus fixed observable marker mutation proxies."""

from __future__ import annotations

import json
from collections.abc import Callable

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.abc_c_features import (
    fixed_pathway_burden_family,
    load_fixed_groups,
    pathway_mutation_type_family,
)
from open_cancer.feature_family import (
    FoldFeatureBundle,
    build_family_registry,
    remove_semantically_equivalent_features,
    transform_checked,
)
from open_cancer.hashing import sha256_file, sha256_lines
from open_cancer.observable_marker_features import observable_marker_family
from run_exp096_fixed_pathway_burden import KNOWLEDGE_PATH as PATHWAY_KNOWLEDGE
from run_hotspot_xgb import ROOT, TEST_PATH, TRAIN_PATH, main


CONFIG = ROOT / "configs" / "exp302_observable_marker_proxies.yaml"
MARKER_KNOWLEDGE = ROOT / "knowledge" / "fixed_observable_cancer_markers_v1.json"
AUDIT_PATH = ROOT / "reports" / "exp302_observable_marker_proxies" / "feature_audit.json"


class ObservableMarkerFoldBuilder:
    """Materialize frozen EXP-229 families plus the marker-proxy candidate."""

    def __init__(
        self,
        marker_factory: Callable = observable_marker_family,
        minimum_positive_count: int = 5,
    ) -> None:
        self.marker_factory = marker_factory
        self.minimum_positive_count = minimum_positive_count
        self.train = pd.read_csv(TRAIN_PATH, dtype=str, keep_default_na=False)
        self.test = pd.read_csv(TEST_PATH, dtype=str, keep_default_na=False)
        self.gene_columns = tuple(
            column for column in self.train.columns if column not in {"ID", "SUBCLASS"}
        )
        self.fitted = None
        self.train_matrix = None
        self.test_matrix = None
        self.fold_audits: dict[str, object] = {}

    def _prepare(self) -> None:
        if self.fitted is not None:
            return
        families = (
            fixed_pathway_burden_family(self.gene_columns, PATHWAY_KNOWLEDGE),
            pathway_mutation_type_family(self.gene_columns, PATHWAY_KNOWLEDGE),
            self.marker_factory(self.gene_columns, MARKER_KNOWLEDGE),
        )
        self.fitted = tuple(family.fit(self.train.iloc[:1]) for family in families)
        self.train_matrix = sparse.hstack(
            [transform_checked(fitted, self.train) for fitted in self.fitted], format="csr"
        )
        self.test_matrix = sparse.hstack(
            [transform_checked(fitted, self.test) for fitted in self.fitted], format="csr"
        )
        marker_fitted = self.fitted[-1]
        pathways, pathway_document = load_fixed_groups(
            PATHWAY_KNOWLEDGE, kind="pathways"
        )
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        AUDIT_PATH.write_text(
            json.dumps(
                {
                    "marker_knowledge_file": str(MARKER_KNOWLEDGE.relative_to(ROOT)),
                    "marker_knowledge_sha256": sha256_file(MARKER_KNOWLEDGE),
                    "catalog_panels": marker_fitted.catalog_panels,
                    "competition_intersections": marker_fitted.intersections,
                    "missing_catalog_genes": marker_fitted.missing_catalog_genes,
                    "candidate_feature_names": marker_fitted.descriptor.feature_names,
                    "candidate_feature_names_sha256": marker_fitted.descriptor.feature_names_sha256,
                    "pathway_knowledge_file": str(PATHWAY_KNOWLEDGE.relative_to(ROOT)),
                    "pathway_knowledge_sha256": sha256_file(PATHWAY_KNOWLEDGE),
                    "pathway_source_commit": pathway_document["source_commit"],
                    "pathway_names": list(pathways),
                    "folds": self.fold_audits,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def _write_fold_audit(self, fold: int, audit: dict[str, object]) -> None:
        self.fold_audits[str(fold)] = audit
        document = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        document["folds"] = self.fold_audits
        AUDIT_PATH.write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

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
        del base_validation, base_test, target
        self._prepare()
        feature_names = tuple(
            name for fitted in self.fitted for name in fitted.descriptor.feature_names
        )
        bundle = FoldFeatureBundle(
            train=self.train_matrix[train_indices],
            validation=self.train_matrix[valid_indices],
            test=self.test_matrix,
            fitted_families=self.fitted,
            feature_names=feature_names,
            registry=build_family_registry(self.fitted),
        )
        bundle, equivalents = remove_semantically_equivalent_features(
            bundle, base_train, base_feature_names
        )

        marker_prefix = "sample__observable_marker_"
        positive_counts = np.asarray(bundle.train.sum(axis=0)).ravel()
        keep: list[int] = []
        dropped_low_support: dict[str, int] = {}
        for index, name in enumerate(bundle.feature_names):
            if name.startswith(marker_prefix) and positive_counts[index] < self.minimum_positive_count:
                dropped_low_support[name] = int(positive_counts[index])
            else:
                keep.append(index)
        if len(keep) != len(bundle.feature_names):
            filtered_names = tuple(bundle.feature_names[index] for index in keep)
            registry = {
                **bundle.registry,
                "marker_minimum_support_filter": {
                    "definition_version": "1.0.0",
                    "enabled": True,
                    "output_dimension": len(filtered_names),
                    "feature_names_sha256": sha256_lines(filtered_names),
                    "fit_scope": "fold_train",
                    "external_knowledge": None,
                    "minimum_positive_count": self.minimum_positive_count,
                    "dropped": dropped_low_support,
                },
            }
            bundle = FoldFeatureBundle(
                train=bundle.train[:, keep],
                validation=bundle.validation[:, keep],
                test=bundle.test[:, keep],
                fitted_families=bundle.fitted_families,
                feature_names=filtered_names,
                registry=registry,
            )
        retained_marker_names = [
            name for name in bundle.feature_names if name.startswith(marker_prefix)
        ]
        self._write_fold_audit(
            fold,
            {
                "semantic_equivalents": equivalents,
                "dropped_low_support": dropped_low_support,
                "retained_marker_features": retained_marker_names,
                "retained_marker_feature_count": len(retained_marker_names),
                "final_feature_names_sha256": sha256_lines(bundle.feature_names),
            },
        )
        return bundle


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=ObservableMarkerFoldBuilder(),
        runner_command="uv run python scripts/run_exp302_observable_marker_proxies.py",
    )
