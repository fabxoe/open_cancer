#!/usr/bin/env python
"""Audit existing model OOF artifacts for ABC-Stack roadmap G4.

This is an explore-only analysis: it never trains, submits, or rewrites a
feature-spec configuration.  All inputs are pre-existing OOF/test probability
artifacts and are checked against the canonical prediction contract.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from open_cancer.portfolio_audit import (
    audit_record,
    audit_test_probability,
    load_and_audit_oof,
    pairwise_metrics,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = ROOT / "reports" / "analysis" / "g4_model_portfolio_audit.json"
OUTPUT_MD = ROOT / "reports" / "analysis" / "g4_model_portfolio_audit.md"
TASK_ISSUE = 133
EXPERIMENTS = {
    "EXP-094": "exp094_feature_spec_v1",
    "EXP-123": "exp123_sparse_logistic_v1",
    "EXP-125": "exp125_lightgbm_v1",
    "EXP-127": "exp127_catboost_v1",
    "EXP-131": "exp131_catboost_v1_extended",
}


def main() -> None:
    models = {
        experiment_id: load_and_audit_oof(
            experiment_id, ROOT / "oof" / f"{slug}.csv"
        )
        for experiment_id, slug in EXPERIMENTS.items()
    }
    test_records = {}
    reference_ids = None
    for experiment_id, slug in EXPERIMENTS.items():
        ids, record = audit_test_probability(
            experiment_id,
            ROOT / "preds" / f"{slug}_test_proba.csv",
            reference_ids=reference_ids,
        )
        if reference_ids is None:
            reference_ids = ids
            record["id_order_verified"] = True
        test_records[experiment_id] = record

    baseline = models["EXP-094"]
    records = {
        experiment_id: audit_record(model, baseline)
        for experiment_id, model in models.items()
    }
    pairwise = {
        left: {
            right: pairwise_metrics(models[left], models[right])
            for right in EXPERIMENTS
        }
        for left in EXPERIMENTS
    }
    eligible = [
        experiment_id
        for experiment_id, record in records.items()
        if experiment_id != "EXP-094"
        and record["gates"]["ensemble_quality_eligible"]
    ]
    diversity_candidates = [
        experiment_id
        for experiment_id in eligible
        if records[experiment_id]["gates"]["diversity"]
    ]
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task_issue": TASK_ISSUE,
        "run_mode": "explore",
        "score_role": "diagnostic_existing_oof_only",
        "baseline": "EXP-094",
        "selection_policy": {
            "quality_macro_f1_delta_min": -0.004,
            "wildcard_macro_f1_delta_min": -0.010,
            "wildcard_label_disagreement_min": 0.12,
            "ensemble_log_loss_delta_max": 0.01,
            "diversity_correctness_pearson_max": 0.92,
            "diversity_label_disagreement_min": 0.10,
        },
        "records": records,
        "test_probability_artifacts": test_records,
        "pairwise": pairwise,
        "selection": {
            "ensemble_quality_eligible": eligible,
            "diversity_candidates": diversity_candidates,
            "archive_only": [
                experiment_id
                for experiment_id in EXPERIMENTS
                if experiment_id != "EXP-094" and experiment_id not in eligible
            ],
            "public_lb_used": False,
            "test_distribution_used": False,
            "new_training_performed": False,
        },
    }
    OUTPUT_JSON.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    rows = []
    for experiment_id, record in records.items():
        metrics = record["metrics"]
        versus = record["versus_exp094"]
        gate = "PASS" if record["gates"]["ensemble_quality_eligible"] else "FAIL"
        rows.append(
            f"| {experiment_id} | {metrics['macro_f1']:.10f} | "
            f"{versus['macro_f1_delta']:+.10f} | {metrics['fold_std']:.10f} | "
            f"{metrics['log_loss']:.10f} | {versus['label_disagreement']:.4f} | "
            f"{versus['correctness_pearson']:.4f} | {gate} |"
        )
    OUTPUT_MD.write_text(
        "# G4 OOF 다양성·확률 품질 감사\n\n"
        "> Issue #133의 explore 분석입니다. 기존 OOF·test 확률만 사용했으며,\n"
        "> 새 학습·Public LB 제출·Feature Spec 변경을 수행하지 않았습니다.\n\n"
        "## 결론\n\n"
        f"- 앙상블 품질 gate 통과: {', '.join(eligible) or '없음'}\n"
        f"- 다양성 조건도 통과한 품질 후보: {', '.join(diversity_candidates) or '없음'}\n"
        f"- archive-only: {', '.join(result['selection']['archive_only'])}\n\n"
        "EXP-131은 EXP-094 대비 오류 다양성은 있지만 Log Loss가 허용 범위를 "
        "초과하고, EXP-127과 오류 상관이 높아 고정 blend 후보에서 제외합니다. "
        "G5에서는 품질 gate를 통과한 모델만 사전 고정 가중치로 비교해야 합니다.\n\n"
        "## 동일 OOF 기준 비교\n\n"
        "| 모델 | Macro F1 | EXP-094 대비 | Fold std | Log Loss | 라벨 불일치 | 정오답 상관 | 품질 gate |\n"
        "|---|---:|---:|---:|---:|---:|---:|---|\n"
        + "\n".join(rows)
        + "\n\n## 검증 범위\n\n"
        "- 모든 OOF는 ID·정답·fold·26개 확률 열과 확률 합을 검증했습니다.\n"
        "- 모든 test 확률은 행 수·확률 범위·ID 순서를 검증했습니다.\n"
        "- pairwise 결과에는 라벨 불일치, 오류 상태 Pearson, 확률 Pearson/Spearman을 기록했습니다.\n"
        "- test 분포, Public LB 점수, 제출 결과는 선택 기준으로 사용하지 않았습니다.\n\n"
        "## 다음 단계\n\n"
        "G4 결과를 기준으로 G5 고정 가중 확률 blend Issue를 별도로 발급합니다. "
        "첫 비교는 품질 gate 통과 모델과 EXP-094의 사전 고정 0.5/0.5 평균으로 하며, "
        "OOF 결과를 본 뒤 가중치를 조정하지 않습니다.\n",
        encoding="utf-8",
    )
    print(json.dumps(result["selection"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
