#!/usr/bin/env python
"""Run EXP-603: EXP-374 plus a directionally-split lineage driver-gene burden.

EXP-514 (Issue #514, ARCHIVE, already merged to main) pooled kidney driver
genes (VHL, MTOR, TSC1, TSC2, PTEN, MET, FH) into one group and glioma driver
genes (IDH1, IDH2, ATRX, TP53, NF1, PTEN, EGFR) into another, then summed
mutated/LOF gene counts per group. It improved KIRC (+0.0278) and LGG
(+0.0172) but GBMLGG (-0.0167) offset the gain, so the overall OOF Macro F1
improvement (+0.0001756) missed the +0.001 gate.

Direct data/raw/train.csv verification of per-class mutation rates
(documented in reports/exp603_directional_lineage_burden/README.md) found
that both EXP-514 pooled groups mixed genes with opposite class-favoring
direction:

- glioma: IDH1/IDH2/ATRX/TP53 favor LGG, but NF1/PTEN/EGFR favor GBMLGG.
- kidney: VHL/MTOR favor KIRC, but TSC1/TSC2/MET favor KIPAN; FH is
  zero-variance (0 mutated samples in both KIPAN and KIRC in this dataset).

This matches independent literature (WHO CNS5 IDH-mutant astrocytoma vs
IDH-wildtype GBM molecular classification; WHO renal tumor classification's
VHL-ccRCC/KIRC and MET-papillary-RCC driver associations), not something
mined from SUBCLASS -- the train.csv check only confirms the known biology
shows up in this competition panel.

This experiment re-splits the same 14-gene literature panel (minus
zero-variance FH, minus noise-level kidney-context PTEN) into four
directionally consistent groups via a new knowledge file,
knowledge/kirc_kidney_glioma_directional_lineage_v1.json:

- kirc_lineage: VHL, MTOR
- kipan_nonccrcc_lineage: TSC1, TSC2, MET
- lgg_idh_lineage: IDH1, IDH2, ATRX, TP53
- gbm_idh_wildtype_lineage: NF1, PTEN, EGFR

producing 8 burden columns (4 groups x mutated/LOF gene count) instead of
EXP-514's 4. EXP-514's own 4 columns are NOT reused here -- this is a fresh
single-family ablation against EXP-374, not a stack on top of EXP-514.

EXP-374's stop-notation parser, pathway-20 fixed_pathway_burden family,
pathway_mutation_type_composition candidate, hotspot-34 table, and Ensembl
residue-position isoform mask are all reused unchanged, following the same
fold_feature_builder pattern as
scripts/run_exp514_kidney_glioma_lineage_burden.py /
scripts/run_exp229_pathway_mutation_types.py. Per PROJECT_CONTEXT.md's
committed-report-path lesson learned this session, this runner's own
MEMBERSHIP path lives under reports/exp603_directional_lineage_burden/ (not
EXP-374's or EXP-514's committed report directories) so repeated runs never
dirty another experiment's committed artifacts.
"""

from __future__ import annotations

import dataclasses
import json

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


CONFIG = ROOT / "configs" / "exp603_directional_lineage_burden.yaml"
CANONICAL_PATHWAY_KNOWLEDGE = ROOT / "knowledge" / "canonical_pathways_sanchez_vega_v1.json"
LINEAGE_KNOWLEDGE = ROOT / "knowledge" / "kirc_kidney_glioma_directional_lineage_v1.json"
MEMBERSHIP = (
    ROOT / "reports" / "exp603_directional_lineage_burden" / "pathway_membership.json"
)
LINEAGE_FAMILY_NAME = "kirc_kidney_glioma_directional_lineage_burden"


class DirectionalLineageFoldBuilder:
    """EXP-374's pathway-20 + composition-kept, plus the new lineage burden-8.

    Modeled on run_exp514_kidney_glioma_lineage_burden.KidneyGliomaLineageFoldBuilder,
    itself modeled on run_exp229_pathway_mutation_types.PathwayMutationTypeFoldBuilder:
    all three families are stateless (fit_scope="stateless"), so they are
    materialized once for the whole train/test frame and simply sliced per
    fold. The combined bundle is still checked against the frozen base
    feature matrix (mutation-type/hotspot/residue-position/aggregates) with
    the shared remove_semantically_equivalent_features guard, exactly as
    EXP-229/EXP-374/EXP-514 already do for the canonical pathway family.
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
                    "kirc_kidney_glioma_directional_lineage": {
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
        fold_feature_builder=DirectionalLineageFoldBuilder(),
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        runner_command="uv run python scripts/run_exp603_directional_lineage_burden.py",
    )
