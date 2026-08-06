#!/usr/bin/env python
"""Run EXP-514: EXP-374 plus a fixed kidney/glioma lineage driver-gene burden.

EXP-374's OOF error analysis (reports/exp374_stop_isoform_residue_mask/) found
the two largest confusion pairs are KIPAN<->KIRC (390 combined
misclassifications) and GBMLGG<->LGG (288 combined). Both pairs are known TCGA
labeling artifacts, but this experiment tests whether a compact,
literature-grounded lineage-driver burden feature still helps the tree model
separate them: a kidney/VHL-mTOR group (VHL, MTOR, TSC1, TSC2, PTEN, MET, FH)
and a glioma/WHO-IDH group (IDH1, IDH2, ATRX, TP53, NF1, PTEN, EGFR), fixed
before this experiment ran from independent ccRCC/glioma driver-gene
literature (see knowledge/kirc_kidney_glioma_lineage_v1.json).

EXP-374's stop-notation parser, pathway-20 fixed_pathway_burden family,
pathway_mutation_type_composition candidate, hotspot-34 table, and Ensembl
residue-position isoform mask are all reused unchanged (same config blocks,
same fold_feature_builder pattern as
scripts/run_exp374_stop_isoform_residue_mask.py /
scripts/run_exp229_pathway_mutation_types.py). This is a single-family
ablation: the only addition is four new sample-level burden columns
(mutated_gene_count, lof_gene_count for each of the two lineage groups).
"""

from __future__ import annotations

import dataclasses
import json
from functools import partial

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
from open_cancer.hashing import sha256_file
from open_cancer.paths import relative_posix
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
    parse_stop_notation_invariant_token,
)
from run_hotspot_xgb import ROOT, TEST_PATH, TRAIN_PATH, main


CONFIG = ROOT / "configs" / "exp514_kidney_glioma_lineage_burden.yaml"
CANONICAL_PATHWAY_KNOWLEDGE = ROOT / "knowledge" / "canonical_pathways_sanchez_vega_v1.json"
LINEAGE_KNOWLEDGE = ROOT / "knowledge" / "kirc_kidney_glioma_lineage_v1.json"
MEMBERSHIP = (
    ROOT / "reports" / "exp514_kidney_glioma_lineage_burden" / "pathway_membership.json"
)
LINEAGE_FAMILY_NAME = "kirc_kidney_glioma_lineage_burden"


class KidneyGliomaLineageFoldBuilder:
    """EXP-374's pathway-20 + composition-kept, plus the new lineage burden-4.

    Modeled on run_exp229_pathway_mutation_types.PathwayMutationTypeFoldBuilder:
    all three families are stateless (fit_scope="stateless"), so they are
    materialized once for the whole train/test frame and simply sliced per
    fold. The combined bundle is still checked against the frozen base
    feature matrix (mutation-type/hotspot/residue-position/aggregates) with
    the shared remove_semantically_equivalent_features guard, exactly as
    EXP-229/EXP-374 already do for the canonical pathway family.
    """

    def __init__(self) -> None:
        self.train = pd.read_csv(TRAIN_PATH, dtype=str, keep_default_na=False)
        self.test = pd.read_csv(TEST_PATH, dtype=str, keep_default_na=False)
        self.gene_columns = tuple(
            column for column in self.train.columns if column not in {"ID", "SUBCLASS"}
        )
        self.fitted = None
        self.train_matrix = None
        self.test_matrix = None

    def _prepare(self) -> None:
        if self.fitted is not None:
            return
        canonical_burden = fixed_pathway_burden_family(
            self.gene_columns,
            CANONICAL_PATHWAY_KNOWLEDGE,
            token_parser=parse_stop_notation_invariant_token,
            version="2.1.0",
        )
        canonical_composition = pathway_mutation_type_family(
            self.gene_columns,
            CANONICAL_PATHWAY_KNOWLEDGE,
            token_parser=parse_stop_notation_invariant_token,
            version="2.1.0",
        )
        lineage_burden = fixed_pathway_burden_family(
            self.gene_columns,
            LINEAGE_KNOWLEDGE,
            token_parser=parse_stop_notation_invariant_token,
            version="1.0.0",
        )
        fitted_canonical_burden = canonical_burden.fit(self.train.iloc[:1])
        fitted_canonical_composition = canonical_composition.fit(self.train.iloc[:1])
        fitted_lineage_burden_raw = lineage_burden.fit(self.train.iloc[:1])
        # fixed_pathway_burden_family() always names its descriptor
        # "fixed_pathway_burden" (the family class hard-codes this for
        # kind="pathways"). Rename only the descriptor identity so this
        # second, independently-sourced burden family gets its own distinct
        # registry key; the fitted transform logic and feature names (which
        # already carry the lineage group names) are untouched.
        fitted_lineage_burden = dataclasses.replace(
            fitted_lineage_burden_raw,
            descriptor=dataclasses.replace(
                fitted_lineage_burden_raw.descriptor, name=LINEAGE_FAMILY_NAME
            ),
        )
        self.fitted = (
            fitted_canonical_burden,
            fitted_canonical_composition,
            fitted_lineage_burden,
        )
        self.train_matrix = sparse.hstack(
            [transform_checked(fitted, self.train) for fitted in self.fitted], format="csr"
        )
        self.test_matrix = sparse.hstack(
            [transform_checked(fitted, self.test) for fitted in self.fitted], format="csr"
        )
        groups, document = load_fixed_groups(CANONICAL_PATHWAY_KNOWLEDGE, kind="pathways")
        intersections = fitted_canonical_burden.intersections
        lineage_groups, lineage_document = load_fixed_groups(LINEAGE_KNOWLEDGE, kind="pathways")
        lineage_intersections = fitted_lineage_burden_raw.intersections
        self.membership_path = MEMBERSHIP
        self.membership_path.parent.mkdir(parents=True, exist_ok=True)
        self.membership_path.write_text(
            json.dumps(
                {
                    "canonical_pathways": {
                        "knowledge_file": relative_posix(
                            CANONICAL_PATHWAY_KNOWLEDGE, ROOT
                        ),
                        "knowledge_sha256": sha256_file(CANONICAL_PATHWAY_KNOWLEDGE),
                        "source_url": document["source_url"],
                        "source_commit": document["source_commit"],
                        "source_sha256": document["source_sha256"],
                        "extraction_policy": document["extraction_policy"],
                        "organizer_approval_reference": document[
                            "organizer_approval_reference"
                        ],
                        "pathways": {
                            name: {
                                "source_gene_nodes": list(genes),
                                "panel_intersection": list(intersections[name]),
                                "excluded_non_panel_nodes": [
                                    gene for gene in genes if gene not in intersections[name]
                                ],
                            }
                            for name, genes in groups.items()
                        },
                    },
                    "kirc_kidney_glioma_lineage": {
                        "knowledge_file": relative_posix(LINEAGE_KNOWLEDGE, ROOT),
                        "knowledge_sha256": sha256_file(LINEAGE_KNOWLEDGE),
                        "source_url": lineage_document["source_url"],
                        "source_commit": lineage_document["source_commit"],
                        "source_sha256": lineage_document["source_sha256"],
                        "extraction_policy": lineage_document["extraction_policy"],
                        "selection_policy": lineage_document["selection_policy"],
                        "organizer_approval_reference": lineage_document[
                            "organizer_approval_reference"
                        ],
                        "pathways": {
                            name: {
                                "source_gene_nodes": list(genes),
                                "panel_intersection": list(lineage_intersections[name]),
                                "excluded_non_panel_nodes": [
                                    gene
                                    for gene in genes
                                    if gene not in lineage_intersections[name]
                                ],
                            }
                            for name, genes in lineage_groups.items()
                        },
                    },
                    "competition_gene_count": len(self.gene_columns),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
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
        del fold, base_validation, base_test, target
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
        bundle, _ = remove_semantically_equivalent_features(
            bundle, base_train, base_feature_names
        )
        return bundle


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=KidneyGliomaLineageFoldBuilder(),
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        runner_command="uv run python scripts/run_exp514_kidney_glioma_lineage_burden.py",
    )
