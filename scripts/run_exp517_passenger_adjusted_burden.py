#!/usr/bin/env python
"""Run EXP-517: EXP-374 + additive passenger-adjusted burden derived columns.

This runner keeps every EXP-374 feature (parser, hotspots, residue-position
Ensembl mask, fixed Sanchez-Vega pathway families) exactly unchanged and adds
exactly two new sample-level derived columns on top, computed from a fixed
15-gene "long-gene passenger candidate" list
(``knowledge/long_gene_passenger_candidates_v1.json``):

- ``sample__mutated_gene_count_excl_passenger`` = the existing
  ``sample__mutated_gene_count`` total burden feature minus the count of the
  15 passenger genes mutated in that sample.
- ``sample__passenger_gene_fraction`` = (count of the 15 passenger genes
  mutated in that sample) / 15.

No existing ``GENE__mutated``-style column is removed or replaced; this is
deliberately additive-only (see the config ``notes`` for why).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import partial

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.abc_c_features import (
    fixed_pathway_burden_family,
    load_fixed_groups,
    pathway_mutation_type_family,
)
from open_cancer.feature_family import (
    FeatureFamilyDescriptor,
    FoldFeatureBundle,
    find_semantically_equivalent_features,
    transform_checked,
)
from open_cancer.hashing import sha256_file
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
    parse_stop_notation_invariant_token,
)
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, TEST_PATH, TRAIN_PATH, main


CONFIG = ROOT / "configs" / "exp517_passenger_adjusted_burden.yaml"
REPORT_DIR = ROOT / "reports" / "exp517_passenger_adjusted_burden"
PATHWAY_MEMBERSHIP = REPORT_DIR / "pathway_membership.json"
PASSENGER_MEMBERSHIP = REPORT_DIR / "passenger_group_membership.json"
PASSENGER_KNOWLEDGE_PATH = ROOT / "knowledge" / "long_gene_passenger_candidates_v1.json"
PASSENGER_GROUP_NAME = "long_gene_passenger_candidates"

DERIVED_FEATURE_NAMES = (
    "sample__mutated_gene_count_excl_passenger",
    "sample__passenger_gene_fraction",
)


@dataclass
class PassengerAdjustedBurdenFoldBuilder:
    """Preserve every EXP-374 feature and additively append 2 passenger columns.

    Modeled on ``PathwayMutationTypeFoldBuilder`` (run_exp229). This builder
    first delegates to an unchanged EXP-374 pathway builder instance, then
    layers the 2 new derived columns on top by combining (a) the passenger
    group's ``mutated_gene_count`` from ``fixed_pathway_burden_family`` (the
    existing fixed-gene-group burden machinery, reused rather than
    reimplemented) with (b) the existing ``sample__mutated_gene_count`` base
    feature column that is always present in ``base_feature_names``.
    """

    def __init__(self) -> None:
        self.pathway_builder = PathwayMutationTypeFoldBuilder(
            membership_path=PATHWAY_MEMBERSHIP,
            burden_factory=partial(
                fixed_pathway_burden_family,
                token_parser=parse_stop_notation_invariant_token,
                version="2.1.0",
            ),
            composition_factory=partial(
                pathway_mutation_type_family,
                token_parser=parse_stop_notation_invariant_token,
                version="2.1.0",
            ),
        )
        self.train = pd.read_csv(TRAIN_PATH, dtype=str, keep_default_na=False)
        self.test = pd.read_csv(TEST_PATH, dtype=str, keep_default_na=False)
        self.gene_columns = tuple(
            column for column in self.train.columns if column not in {"ID", "SUBCLASS"}
        )
        self._passenger_fitted = None
        self._passenger_train_matrix = None
        self._passenger_test_matrix = None
        self._passenger_gene_count = None
        self._derived_descriptor = None
        self._duplication_checked = False

    def _prepare_passenger(self) -> None:
        if self._passenger_fitted is not None:
            return
        family = fixed_pathway_burden_family(
            self.gene_columns,
            PASSENGER_KNOWLEDGE_PATH,
            token_parser=parse_stop_notation_invariant_token,
            version="1.0.0",
        )
        self._passenger_fitted = family.fit(self.train.iloc[:1])
        self._passenger_train_matrix = transform_checked(self._passenger_fitted, self.train)
        self._passenger_test_matrix = transform_checked(self._passenger_fitted, self.test)
        self._passenger_gene_count = len(
            self._passenger_fitted.groups[PASSENGER_GROUP_NAME]
        )

        source_provenance = self._passenger_fitted.descriptor.external_knowledge[0]
        self._derived_descriptor = FeatureFamilyDescriptor(
            name="passenger_adjusted_burden",
            version="1.0.0",
            fit_scope="stateless",
            feature_names=DERIVED_FEATURE_NAMES,
            external_knowledge=(source_provenance,),
        )

        groups, document = load_fixed_groups(PASSENGER_KNOWLEDGE_PATH, kind="pathways")
        intersections = self._passenger_fitted.intersections
        PASSENGER_MEMBERSHIP.parent.mkdir(parents=True, exist_ok=True)
        PASSENGER_MEMBERSHIP.write_text(
            json.dumps(
                {
                    "knowledge_file": str(PASSENGER_KNOWLEDGE_PATH.relative_to(ROOT)),
                    "knowledge_sha256": sha256_file(PASSENGER_KNOWLEDGE_PATH),
                    "source": document["source"],
                    "source_url": document["source_url"],
                    "extraction_policy": document["extraction_policy"],
                    "selection_policy": document["selection_policy"],
                    "organizer_approval_reference": document["organizer_approval_reference"],
                    "competition_gene_count": len(self.gene_columns),
                    "derived_feature_names": list(DERIVED_FEATURE_NAMES),
                    "passenger_gene_denominator": self._passenger_gene_count,
                    "groups": {
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
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _passenger_mutated_counts(matrix: sparse.csr_matrix) -> np.ndarray:
        # Column 0 is `<group>__mutated_gene_count`; column 1 is
        # `<group>__lof_gene_count` (unused: only the mutated-gene count is
        # needed to build the 2 additive derived columns of this experiment).
        return np.asarray(matrix[:, 0].todense()).ravel()

    def __call__(
        self,
        *,
        fold: int,
        train_indices: np.ndarray,
        valid_indices: np.ndarray,
        base_train: sparse.spmatrix,
        base_validation: sparse.spmatrix,
        base_test: sparse.spmatrix,
        base_feature_names: tuple[str, ...],
        target: np.ndarray,
    ) -> FoldFeatureBundle:
        pathway_bundle = self.pathway_builder(
            fold=fold,
            train_indices=train_indices,
            valid_indices=valid_indices,
            base_train=base_train,
            base_validation=base_validation,
            base_test=base_test,
            base_feature_names=base_feature_names,
            target=target,
        )
        self._prepare_passenger()

        if "sample__mutated_gene_count" not in base_feature_names:
            raise ValueError("base feature 목록에 sample__mutated_gene_count가 없습니다.")
        total_index = base_feature_names.index("sample__mutated_gene_count")

        def total_column(matrix: sparse.spmatrix) -> np.ndarray:
            return np.asarray(matrix[:, total_index].todense()).ravel().astype(np.float32)

        passenger_train_full = self._passenger_mutated_counts(self._passenger_train_matrix)
        passenger_test_full = self._passenger_mutated_counts(self._passenger_test_matrix)
        passenger_train = passenger_train_full[train_indices]
        passenger_valid = passenger_train_full[valid_indices]

        def derive(total: np.ndarray, passenger: np.ndarray) -> sparse.csr_matrix:
            excl = (total - passenger).astype(np.float32)
            frac = (passenger / float(self._passenger_gene_count)).astype(np.float32)
            return sparse.csr_matrix(np.column_stack([excl, frac]))

        derived_train = derive(total_column(base_train), passenger_train)
        derived_valid = derive(total_column(base_validation), passenger_valid)
        derived_test = derive(total_column(base_test), passenger_test_full)

        if not self._duplication_checked:
            # One-time (fold 0) semantic-duplication self-check: confirm the 2
            # new derived columns are not byte-identical, on these fold-train
            # rows, to any existing base feature or EXP-374 pathway-family
            # feature already in this experiment's feature set.
            reference = sparse.hstack([base_train, pathway_bundle.train], format="csr")
            reference_names = (*base_feature_names, *pathway_bundle.feature_names)
            duplicates = find_semantically_equivalent_features(
                derived_train, DERIVED_FEATURE_NAMES, reference, reference_names
            )
            print(
                "[EXP-517 semantic-duplication check] fold=0 duplicates found: "
                f"{duplicates if duplicates else 'none'}"
            )
            if duplicates:
                raise ValueError(
                    f"passenger_adjusted_burden 열이 기존 열과 값이 같습니다: {duplicates}"
                )
            self._duplication_checked = True

        feature_names = (*pathway_bundle.feature_names, *DERIVED_FEATURE_NAMES)
        registry = {
            **pathway_bundle.registry,
            "passenger_adjusted_burden": self._derived_descriptor.to_registry_record(),
        }

        return FoldFeatureBundle(
            train=sparse.hstack([pathway_bundle.train, derived_train], format="csr", dtype=np.float32),
            validation=sparse.hstack(
                [pathway_bundle.validation, derived_valid], format="csr", dtype=np.float32
            ),
            test=sparse.hstack([pathway_bundle.test, derived_test], format="csr", dtype=np.float32),
            fitted_families=(*pathway_bundle.fitted_families, self._passenger_fitted),
            feature_names=feature_names,
            registry=registry,
            base_feature_names_to_drop=pathway_bundle.base_feature_names_to_drop,
        )


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=PassengerAdjustedBurdenFoldBuilder(),
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        runner_command="uv run python scripts/run_exp517_passenger_adjusted_burden.py",
    )
