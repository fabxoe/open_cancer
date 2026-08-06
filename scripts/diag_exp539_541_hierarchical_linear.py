#!/usr/bin/env python
"""Audit EXP-539/541 OOF behavior and compare with leakage-safe EXP-527."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, log_loss

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports/analysis/exp539_541_hierarchical_linear"
INPUTS = {
    "EXP-527": ROOT / "oof/exp527_parser_v4_class_cosine_loo.csv",
    "EXP-539": ROOT / "oof/exp539_hierarchical_raw_linear.csv",
    "EXP-541": ROOT / "oof/exp541_hierarchical_row_l2_linear.csv",
}


def _load(name: str, path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    rename = {
        "SUBCLASS_TRUE": "SUBCLASS",
        "SUBCLASS_PRED": "PREDICTED",
        "FOLD": "fold",
    }
    frame = frame.rename(columns=rename)
    required = {"ID", "SUBCLASS", "PREDICTED", "fold", *PROBABILITY_COLUMNS}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{name}: missing columns {sorted(missing)}")
    return frame[["ID", "SUBCLASS", "PREDICTED", "fold", *PROBABILITY_COLUMNS]]


def _summary(frame: pd.DataFrame) -> dict[str, object]:
    y = frame["SUBCLASS"].to_numpy()
    pred = frame["PREDICTED"].to_numpy()
    proba = frame[list(PROBABILITY_COLUMNS)].to_numpy(dtype=float)
    proba = proba / proba.sum(axis=1, keepdims=True)
    confidence = proba.max(axis=1)
    entropy = -(proba * np.log(np.clip(proba, 1e-15, 1))).sum(axis=1)
    correct = pred == y
    per_class = f1_score(
        y, pred, labels=CLASS_LABELS, average=None, zero_division=0
    )
    return {
        "macro_f1": float(f1_score(y, pred, average="macro", zero_division=0)),
        "log_loss": float(log_loss(y, proba, labels=CLASS_LABELS)),
        "accuracy": float(correct.mean()),
        "mean_confidence": float(confidence.mean()),
        "mean_correct_confidence": float(confidence[correct].mean()),
        "mean_wrong_confidence": float(confidence[~correct].mean()),
        "high_confidence_wrong_rate": float(((confidence >= 0.8) & ~correct).mean()),
        "mean_entropy": float(entropy.mean()),
        "per_class_f1": dict(zip(CLASS_LABELS, per_class.tolist(), strict=True)),
    }


def _pair(left: pd.DataFrame, right: pd.DataFrame) -> dict[str, float]:
    if left["ID"].tolist() != right["ID"].tolist():
        raise ValueError("OOF ID order mismatch")
    if left["SUBCLASS"].tolist() != right["SUBCLASS"].tolist():
        raise ValueError("OOF label order mismatch")
    truth = left["SUBCLASS"].to_numpy()
    left_pred = left["PREDICTED"].to_numpy()
    right_pred = right["PREDICTED"].to_numpy()
    left_correct = left_pred == truth
    right_correct = right_pred == truth
    return {
        "prediction_disagreement": float((left_pred != right_pred).mean()),
        "correctness_correlation": float(
            np.corrcoef(left_correct.astype(float), right_correct.astype(float))[0, 1]
        ),
        "left_only_correct": float((left_correct & ~right_correct).mean()),
        "right_only_correct": float((~left_correct & right_correct).mean()),
        "both_wrong": float((~left_correct & ~right_correct).mean()),
    }


def main() -> None:
    frames = {name: _load(name, path) for name, path in INPUTS.items()}
    summaries = {name: _summary(frame) for name, frame in frames.items()}
    pairs = {
        "EXP-539_vs_EXP-541": _pair(frames["EXP-539"], frames["EXP-541"]),
        "EXP-527_vs_EXP-539": _pair(frames["EXP-527"], frames["EXP-539"]),
        "EXP-527_vs_EXP-541": _pair(frames["EXP-527"], frames["EXP-541"]),
    }
    class_delta = {
        label: summaries["EXP-541"]["per_class_f1"][label]
        - summaries["EXP-539"]["per_class_f1"][label]
        for label in CLASS_LABELS
    }
    ranked_delta = sorted(class_delta.items(), key=lambda item: (-item[1], item[0]))
    result = {
        "inputs": {name: str(path.relative_to(ROOT)) for name, path in INPUTS.items()},
        "summaries": summaries,
        "pairwise": pairs,
        "exp541_minus_exp539_per_class_f1": dict(ranked_delta),
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "audit.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    rows = []
    for name in ("EXP-527", "EXP-539", "EXP-541"):
        item = summaries[name]
        rows.append(
            f"| {name} | {item['macro_f1']:.10f} | {item['log_loss']:.10f} | "
            f"{item['accuracy']:.10f} | {item['mean_wrong_confidence']:.6f} | "
            f"{item['high_confidence_wrong_rate']:.4%} |"
        )
    pair_rows = []
    for name, item in pairs.items():
        pair_rows.append(
            f"| {name.replace('_', ' ')} | {item['prediction_disagreement']:.4%} | "
            f"{item['correctness_correlation']:.6f} | {item['left_only_correct']:.4%} | "
            f"{item['right_only_correct']:.4%} | {item['both_wrong']:.4%} |"
        )
    improved = ranked_delta[:8]
    worsened = sorted(class_delta.items(), key=lambda item: (item[1], item[0]))[:8]
    lines = [
        "# EXP-539·541 hierarchical sparse-linear 오류 감사",
        "",
        "이 보고서는 Public LB나 test label을 사용하지 않고 canonical OOF만 비교합니다.",
        "",
        "## 전체 지표",
        "",
        "| 모델 | Macro F1 | Log Loss | Accuracy | 오답 평균 confidence | confidence≥0.8 오답률 |",
        "|---|---:|---:|---:|---:|---:|",
        *rows,
        "",
        "## 오류 다양성",
        "",
        "| 비교 | 예측 불일치 | 정오답 상관 | 왼쪽만 정답 | 오른쪽만 정답 | 둘 다 오답 |",
        "|---|---:|---:|---:|---:|---:|",
        *pair_rows,
        "",
        "## EXP-541 row-L2의 클래스별 변화",
        "",
        "개선 상위: " + ", ".join(f"{name} {delta:+.4f}" for name, delta in improved),
        "",
        "악화 상위: " + ", ".join(f"{name} {delta:+.4f}" for name, delta in worsened),
        "",
        "## 판단",
        "",
        "- row-L2는 raw count보다 Macro F1과 수렴을 개선했지만 Log Loss를 크게 악화했습니다.",
        "- 두 hierarchical linear 모델 모두 EXP-527보다 Macro F1이 0.02 이상 낮습니다.",
        "- 오류 다양성이 있더라도 확률 보정 전 LinearSVC softmax 출력은 앙상블 확률로 사용하지 않습니다.",
        "- A2 TF-IDF+L2는 사전 정의된 마지막 sparse-linear ablation으로 한 번만 실행할 수 있습니다.",
        "- A2도 EXP-527 대비 -0.02 미만이고 독자적 클래스 보완이 없으면 sparse-linear track을 종료합니다.",
        "",
        "참고로 EXP-539의 committed OOF probability에서 재계산한 Log Loss는 "
        "`2.5567518114`로 metrics.json의 실행 중 기록 `2.5453414917`과 "
        "`0.0114103197` 차이가 납니다. 이 차이는 Macro F1 판단에는 영향을 주지 "
        "않지만, EXP-539 확률 산출물의 계보를 재현 검증하기 전까지 해당 Log Loss를 "
        "근사 진단값으로 취급합니다. EXP-541은 재계산값과 실행 기록이 "
        "부동소수점 오차 범위에서 일치합니다.",
    ]
    (REPORT_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
