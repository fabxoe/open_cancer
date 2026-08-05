#!/usr/bin/env python
"""Mandatory completion-condition check for EXP-450 (Issue #450).

Compares the EXP-450 blend against its EXP-374 component on the
train_domain_propensity.csv (#292) top-quartile "test-like" subset, to
catch an EXP-253-style Local-pass/Public-fail pattern before any Public
submission decision. Read-only diagnostic use of propensity, same boundary
as EXP-351's finalization -- never used to select features, weights, or
training rows.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sklearn.metrics import f1_score

from open_cancer.constants import CLASS_LABELS

ROOT = Path(__file__).resolve().parents[1]
BLEND_OOF_PATH = ROOT / "oof" / "exp450_lightgbm_exp374_blend.csv"
EXP374_OOF_PATH = ROOT / "oof" / "exp374_stop_isoform_residue_mask.csv"
PROPENSITY_PATH = ROOT / "reports" / "analysis" / "adversarial_validation" / "train_domain_propensity.csv"
OUT_PATH = ROOT / "reports" / "exp450_lightgbm_exp374_blend" / "test_like_subset_check.json"


def main() -> None:
    blend_oof = pd.read_csv(BLEND_OOF_PATH).set_index("ID")
    exp374_oof = pd.read_csv(EXP374_OOF_PATH).set_index("ID")
    exp374_oof = exp374_oof.rename(columns={f"PROBA_{c}": c for c in CLASS_LABELS})

    propensity = pd.read_csv(PROPENSITY_PATH).set_index("ID")
    ids = blend_oof.index
    propensity_aligned = propensity.loc[ids]
    threshold = float(propensity["oof_test_domain_probability"].quantile(0.75))
    test_like_mask = (propensity_aligned["oof_test_domain_probability"] >= threshold).to_numpy()

    label_to_idx = {c: i for i, c in enumerate(CLASS_LABELS)}
    true_idx = blend_oof["SUBCLASS_TRUE"].map(label_to_idx).to_numpy()

    blend_proba_cols = [f"PROBA_{c}" for c in CLASS_LABELS]
    blend_pred = blend_oof[blend_proba_cols].to_numpy().argmax(axis=1)
    exp374_aligned = exp374_oof.loc[ids]
    exp374_pred = exp374_aligned[list(CLASS_LABELS)].to_numpy().argmax(axis=1)

    result = {
        "purpose": "mandatory_completion_condition",
        "issue": 450,
        "propensity_source": "reports/analysis/adversarial_validation/train_domain_propensity.csv",
        "propensity_use": "read_only_diagnostic_subset_selector",
        "test_or_public_used_for_selection": False,
        "test_like_threshold_quantile": 0.75,
        "test_like_threshold_value": threshold,
        "n_test_like": int(test_like_mask.sum()),
        "overall": {
            "blend_macro_f1": float(f1_score(true_idx, blend_pred, average="macro")),
            "exp374_macro_f1": float(f1_score(true_idx, exp374_pred, average="macro")),
        },
        "test_like_subset": {
            "blend_macro_f1": float(
                f1_score(true_idx[test_like_mask], blend_pred[test_like_mask], average="macro")
            ),
            "exp374_macro_f1": float(
                f1_score(true_idx[test_like_mask], exp374_pred[test_like_mask], average="macro")
            ),
        },
    }
    result["overall"]["delta"] = result["overall"]["blend_macro_f1"] - result["overall"]["exp374_macro_f1"]
    result["test_like_subset"]["delta"] = (
        result["test_like_subset"]["blend_macro_f1"] - result["test_like_subset"]["exp374_macro_f1"]
    )
    result["verdict"] = (
        "PASS" if result["test_like_subset"]["delta"] >= 0 else "FAIL_test_like_regression"
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
