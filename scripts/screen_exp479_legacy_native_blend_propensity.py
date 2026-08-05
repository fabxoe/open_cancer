"""Screen fixed EXP-484 (legacy)+EXP-479 (native) blend ratios against the #292
test-like propensity subset before proposing a formal blend Experiment Issue.

No new model training. Reuses existing OOF probability artifacts (EXP-479
reproduced locally in an isolated worktree at source commit 8a6010d, byte-level
match confirmed against the recorded OOF Macro F1) and the analysis-only
`train_domain_propensity.csv` from #292. SUBCLASS is used only to score Macro F1
(already present in the OOF files); Public LB and test features are not touched
here beyond the pre-existing #292 propensity column.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

REPO_ROOT = Path(__file__).resolve().parents[1]
PROPENSITY_PATH = (
    REPO_ROOT / "reports/analysis/adversarial_validation/train_domain_propensity.csv"
)
EXP484_OOF_PATH = REPO_ROOT / "oof/exp484_exp374_exp459_blend.csv"
EXP479_OOF_PATH = REPO_ROOT / "oof/exp479_parser_v4_native_semantic_range.csv"
OUTPUT_DIR = REPO_ROOT / "reports/analysis/exp479_legacy_native_blend_propensity_screening"

TEST_LIKE_QUANTILE = 0.75
BLEND_WEIGHTS_ON_484 = [0.9, 0.8, 0.7, 0.6, 0.5]

CLASS_LABELS = [
    "ACC", "BLCA", "BRCA", "CESC", "COAD", "DLBC", "GBMLGG", "HNSC", "KIPAN",
    "KIRC", "LAML", "LGG", "LIHC", "LUAD", "LUSC", "OV", "PAAD", "PCPG",
    "PRAD", "SARC", "SKCM", "STES", "TGCT", "THCA", "THYM", "UCEC",
]
PROBA_COLS = [f"PROBA_{c}" for c in CLASS_LABELS]


def macro_f1(y_true: pd.Series, y_pred: np.ndarray) -> float:
    return float(f1_score(y_true, y_pred, average="macro", labels=CLASS_LABELS))


def main() -> None:
    propensity = pd.read_csv(PROPENSITY_PATH).set_index("ID")
    oof_484 = pd.read_csv(EXP484_OOF_PATH).set_index("ID")
    oof_479 = pd.read_csv(EXP479_OOF_PATH).set_index("ID")

    assert list(oof_484.index) == list(oof_479.index), "ID order mismatch between OOF files"
    assert (oof_484["SUBCLASS_TRUE"] == oof_479["SUBCLASS_TRUE"]).all(), "label mismatch"
    assert set(propensity.index) == set(oof_484.index), "propensity/OOF ID set mismatch"

    propensity = propensity.loc[oof_484.index]
    threshold = float(propensity["oof_test_domain_probability"].quantile(TEST_LIKE_QUANTILE))
    test_like_mask = (propensity["oof_test_domain_probability"] >= threshold).to_numpy()

    y_true = oof_484["SUBCLASS_TRUE"]
    proba_484 = oof_484[PROBA_COLS].to_numpy()
    proba_479 = oof_479[PROBA_COLS].to_numpy()

    pred_484 = np.array(CLASS_LABELS)[proba_484.argmax(axis=1)]
    baseline_full = macro_f1(y_true, pred_484)
    baseline_test_like = macro_f1(y_true[test_like_mask], pred_484[test_like_mask])

    rows = []
    for w in BLEND_WEIGHTS_ON_484:
        blended = w * proba_484 + (1 - w) * proba_479
        pred_blend = np.array(CLASS_LABELS)[blended.argmax(axis=1)]

        full_f1 = macro_f1(y_true, pred_blend)
        test_like_f1 = macro_f1(y_true[test_like_mask], pred_blend[test_like_mask])

        rows.append(
            {
                "weight_exp484": w,
                "weight_exp479": round(1 - w, 2),
                "full_oof_macro_f1": full_f1,
                "full_oof_delta_vs_exp484": full_f1 - baseline_full,
                "test_like_macro_f1": test_like_f1,
                "test_like_delta_vs_exp484": test_like_f1 - baseline_test_like,
                "test_like_gate_pass": bool(test_like_f1 - baseline_test_like >= 0),
            }
        )

    any_pass = any(row["test_like_gate_pass"] for row in rows)

    result = {
        "propensity_source": str(PROPENSITY_PATH.relative_to(REPO_ROOT)),
        "exp484_oof_source": str(EXP484_OOF_PATH.relative_to(REPO_ROOT)),
        "exp479_oof_source": str(EXP479_OOF_PATH.relative_to(REPO_ROOT)),
        "test_like_quantile": TEST_LIKE_QUANTILE,
        "test_like_threshold": threshold,
        "test_like_row_count": int(test_like_mask.sum()),
        "total_row_count": int(len(y_true)),
        "exp484_baseline_full_oof_macro_f1": baseline_full,
        "exp484_baseline_test_like_macro_f1": baseline_test_like,
        "ratios": rows,
        "any_ratio_passes_test_like_gate": any_pass,
        "recommendation": (
            "at least one ratio passes the test-like gate -- propose a formal "
            "blend Experiment Issue with that ratio as the starting point"
            if any_pass
            else "no ratio passes the test-like gate -- do not pursue further "
            "EXP-484+EXP-479 (legacy+native) blend attempts"
        ),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUTPUT_DIR / "screening.json").open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
