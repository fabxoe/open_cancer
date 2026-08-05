#!/usr/bin/env python
"""Run EXP-370: isolated stop notation normalization on EXP-223."""

from __future__ import annotations

import json

from open_cancer.abc_c_features import (
    fixed_pathway_burden_family,
    load_fixed_groups,
)
from open_cancer.feature_family import transform_checked
from open_cancer.hashing import sha256_file
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
    parse_stop_notation_invariant_token,
)
from run_exp096_fixed_pathway_burden import (
    FixedPathwayBurdenFoldBuilder,
    KNOWLEDGE_PATH,
)
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp370_exp223_stop_notation_normalization.yaml"
MEMBERSHIP = (
    ROOT
    / "reports"
    / "exp370_exp223_stop_notation_normalization"
    / "pathway_membership.json"
)


class StopNormalizedFixedPathwayBurdenFoldBuilder(
    FixedPathwayBurdenFoldBuilder
):
    """EXP-223 pathway burden with only stop notation semantics replaced."""

    def _prepare(self) -> None:
        if self.fitted is not None:
            return

        family = fixed_pathway_burden_family(
            self.gene_columns,
            KNOWLEDGE_PATH,
            token_parser=parse_stop_notation_invariant_token,
            version="2.1.0",
        )
        self.fitted = family.fit(self.train.iloc[:1])
        self.train_matrix = transform_checked(self.fitted, self.train)
        self.test_matrix = transform_checked(self.fitted, self.test)

        groups, document = load_fixed_groups(
            KNOWLEDGE_PATH,
            kind="pathways",
        )
        self.membership_path.parent.mkdir(parents=True, exist_ok=True)
        self.membership_path.write_text(
            json.dumps(
                {
                    "knowledge_file": str(KNOWLEDGE_PATH.relative_to(ROOT)),
                    "knowledge_sha256": sha256_file(KNOWLEDGE_PATH),
                    "source_url": document["source_url"],
                    "source_commit": document["source_commit"],
                    "source_sha256": document["source_sha256"],
                    "extraction_policy": document["extraction_policy"],
                    "organizer_approval_reference": document[
                        "organizer_approval_reference"
                    ],
                    "competition_gene_count": len(self.gene_columns),
                    "mutation_parser_contract": STOP_NOTATION_PARSER_CONTRACT,
                    "pathways": {
                        name: {
                            "source_gene_nodes": list(genes),
                            "panel_intersection": list(
                                self.fitted.intersections[name]
                            ),
                            "excluded_non_panel_nodes": [
                                gene
                                for gene in genes
                                if gene not in self.fitted.intersections[name]
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


def build_fold_features() -> StopNormalizedFixedPathwayBurdenFoldBuilder:
    """Build the EXP-223 pathway family with the EXP-369 parser adapter."""

    return StopNormalizedFixedPathwayBurdenFoldBuilder(MEMBERSHIP)


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=build_fold_features(),
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        runner_command=(
            "uv run python "
            "scripts/run_exp370_exp223_stop_notation_normalization.py "
            "--config configs/exp370_exp223_stop_notation_normalization.yaml"
        ),
    )
