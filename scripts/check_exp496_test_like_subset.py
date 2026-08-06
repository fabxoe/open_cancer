#!/usr/bin/env python
"""Mandatory completion-condition check for EXP-496 (Issue #496).

Compares EXP-496 (EXP-374 with sample__complex_count replaced by the robust
non-simple event gene count) against its EXP-374 parent on the
train_domain_propensity.csv (#292) top-quartile "test-like" subset -- same
boundary as EXP-351/450/457/464/465/484, read-only diagnostic use only.
This is the primary judgment criterion for EXP-496 (raw sample__complex_count
is the #1 gain feature in the #292 domain-shift diagnostic).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import f1_score

from open_cancer.constants import CLASS_LABELS

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_OOF_PATH = ROOT / "oof" / "exp496_robust_complex_count_exp374.csv"
EXP374_OOF_PATH = ROOT / "oof" / "exp374_stop_isoform_residue_mask.csv"
PROPENSITY_PATH = ROOT / "reports" / "analysis" / "adversarial_validation" / "train_domain_propensity.csv"
OUT_PATH = ROOT / "reports" / "exp496_robust_complex_count_exp374" / "test_like_subset_check.json"


def main() -> None:
    candidate_oof = pd.read_csv(CANDIDATE_OOF_PATH).set_index("ID")
    exp374_oof = pd.read_csv(EXP374_OOF_PATH).set_index("ID")
    exp374_oof = exp374_oof.rename(columns={f"PROBA_{c}": c for c in CLASS_LABELS})

    propensity = pd.read_csv(PROPENSITY_PATH).set_index("ID")
    ids = candidate_oof.index
    propensity_aligned = propensity.loc[ids]
    threshold = float(propensity["oof_test_domain_probability"].quantile(0.75))
    test_like_mask = (propensity_aligned["oof_test_domain_probability"] >= threshold).to_numpy()

    label_to_idx = {c: i for i, c in enumerate(CLASS_LABELS)}
    true_idx = candidate_oof["SUBCLASS_TRUE"].map(label_to_idx).to_numpy()

    candidate_proba_cols = [f"PROBA_{c}" for c in CLASS_LABELS]
    candidate_pred = candidate_oof[candidate_proba_cols].to_numpy().argmax(axis=1)
    exp374_aligned = exp374_oof.loc[ids]
    exp374_pred = exp374_aligned[list(CLASS_LABELS)].to_numpy().argmax(axis=1)

    candidate_f1 = f1_score(true_idx, candidate_pred, average=None, labels=range(len(CLASS_LABELS)), zero_division=0)
    exp374_f1 = f1_score(true_idx, exp374_pred, average=None, labels=range(len(CLASS_LABELS)), zero_division=0)
    per_class_delta = candidate_f1 - exp374_f1
    worst_idx = int(per_class_delta.argmin())

    result = {
        "purpose": "mandatory_completion_condition",
        "issue": 496,
        "propensity_source": "reports/analysis/adversarial_validation/train_domain_propensity.csv",
        "propensity_use": "read_only_diagnostic_subset_selector",
        "test_or_public_used_for_selection": False,
        "test_like_threshold_quantile": 0.75,
        "test_like_threshold_value": threshold,
        "n_test_like": int(test_like_mask.sum()),
        "overall": {
            "candidate_macro_f1": float(f1_score(true_idx, candidate_pred, average="macro")),
            "exp374_macro_f1": float(f1_score(true_idx, exp374_pred, average="macro")),
        },
        "test_like_subset": {
            "candidate_macro_f1": float(
                f1_score(true_idx[test_like_mask], candidate_pred[test_like_mask], average="macro")
            ),
            "exp374_macro_f1": float(
                f1_score(true_idx[test_like_mask], exp374_pred[test_like_mask], average="macro")
            ),
        },
        "worst_class": {"label": CLASS_LABELS[worst_idx], "delta": float(per_class_delta[worst_idx])},
    }
    result["overall"]["delta"] = result["overall"]["candidate_macro_f1"] - result["overall"]["exp374_macro_f1"]
    result["test_like_subset"]["delta"] = (
        result["test_like_subset"]["candidate_macro_f1"] - result["test_like_subset"]["exp374_macro_f1"]
    )
    result["verdict"] = (
        "PASS" if result["test_like_subset"]["delta"] >= 0 else "FAIL_test_like_regression"
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
