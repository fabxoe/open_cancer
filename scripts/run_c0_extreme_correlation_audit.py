#!/usr/bin/env python
"""Record the C0 extreme mutation-presence redundancy diagnostic.

This is Issue #187's analysis-only step.  It does not create an EXP-ID, fit a
model, use SUBCLASS, inspect test rows, or choose a feature policy.  C1~C3
recompute their masks inside each outer training fold.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from open_cancer.correlation_audit import phi_jaccard_audit, raw_mutation_presence
from open_cancer.hashing import sha256_file, sha256_lines


ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "data" / "raw" / "train.csv"
OUTPUT_DIR = ROOT / "reports" / "analysis" / "c0_extreme_correlation_audit"
SUMMARY_PATH = OUTPUT_DIR / "summary.json"
PAIRS_PATH = OUTPUT_DIR / "candidate_pairs.csv"
README_PATH = OUTPUT_DIR / "README.md"
THRESHOLDS = {"phi_min": 0.50, "jaccard_min": 0.90, "min_joint_count": 20}


def main() -> None:
    frame = pd.read_csv(TRAIN, dtype=str, keep_default_na=False)
    if "SUBCLASS" not in frame.columns:
        raise ValueError("C0 train.csv에는 SUBCLASS 열이 필요합니다.")
    features, feature_names = raw_mutation_presence(frame)
    selection = phi_jaccard_audit(features, feature_names, **THRESHOLDS)
    metadata = selection.metadata
    candidates = metadata["candidate_pairs"]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    columns = [
        "left_gene",
        "right_gene",
        "left_prevalence",
        "right_prevalence",
        "joint_mutation_count",
        "phi",
        "jaccard",
    ]
    with PAIRS_PATH.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(candidates)
    summary = {
        "task_issue": 187,
        "run_mode": "explore",
        "record_role": "diagnostic_train_only",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": {
            "path": str(TRAIN.relative_to(ROOT)),
            "sha256": sha256_file(TRAIN),
            "rows": int(features.shape[0]),
            "gene_count": int(features.shape[1]),
            "gene_order_sha256": sha256_lines(name.removesuffix("__mutated") for name in feature_names),
            "mutation_presence_cells": int(features.nnz),
        },
        "selection_policy": metadata["parameters"],
        "candidate_pair_count": metadata["candidate_pair_count"],
        "matched_pair_count": metadata["matched_pair_count"],
        "dropped_feature_count": len(metadata["dropped_feature_names"]),
        "candidate_pairs_path": str(PAIRS_PATH.relative_to(ROOT)),
        "uses_subclass": False,
        "uses_test_rows": False,
        "fits_model": False,
        "decision": (
            "극단 중복 후보가 없어 C0는 제거 정책을 제안하지 않는다. "
            "C1~C3은 사전 고정된 각 임계값으로 outer-train에서 다시 계산한다."
            if not candidates
            else "C0 후보는 진단용으로만 기록한다. C1~C3은 outer-train에서 다시 계산한다."
        ),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    candidate_message = "없음 (0개)" if not candidates else f"{len(candidates)}개"
    README_PATH.write_text(
        "# C0 극단 Phi/Jaccard 중복 진단\n\n"
        "> Issue #187의 분석 전용 단계입니다. 공식 EXP, 모델 학습, OOF, Public LB, "
        "test 데이터 사용을 포함하지 않습니다.\n\n"
        "## 결과\n\n"
        f"- 분석 행: {features.shape[0]:,}\n"
        f"- mutation-presence 유전자 열: {features.shape[1]:,}\n"
        f"- 기록된 변이 존재 셀: {features.nnz:,}\n"
        f"- 극단 중복 후보: **{candidate_message}**\n\n"
        "## 사전 고정 기준\n\n"
        "- Phi ≥ 0.50\n"
        "- Jaccard ≥ 0.90\n"
        "- 공동 변이 수 ≥ 20\n"
        "- `GENE__mutated` 열만 검사\n\n"
        "## 해석\n\n"
        "이 기준은 사실상 같은 정보를 반복하는 열이 있는지만 확인하는 보수적 감사다. "
        "후보가 없으므로 C0 자체는 어떤 열도 삭제하지 않으며, Feature Spec이나 모델을 "
        "변경하지 않는다. 이후 C1~C3 공식 실험은 전체 train 진단 결과를 재사용하지 않고 "
        "각 outer-fold 학습 행에서 후보와 mask를 새로 계산한다.\n\n"
        "## 산출물\n\n"
        "- `summary.json`: 입력 해시, 기준, 후보 수와 사용 범위\n"
        "- `candidate_pairs.csv`: 기준을 통과한 모든 pair (없어도 header 유지)\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
