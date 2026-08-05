#!/usr/bin/env python
"""Diagnostic ratio sweep for Issue #464 (EXP-374 x EXP-449 blend).

Pure OOF/test recombination, no retraining. Computes, for each candidate
(EXP-374, EXP-449) weight pair, the overall OOF Macro F1, fold std,
worst-class delta, and the mandatory test-like subset (#292 propensity)
Macro F1 delta -- the primary judgment criterion per Issue #464. This is
a read-only comparison script; the ratio ultimately adopted (if any) is
recorded as a separate official EXP-464 run via
scripts/run_exp464_blend_ratio_sweep.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

from open_cancer.constants import CLASS_LABELS

ROOT = Path(__file__).resolve().parents[1]
EXP374_OOF_PATH = ROOT / "oof/exp374_stop_isoform_residue_mask.csv"
EXP449_OOF_PATH = ROOT / "oof/exp449_lightgbm_exp374.csv"
PROPENSITY_PATH = ROOT / "reports/analysis/adversarial_validation/train_domain_propensity.csv"
OUT_PATH = ROOT / "reports/exp464_blend_ratio_sweep/sweep_results.json"

RATIOS = [(0.9, 0.1), (0.8, 0.2), (0.7, 0.3), (0.6, 0.4)]
PROBA_COLS = [f"PROBA_{c}" for c in CLASS_LABELS]


def main() -> None:
    exp374 = pd.read_csv(EXP374_OOF_PATH, dtype={"ID": str}).set_index("ID")
    exp449 = pd.read_csv(EXP449_OOF_PATH, dtype={"ID": str}).set_index("ID")
    if not exp374.index.equals(exp449.index) or not exp374["SUBCLASS_TRUE"].equals(exp449["SUBCLASS_TRUE"]):
        raise ValueError("EXP-374/EXP-449 OOF의 ID·정답이 정렬되지 않았습니다.")

    propensity = pd.read_csv(PROPENSITY_PATH).set_index("ID")
    propensity_aligned = propensity.loc[exp374.index]
    threshold = float(propensity["oof_test_domain_probability"].quantile(0.75))
    test_like_mask = (propensity_aligned["oof_test_domain_probability"] >= threshold).to_numpy()

    label_to_idx = {c: i for i, c in enumerate(CLASS_LABELS)}
    true_idx = exp374["SUBCLASS_TRUE"].map(label_to_idx).to_numpy()
    p374 = exp374[PROBA_COLS].to_numpy(dtype=float)
    p449 = exp449[PROBA_COLS].to_numpy(dtype=float)
    fold = exp374["FOLD"].to_numpy()

    exp374_pred = p374.argmax(axis=1)
    exp374_overall = float(f1_score(true_idx, exp374_pred, average="macro"))
    exp374_test_like = float(f1_score(true_idx[test_like_mask], exp374_pred[test_like_mask], average="macro"))
    exp374_per_class = f1_score(true_idx, exp374_pred, average=None, labels=range(len(CLASS_LABELS)))

    results = []
    for w374, w449 in RATIOS:
        blended = w374 * p374 + w449 * p449
        pred = blended.argmax(axis=1)
        fold_f1 = [
            float(f1_score(true_idx[fold == f], pred[fold == f], average="macro", labels=range(len(CLASS_LABELS)), zero_division=0))
            for f in sorted(np.unique(fold))
        ]
        overall = float(f1_score(true_idx, pred, average="macro"))
        test_like = float(f1_score(true_idx[test_like_mask], pred[test_like_mask], average="macro"))
        per_class = f1_score(true_idx, pred, average=None, labels=range(len(CLASS_LABELS)), zero_division=0)
        per_class_delta = per_class - exp374_per_class
        worst_idx = int(np.argmin(per_class_delta))
        results.append(
            {
                "weights": {"EXP-374": w374, "EXP-449": w449},
                "oof_macro_f1": overall,
                "oof_macro_f1_delta_vs_exp374": overall - exp374_overall,
                "fold_std": float(np.std(fold_f1)),
                "test_like_macro_f1": test_like,
                "test_like_delta_vs_exp374": test_like - exp374_test_like,
                "worst_class": CLASS_LABELS[worst_idx],
                "worst_class_delta": float(per_class_delta[worst_idx]),
                "verdict": "PASS" if (test_like - exp374_test_like) >= 0 else "FAIL_test_like_regression",
            }
        )

    output = {
        "purpose": "ratio_sweep_diagnostic",
        "issue": 464,
        "base_experiments": ["EXP-374", "EXP-449"],
        "exp374_reference": {"oof_macro_f1": exp374_overall, "test_like_macro_f1": exp374_test_like},
        "propensity_source": "reports/analysis/adversarial_validation/train_domain_propensity.csv",
        "test_like_threshold_quantile": 0.75,
        "test_like_threshold_value": threshold,
        "n_test_like": int(test_like_mask.sum()),
        "ratios": results,
        "any_ratio_passes_test_like": any(item["verdict"] == "PASS" for item in results),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
