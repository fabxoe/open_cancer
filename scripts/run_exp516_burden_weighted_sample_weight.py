#!/usr/bin/env python
"""Run EXP-516: EXP-374 + fold-safe low-burden sample weight multiplier.

Single change vs EXP-374 (see configs/exp516_burden_weighted_sample_weight.yaml
and Issue #516): multiply the existing balanced_sample_weight by a fixed 1.5x
factor for samples in the lowest burden quartile of that fold's TRAIN
partition only. The quantile boundary is computed on fold-train alone, never
on validation, test or the full unsplit train set.

Burden is defined exactly as the existing ``sample__mutated_gene_count``
feature (src/open_cancer/mutation_features.py): the count of gene cells that
are not WT, using the same stop-notation-invariant parser EXP-374 already
uses as its mutation_cell_parser. It is computed directly by streaming
data/raw/train.csv (cheap, no need to go through the full Feature Factory),
then sliced by each fold's train row indices inside the
fold_sample_weight_multiplier hook -- run_hotspot_xgb.py itself never learns
about burden.
"""

from __future__ import annotations

import csv
from functools import partial

import numpy as np
import yaml

from open_cancer.abc_c_features import (
    fixed_pathway_burden_family,
    pathway_mutation_type_family,
)
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
    parse_stop_notation_invariant_token,
)
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, TRAIN_PATH, main


CONFIG = ROOT / "configs" / "exp516_burden_weighted_sample_weight.yaml"
MEMBERSHIP = (
    ROOT / "reports" / "exp374_stop_isoform_residue_mask" / "pathway_membership.json"
)
GENE_START_COLUMN = 2  # train.csv columns: ID, SUBCLASS, gene_0, gene_1, ...


def build_fold_features() -> PathwayMutationTypeFoldBuilder:
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
    return PathwayMutationTypeFoldBuilder(
        membership_path=MEMBERSHIP,
        burden_factory=burden,
        composition_factory=composition,
    )


def load_train_mutated_gene_count() -> np.ndarray:
    """Count non-WT gene cells per train row, in train.csv row order.

    Uses the same "cell has at least one non-WT token" rule as
    ``sample__mutated_gene_count`` in src/open_cancer/mutation_features.py
    with the stop-notation-invariant parser (a cell parses to zero tokens
    iff every whitespace-separated entry is empty or "WT", case
    insensitively). This matches the burden definition used in the EXP-374
    OOF error analysis that motivated Issue #516.
    """

    counts: list[int] = []
    with TRAIN_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.reader(file)
        next(reader)  # header
        for row in reader:
            mutated = 0
            for cell in row[GENE_START_COLUMN:]:
                if not cell:
                    continue
                if any(token.upper() != "WT" for token in cell.split()):
                    mutated += 1
            counts.append(mutated)
    return np.asarray(counts, dtype=np.float64)


def build_fold_sample_weight_multiplier(
    *,
    low_burden_quantile: float,
    multiplier_value: float,
):
    """Return the fold_sample_weight_multiplier hook for run_hotspot_xgb.main.

    The quantile boundary is computed on each fold's TRAIN indices only, so
    validation/test burden values never influence which samples get the
    extra weight (fold-safe by construction).
    """

    train_burden = load_train_mutated_gene_count()

    def _multiplier(
        *,
        fold: int,
        train_indices: np.ndarray,
        y_train: np.ndarray,
        base_sample_weight: np.ndarray,
    ) -> np.ndarray:
        del fold, y_train  # unused; burden threshold only depends on fold-train rows
        fold_train_burden = train_burden[train_indices]
        low_burden_threshold = np.quantile(fold_train_burden, low_burden_quantile)
        extra = np.where(fold_train_burden <= low_burden_threshold, multiplier_value, 1.0)
        return extra.astype(base_sample_weight.dtype, copy=False)

    return _multiplier


if __name__ == "__main__":
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    burden_config = config["training"]["burden_sample_weight"]
    if not burden_config["enabled"]:
        raise RuntimeError("EXP-516 config에서 burden_sample_weight.enabled가 false입니다.")
    main(
        CONFIG,
        fold_feature_builder=build_fold_features(),
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        fold_sample_weight_multiplier=build_fold_sample_weight_multiplier(
            low_burden_quantile=burden_config["low_burden_quantile"],
            multiplier_value=burden_config["multiplier"],
        ),
        runner_command="uv run python scripts/run_exp516_burden_weighted_sample_weight.py",
    )
