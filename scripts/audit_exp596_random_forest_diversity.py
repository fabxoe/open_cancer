#!/usr/bin/env python
"""Resolve the EXP-596 (RandomForest v1) #505 S0 diversity-gate verdict.

Explore-only analysis: it never trains, submits, or rewrites a feature-spec
configuration. Baseline is EXP-127 (CatBoost v1, the best v1-family model);
EXP-125 (LightGBM v1) is included as a secondary pairwise check. EXP-123
(Logistic v1) is included only if its OOF is present locally.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from open_cancer.portfolio_audit import audit_record, load_and_audit_oof, pairwise_metrics

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = ROOT / "reports" / "analysis" / "exp596_random_forest_diversity_audit.json"
OUTPUT_MD = ROOT / "reports" / "analysis" / "exp596_random_forest_diversity_audit.md"
CANDIDATE = ("EXP-596", "exp596_random_forest_v1")
BASELINE = ("EXP-127", "exp127_catboost_v1")
SECONDARY = [("EXP-125", "exp125_lightgbm_v1"), ("EXP-123", "exp123_sparse_logistic_v1")]


def main() -> None:
    candidate = load_and_audit_oof(CANDIDATE[0], ROOT / "oof" / f"{CANDIDATE[1]}.csv")
    baseline = load_and_audit_oof(BASELINE[0], ROOT / "oof" / f"{BASELINE[1]}.csv")
    record = audit_record(candidate, baseline)

    secondary_pairwise = {}
    for experiment_id, slug in SECONDARY:
        path = ROOT / "oof" / f"{slug}.csv"
        if not path.exists():
            secondary_pairwise[experiment_id] = {"skipped": "oof file not present locally"}
            continue
        peer = load_and_audit_oof(experiment_id, path)
        secondary_pairwise[experiment_id] = pairwise_metrics(peer, candidate)

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "issue": 505,
        "run_mode": "explore",
        "score_role": "diagnostic_existing_oof_only",
        "baseline": BASELINE[0],
        "selection_policy": {
            "quality_macro_f1_delta_min": -0.004,
            "diversity_correctness_pearson_max": 0.92,
            "diversity_label_disagreement_min": 0.10,
        },
        "record": record,
        "secondary_pairwise_vs_exp596": secondary_pairwise,
        "verdict": {
            "quality_gate": record["gates"]["quality"],
            "diversity_gate": record["gates"]["diversity"],
            "s0_stacking_candidate": record["gates"]["quality"] or record["gates"]["diversity"],
        },
    }
    OUTPUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    versus = record["versus_exp094"]
    verdict = result["verdict"]
    OUTPUT_MD.write_text(
        "# EXP-596 RandomForest v1 — #505 S0 다양성 게이트 판정\n\n"
        "> Issue #596/PR #598 코멘트에서 보류했던 판정입니다. 기존 OOF만 사용했고,\n"
        "> 새 학습·Public LB 제출을 수행하지 않았습니다.\n\n"
        f"- 기준 모델: {BASELINE[0]} (v1 계열 최고)\n"
        f"- Macro F1 delta: {versus['macro_f1_delta']:+.10f} "
        f"(품질 gate 0.004 이내 여부: {'PASS' if record['gates']['quality'] else 'FAIL'})\n"
        f"- 오류(정오답) 상관: {versus['correctness_pearson']:.4f} "
        f"(다양성 gate ≤0.92 여부: {'PASS' if versus['correctness_pearson'] <= 0.92 else 'FAIL'})\n"
        f"- 라벨 불일치율: {versus['label_disagreement']:.4f} "
        f"(다양성 gate ≥0.10 여부: {'PASS' if versus['label_disagreement'] >= 0.10 else 'FAIL'})\n"
        f"- 종합 다양성 gate: {'PASS' if record['gates']['diversity'] else 'FAIL'}\n\n"
        f"## 최종 판정: {'S0 스태킹 후보로 채택' if verdict['s0_stacking_candidate'] else 'ARCHIVE'}\n\n"
        "## 보조 비교 (EXP-596 vs 다른 v1 후보)\n\n"
        + "\n".join(
            f"- {experiment_id}: "
            + (
                f"라벨 불일치 {metrics['label_disagreement']:.4f}, "
                f"정오답 상관 {metrics['correctness_pearson']:.4f}"
                if "skipped" not in metrics
                else metrics["skipped"]
            )
            for experiment_id, metrics in secondary_pairwise.items()
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["verdict"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
