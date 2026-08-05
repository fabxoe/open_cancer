"""Diversity gate audit: EXP-479 (native parser) vs the legacy-track lineage
(EXP-374, EXP-459, EXP-484) ahead of Task #489's blend propensity screening.

No new model training. Reuses existing OOF probability artifacts. Follows the
same error-correlation / label-disagreement definitions as
`scripts/audit_parser_v4_n4_results.py` and the stacking gate in
PROJECT_CONTEXT.md (correlation <= 0.92 or disagreement >= 10%).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
OOF_DIR = REPO_ROOT / "oof"
OUTPUT_DIR = REPO_ROOT / "reports/analysis/exp479_legacy_native_blend_propensity_screening"

BASE = ("EXP-479", "exp479_parser_v4_native_semantic_range")
OTHERS = (
    ("EXP-374", "exp374_stop_notation_isoform_mask"),
    ("EXP-459", "exp459_catboost_exp374"),
    ("EXP-484", "exp484_exp374_exp459_blend"),
)

CORRELATION_MAX = 0.92
DISAGREEMENT_MIN = 0.10


def main() -> None:
    base_name, base_slug = BASE
    base = pd.read_csv(OOF_DIR / f"{base_slug}.csv").set_index("ID")
    base_error = (base["SUBCLASS_PRED"] != base["SUBCLASS_TRUE"]).astype(float)

    pairs = []
    for name, slug in OTHERS:
        other = pd.read_csv(OOF_DIR / f"{slug}.csv").set_index("ID")
        other = other.loc[base.index]
        if not (other["SUBCLASS_TRUE"] == base["SUBCLASS_TRUE"]).all():
            raise ValueError(f"{name}: SUBCLASS_TRUE mismatch against {base_name}")
        other_error = (other["SUBCLASS_PRED"] != other["SUBCLASS_TRUE"]).astype(float)
        correlation = float(np.corrcoef(base_error, other_error)[0, 1])
        disagreement = float((base["SUBCLASS_PRED"] != other["SUBCLASS_PRED"]).mean())
        gate_pass = bool(correlation <= CORRELATION_MAX or disagreement >= DISAGREEMENT_MIN)
        pairs.append(
            {
                "compared_to": name,
                "oof_error_correlation": correlation,
                "prediction_label_disagreement": disagreement,
                "gate_pass": gate_pass,
            }
        )

    result = {
        "base_experiment": base_name,
        "correlation_max_threshold": CORRELATION_MAX,
        "disagreement_min_threshold": DISAGREEMENT_MIN,
        "pairs": pairs,
        "all_pairs_pass": all(p["gate_pass"] for p in pairs),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUTPUT_DIR / "diversity_gate.json").open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
