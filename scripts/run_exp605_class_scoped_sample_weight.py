#!/usr/bin/env python
"""Run EXP-605: EXP-374 + fold-safe class-scoped sample weight multiplier.

Single change vs EXP-374 (see configs/exp605_class_scoped_sample_weight.yaml
and Issue #605): multiply the existing balanced_sample_weight by a fixed
1.2x factor for fold-train rows whose train SUBCLASS is one of 8
pre-declared low-burden/high-misclassification classes (KIRC, KIPAN,
GBMLGG, SARC, PRAD, PCPG, THYM, LAML). This list was already fixed in the
EXP-374 OOF error analysis that motivated EXP-516 -- it is not re-selected
from EXP-516's own result.

This is a direct follow-up to EXP-516 (ARCHIVE), which used a burden
quantile (fold-train lowest 25% of ``sample__mutated_gene_count``,
class-agnostic) instead of class membership to pick which rows get the
extra weight. EXP-516's post-hoc analysis found that the quantile criterion
did not respect class boundaries: samples that were merely low-burden *for
their own (typically high-burden) class*, such as LUAD and BLCA, also
picked up the extra weight and took the largest collateral damage
(LUAD -0.064, DLBC -0.050, BLCA -0.050), even though none of the three were
hypothesis targets. Class membership instead of a burden threshold
structurally prevents that mechanism: only rows already labelled as one of
the 8 target classes in fold-train can receive the extra multiplier, so
LUAD/BLCA/DLBC rows are never touched directly by this hook.

``y_train`` is the integer-encoded class label produced by
``LabelEncoder().fit(list(CLASS_LABELS))`` in run_hotspot_xgb.py. Because
``open_cancer.constants.CLASS_LABELS`` is already alphabetically sorted,
that encoder's ``classes_`` order equals ``CLASS_LABELS`` itself, so each
class index is simply ``CLASS_LABELS.index(name)``.
"""

from __future__ import annotations

from functools import partial

import numpy as np
import yaml

from open_cancer.abc_c_features import (
    fixed_pathway_burden_family,
    pathway_mutation_type_family,
)
from open_cancer.constants import CLASS_LABELS
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
    parse_stop_notation_invariant_token,
)
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp605_class_scoped_sample_weight.yaml"
# NOTE: intentionally an EXP-605-local path, not EXP-374's own committed
# report path -- see scripts/run_exp516_burden_weighted_sample_weight.py for
# why pointing MEMBERSHIP at another experiment's committed report is a
# recurring worktree-cleanliness bug in this family of runners.
MEMBERSHIP = (
    ROOT / "reports" / "exp605_class_scoped_sample_weight" / "pathway_membership.json"
)


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


def resolve_target_class_indices(target_classes: list[str]) -> np.ndarray:
    """Map pre-declared class names to their CLASS_LABELS integer index.

    ``CLASS_LABELS`` is alphabetically sorted, matching
    ``LabelEncoder().fit(list(CLASS_LABELS)).classes_`` exactly, so the
    index within ``CLASS_LABELS`` is the same integer ``y_train`` uses.
    """

    unknown = sorted(set(target_classes) - set(CLASS_LABELS))
    if unknown:
        raise ValueError(f"configs의 target_classes에 알 수 없는 클래스가 있습니다: {unknown}")
    return np.asarray(
        sorted(CLASS_LABELS.index(name) for name in target_classes), dtype=np.int64
    )


def build_fold_sample_weight_multiplier(
    *,
    target_class_indices: np.ndarray,
    multiplier_value: float,
):
    """Return the fold_sample_weight_multiplier hook for run_hotspot_xgb.main.

    Membership is read directly from ``y_train`` (the fold's own train
    labels), so no validation/test information is used and no extra
    fold-train-only fit step is required -- unlike EXP-516's burden
    quantile, class membership needs no boundary estimation at all.
    """

    target_set = set(int(idx) for idx in target_class_indices)

    def _multiplier(
        *,
        fold: int,
        train_indices: np.ndarray,
        y_train: np.ndarray,
        base_sample_weight: np.ndarray,
    ) -> np.ndarray:
        del fold, train_indices  # unused; membership only depends on y_train
        is_target = np.isin(y_train, list(target_set))
        extra = np.where(is_target, multiplier_value, 1.0)
        return extra.astype(base_sample_weight.dtype, copy=False)

    return _multiplier


if __name__ == "__main__":
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    weight_config = config["training"]["class_scoped_sample_weight"]
    if not weight_config["enabled"]:
        raise RuntimeError("EXP-605 config에서 class_scoped_sample_weight.enabled가 false입니다.")
    target_indices = resolve_target_class_indices(weight_config["target_classes"])
    main(
        CONFIG,
        fold_feature_builder=build_fold_features(),
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        fold_sample_weight_multiplier=build_fold_sample_weight_multiplier(
            target_class_indices=target_indices,
            multiplier_value=weight_config["multiplier"],
        ),
        runner_command="uv run python scripts/run_exp605_class_scoped_sample_weight.py",
    )
