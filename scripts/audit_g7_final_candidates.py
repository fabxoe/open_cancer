#!/usr/bin/env python
"""Audit final candidate artifacts without training or leaderboard selection."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from open_cancer.hashing import sha256_file
from open_cancer.validation import validate_submission

ROOT = Path(__file__).resolve().parents[1]
ISSUE = 139
OUTPUT_JSON = ROOT / "reports/analysis/g7_final_candidate_audit.json"
OUTPUT_MD = ROOT / "reports/analysis/g7_final_candidate_audit.md"
CANDIDATES = {
    "EXP-131": {
        "metrics": "reports/exp131_catboost_v1_extended/metrics.json",
        "manifest": "reproducibility/exp131_catboost_v1_extended/artifact_manifest.json",
        "submission": "submissions/exp131_catboost_v1_extended.csv",
        "reason": "최고 Local OOF Macro F1",
    },
    "EXP-125": {
        "metrics": "reports/exp125_lightgbm_v1/metrics.json",
        "manifest": "reproducibility/exp125_lightgbm_v1/artifact_manifest.json",
        "submission": "submissions/exp125_lightgbm_v1.csv",
        "reason": "품질·다양성 gate 통과 및 Public 결과 보유",
    },
}


def main() -> None:
    records = {}
    for experiment_id, spec in CANDIDATES.items():
        metrics_path = ROOT / spec["metrics"]
        manifest_path = ROOT / spec["manifest"]
        submission_path = ROOT / spec["submission"]
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        artifact_paths = [ROOT / item["path"] for item in manifest.get("artifacts", [])]
        records[experiment_id] = {
            "reason": spec["reason"],
            "macro_f1": metrics["oof"]["macro_f1"],
            "fold_std": metrics["oof"].get("fold_std"),
            "log_loss": metrics["oof"].get("log_loss"),
            "public_score": (metrics.get("leaderboard") or {}).get("public_score"),
            "metrics_status": metrics["status"],
            "reproducibility_status": manifest["reproducibility_status"],
            "submission_sha256": sha256_file(submission_path),
            "artifact_files_present": all(path.is_file() for path in artifact_paths),
            "artifact_count": len(artifact_paths),
            "training_verified": manifest["reproducibility_status"] == "TRAINING_VERIFIED",
            "ready_for_independent_training": manifest["reproducibility_status"] != "TRAINING_VERIFIED",
        }
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task_issue": ISSUE,
        "run_mode": "task_audit",
        "training_performed": False,
        "public_lb_used_for_selection": False,
        "candidates": records,
        "selected_for_final_verification": ["EXP-131", "EXP-125"],
        "selection_reason": "Macro F1 최고 후보와 품질·Public 검증 후보를 각각 보존",
        "all_training_verified": all(item["training_verified"] for item in records.values()),
        "submission_checklist": {
            "candidate_count_at_most_two": True,
            "checkpoint_and_manifest_reviewed": all(item["artifact_files_present"] for item in records.values()),
            "independent_training_verified": False,
            "release_asset_archived": False,
            "leaderboard_submission_ready": False,
        },
    }
    OUTPUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = []
    for experiment_id, item in records.items():
        rows.append(f"| {experiment_id} | {item['macro_f1']:.10f} | {item['fold_std']:.10f} | {item['log_loss']:.10f} | {item['public_score'] if item['public_score'] is not None else '미제출'} | {item['reproducibility_status']} | {'통과' if item['artifact_files_present'] else '확인 필요'} |")
    OUTPUT_MD.write_text(
        "# G7 최종 후보 재현·제출 준비 감사\n\n"
        "> Issue #139의 task audit입니다. 새 학습과 Public LB 기반 선택을 수행하지 않았습니다.\n\n"
        "## 최종 후보\n\n"
        "최대 2개 제한에 따라 EXP-131과 EXP-125를 최종 독립 재현 검증 후보로 남깁니다. "
        "EXP-131은 Local Macro F1 최고 후보이고, EXP-125는 G4 품질·다양성 gate와 Public "
        "결과가 있는 보수적 후보입니다.\n\n"
        "| 실험 | OOF Macro F1 | Fold std | Log Loss | Public | 재현 상태 | 산출물 |\n"
        "|---|---:|---:|---:|---:|---|---|\n"
        + "\n".join(rows)
        + "\n\n## 현재 제한\n\n"
        "두 후보 모두 현재 `INFERENCE_VERIFIED`이며 `TRAINING_VERIFIED`가 아닙니다. "
        "따라서 수상 후보로 확정하거나 최종 제출하지 않습니다. 다른 팀원이 fresh clone에서 "
        "`uv sync --frozen` 후 재학습·checkpoint 추론까지 검증해야 합니다.\n\n"
        "## 다음 작업\n\n"
        "1. 두 후보의 Release asset과 SHA-256을 보관합니다.\n"
        "2. 작성자가 아닌 팀원이 독립 환경에서 재학습합니다.\n"
        "3. OOF/test 라벨 100%, 확률 허용범위, 제출 SHA-256을 확인합니다.\n"
        "4. `TRAINING_VERIFIED` 승격 후에만 리더보드 제출 후보로 확정합니다.\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
