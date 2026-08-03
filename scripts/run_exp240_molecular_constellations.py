#!/usr/bin/env python
"""Run EXP-240: EXP-229 plus fixed molecular-constellation features."""

from __future__ import annotations

import json

from scipy import sparse

from open_cancer.feature_family import build_family_registry, transform_checked
from open_cancer.hashing import sha256_file
from open_cancer.molecular_constellation_features import (
    MolecularConstellationFamily,
    load_molecular_modules,
)
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp240_molecular_constellations.yaml"
KNOWLEDGE_PATH = ROOT / "knowledge" / "cancer_lineage_modules_tcga_v1.json"
REPORT_DIR = ROOT / "reports" / "exp240_molecular_constellations"
MEMBERSHIP = REPORT_DIR / "molecular_module_membership.json"


class MolecularConstellationFoldBuilder(PathwayMutationTypeFoldBuilder):
    """Materialize EXP-229 families and 21 fixed lineage-module candidates."""

    def __init__(self) -> None:
        super().__init__(REPORT_DIR / "pathway_membership.json")

    def _prepare(self) -> None:
        if self.fitted is not None:
            return
        super()._prepare()
        family = MolecularConstellationFamily(self.gene_columns, KNOWLEDGE_PATH)
        fitted = family.fit(self.train.iloc[:1])
        self.fitted = (*self.fitted, fitted)
        self.train_matrix = sparse.hstack(
            [self.train_matrix, transform_checked(fitted, self.train)], format="csr"
        )
        self.test_matrix = sparse.hstack(
            [self.test_matrix, transform_checked(fitted, self.test)], format="csr"
        )
        modules, document = load_molecular_modules(KNOWLEDGE_PATH)
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        MEMBERSHIP.write_text(
            json.dumps(
                {
                    "knowledge_file": str(KNOWLEDGE_PATH.relative_to(ROOT)),
                    "knowledge_sha256": sha256_file(KNOWLEDGE_PATH),
                    "version": document["version"],
                    "selection_policy": document["selection_policy"],
                    "competition_rule_basis": document["competition_rule_basis"],
                    "rule_review_status": document["rule_review_status"],
                    "sources": document["sources"],
                    "competition_gene_count": len(self.gene_columns),
                    "modules": {
                        name: {
                            "source_core_genes": list(definition["core"]),
                            "source_partner_genes": list(definition["partners"]),
                            "panel_core_intersection": list(
                                fitted.intersections[name]["core"]
                            ),
                            "panel_partner_intersection": list(
                                fitted.intersections[name]["partners"]
                            ),
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


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=MolecularConstellationFoldBuilder(),
        runner_command="uv run python scripts/run_exp240_molecular_constellations.py",
    )
