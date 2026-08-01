#!/usr/bin/env python
"""Audit the frozen ABC-Stack OOF portfolio without training a model."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from open_cancer.portfolio_audit import (
    audit_record,
    audit_test_probability,
    load_and_audit_oof,
    pairwise_metrics,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON = ROOT / "reports" / "analysis" / "abc_oof_portfolio_audit.json"
OUTPUT_MD = ROOT / "reports" / "analysis" / "abc_oof_portfolio_audit.md"
SPEC_PATH = ROOT / "configs" / "abc_stack_feature_spec_v2.yaml"
EXPERIMENTS = {
    "EXP-094": "exp094_feature_spec_v1",
    "EXP-096": "exp096_fixed_pathway_burden",
    "EXP-106": "exp106_recurrent_exact_token",
    "EXP-107": "exp107_amino_acid_change",
    "EXP-109": "exp109_complex_morphology",
    "EXP-110": "exp110_frequency_tier_spectrum",
}


def main() -> None:
    models = {
        experiment_id: load_and_audit_oof(
            experiment_id,
            ROOT / "oof" / f"{slug}.csv",
        )
        for experiment_id, slug in EXPERIMENTS.items()
    }
    test_records = {}
    reference_test_ids = None
    for experiment_id, slug in EXPERIMENTS.items():
        test_ids, test_record = audit_test_probability(
            experiment_id,
            ROOT / "preds" / f"{slug}_test_proba.csv",
            reference_ids=reference_test_ids,
        )
        if reference_test_ids is None:
            reference_test_ids = test_ids
            test_record["id_order_verified"] = True
        test_records[experiment_id] = test_record
    baseline = models["EXP-094"]
    records = {
        experiment_id: audit_record(model, baseline)
        for experiment_id, model in models.items()
    }
    eligible = [
        experiment_id
        for experiment_id, record in records.items()
        if experiment_id != "EXP-094"
        and record["gates"]["ensemble_quality_eligible"]
    ]
    performance = max(
        (experiment_id for experiment_id in eligible if records[experiment_id]["metrics"]["macro_f1"] > baseline.metrics["macro_f1"]),
        key=lambda experiment_id: records[experiment_id]["metrics"]["macro_f1"],
    )
    diversity_candidates = [
        experiment_id
        for experiment_id in eligible
        if experiment_id != performance and records[experiment_id]["gates"]["diversity"]
    ]
    diversity = min(
        diversity_candidates,
        key=lambda experiment_id: (
            records[experiment_id]["versus_exp094"]["correctness_pearson"],
            records[experiment_id]["versus_exp094"]["probability_pearson"],
        ),
    )
    pairwise = {
        left: {
            right: pairwise_metrics(models[left], models[right])
            for right in EXPERIMENTS
        }
        for left in EXPERIMENTS
    }
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task_issue": 119,
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
            "v2_performance_evidence": performance,
            "v2_diversity_evidence": diversity,
            "ensemble_quality_eligible": eligible,
            "archive_only": [
                experiment_id
                for experiment_id in EXPERIMENTS
                if experiment_id != "EXP-094" and experiment_id not in eligible
            ],
        },
    }
    diversity_record = records[diversity]["versus_exp094"]
    diversity_gains = sorted(
        diversity_record["per_class_f1_delta"].items(),
        key=lambda item: item[1],
        reverse=True,
    )[:5]
    OUTPUT_JSON.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    spec = {
        "status": "FROZEN",
        "task_issue": 119,
        "baseline": {
            "experiment_id": "EXP-094",
            "feature_spec_sha256": "1fba3a7dac9f9b2a76deb5bec4c1099f650153b82c64d48e476dc1f2f84f3ed3",
        },
        "v2_performance": {
            "evidence_experiment": performance,
            "base": "EXP-094",
            "families": ["fixed_pathway_burden"],
            "source_config": "configs/exp096_fixed_pathway_burden.yaml",
        },
        "v2_diversity": {
            "evidence_experiment": diversity,
            "base": "EXP-094",
            "families": [
                {
                    "EXP-106": "recurrent_exact_token",
                    "EXP-107": "amino_acid_change",
                    "EXP-109": "complex_morphology",
                    "EXP-110": "frequency_tier_spectrum",
                }[diversity]
            ],
            "source_config": {
                "EXP-106": "configs/exp106_recurrent_exact_token.yaml",
                "EXP-107": "configs/exp107_amino_acid_change.yaml",
                "EXP-109": "configs/exp109_complex_morphology.yaml",
                "EXP-110": "configs/exp110_frequency_tier_spectrum.yaml",
            }[diversity],
        },
        "selection_evidence": "reports/analysis/abc_oof_portfolio_audit.json",
        "constraints": {
            "public_lb_used": False,
            "test_distribution_used": False,
            "new_training_performed": False,
            "official_experiment_created": False,
        },
    }
    SPEC_PATH.write_text(
        yaml.safe_dump(spec, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    rows = []
    for experiment_id, record in records.items():
        metrics = record["metrics"]
        versus = record["versus_exp094"]
        rows.append(
            f"| {experiment_id} | {metrics['macro_f1']:.10f} | "
            f"{versus['macro_f1_delta']:+.10f} | {metrics['fold_std']:.10f} | "
            f"{metrics['log_loss']:.10f} | {versus['label_disagreement']:.4f} | "
            f"{versus['correctness_pearson']:.4f} | "
            f"{'PASS' if record['gates']['ensemble_quality_eligible'] else 'FAIL'} |"
        )
    OUTPUT_MD.write_text(
        "# ABC-Stack OOF 포트폴리오 감사\n\n"
        "> Issue #119의 explore 분석입니다. 새 학습·공식 EXP·Public LB 선택을 수행하지 않았습니다.\n\n"
        "## 결론\n\n"
        f"- v2-performance 근거: **{performance}** (`fixed_pathway_burden`)\n"
        f"- v2-diversity 근거: **{diversity}**\n"
        f"- 앙상블 품질 통과: {', '.join(eligible)}\n"
        f"- archive only: {', '.join(result['selection']['archive_only'])}\n\n"
        f"{diversity}는 EXP-094 대비 라벨 불일치 "
        f"`{diversity_record['label_disagreement']:.4f}`, 정오답 상관 "
        f"`{diversity_record['correctness_pearson']:.4f}`이며, 큰 클래스 개선은 "
        + ", ".join(f"{label} `{delta:+.4f}`" for label, delta in diversity_gains)
        + "입니다.\n\n"
        "## 동일 OOF 기준 비교\n\n"
        "| 모델 | Macro F1 | EXP-094 대비 | Fold std | Log Loss | 라벨 불일치 | 정오답 상관 | 품질 gate |\n"
        "|---|---:|---:|---:|---:|---:|---:|---|\n"
        + "\n".join(rows)
        + "\n\n## 해석\n\n"
        "v2-performance는 유일하게 기준보다 사전 임계값 이상 개선된 C family를 사용합니다. "
        "v2-diversity는 품질 하한을 통과한 후보 중 EXP-094와 정오답 상관, 확률 상관이 "
        "가장 낮은 family를 고정했습니다. EXP-110은 독립성은 크지만 성능·Log Loss 하한을 "
        "통과하지 못해 archive-only입니다.\n\n"
        "다음 공식 단계에서는 이 사양을 바꾸지 않고 모델별 Experiment Issue를 발급합니다. "
        "고정 blend나 stacking은 별도 Experiment Issue에서만 공식 결과로 기록합니다.\n",
        encoding="utf-8",
    )
    print(json.dumps(result["selection"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
