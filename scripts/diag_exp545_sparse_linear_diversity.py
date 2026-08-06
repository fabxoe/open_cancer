#!/usr/bin/env python
"""Compare EXP-545 OOF errors with leakage-safe and tree baselines."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, log_loss

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS


ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports/analysis/exp545_sparse_linear_diversity"
INPUTS = {
    "EXP-374": ROOT / "oof/exp374_stop_isoform_residue_mask.csv",
    "EXP-527": ROOT / "oof/exp527_parser_v4_class_cosine_loo.csv",
    "EXP-545": ROOT / "oof/exp545_hierarchical_tfidf_linear.csv",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path).rename(
        columns={
            "SUBCLASS_TRUE": "SUBCLASS",
            "SUBCLASS_PRED": "PREDICTED",
            "FOLD": "fold",
        }
    )
    return frame[["ID", "SUBCLASS", "PREDICTED", "fold", *PROBABILITY_COLUMNS]]


def _summary(frame: pd.DataFrame) -> dict[str, object]:
    y = frame["SUBCLASS"].to_numpy()
    pred = frame["PREDICTED"].to_numpy()
    proba = frame[list(PROBABILITY_COLUMNS)].to_numpy(dtype=float)
    proba /= proba.sum(axis=1, keepdims=True)
    confidence = proba.max(axis=1)
    correct = pred == y
    per_class = f1_score(
        y, pred, labels=CLASS_LABELS, average=None, zero_division=0
    )
    return {
        "macro_f1": float(f1_score(y, pred, average="macro", zero_division=0)),
        "accuracy": float(correct.mean()),
        "log_loss": float(log_loss(y, proba, labels=CLASS_LABELS)),
        "mean_confidence": float(confidence.mean()),
        "mean_wrong_confidence": float(confidence[~correct].mean()),
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
    frames = {name: _load(path) for name, path in INPUTS.items()}
    summaries = {name: _summary(frame) for name, frame in frames.items()}
    pairs = {
        "EXP-374_vs_EXP-545": _pair(frames["EXP-374"], frames["EXP-545"]),
        "EXP-527_vs_EXP-545": _pair(frames["EXP-527"], frames["EXP-545"]),
    }
    delta_527 = {
        label: summaries["EXP-545"]["per_class_f1"][label]
        - summaries["EXP-527"]["per_class_f1"][label]
        for label in CLASS_LABELS
    }
    result = {
        "inputs": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": _sha256(path)}
            for name, path in INPUTS.items()
        },
        "summaries": summaries,
        "pairwise": pairs,
        "exp545_minus_exp527_per_class_f1": dict(
            sorted(delta_527.items(), key=lambda item: (-item[1], item[0]))
        ),
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "audit.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    model_rows = [
        f"| {name} | {item['macro_f1']:.10f} | {item['accuracy']:.10f} | "
        f"{item['log_loss']:.10f} | {item['mean_confidence']:.6f} |"
        for name, item in summaries.items()
    ]
    pair_rows = [
        f"| {name.replace('_', ' ')} | {item['prediction_disagreement']:.4%} | "
        f"{item['correctness_correlation']:.6f} | {item['left_only_correct']:.4%} | "
        f"{item['right_only_correct']:.4%} | {item['both_wrong']:.4%} |"
        for name, item in pairs.items()
    ]
    improved = sorted(delta_527.items(), key=lambda item: (-item[1], item[0]))[:8]
    worsened = sorted(delta_527.items(), key=lambda item: (item[1], item[0]))[:8]
    report = [
        "# EXP-545 sparse-linear 다양성·calibration 사전 감사",
        "",
        "Canonical OOF만 사용했으며 Public LB와 test label은 사용하지 않았습니다.",
        "",
        "## 전체 지표",
        "",
        "| 모델 | Macro F1 | Accuracy | OOF probability Log Loss | 평균 confidence |",
        "|---|---:|---:|---:|---:|",
        *model_rows,
        "",
        "## 오류 다양성",
        "",
        "| 비교 | 예측 불일치 | 정오답 상관 | 왼쪽만 정답 | 오른쪽만 정답 | 둘 다 오답 |",
        "|---|---:|---:|---:|---:|---:|",
        *pair_rows,
        "",
        "## EXP-527 대비 클래스별 보완",
        "",
        "개선 상위: " + ", ".join(f"{label} {delta:+.4f}" for label, delta in improved),
        "",
        "악화 상위: " + ", ".join(f"{label} {delta:+.4f}" for label, delta in worsened),
        "",
        "## 결정",
        "",
        "- EXP-545는 단독 최고점보다 오류 다양성을 제공하는 후보인지 판정합니다.",
        "- LinearSVC decision score softmax는 보정 확률이 아니므로 평균·stacking 입력으로 확정하지 않습니다.",
        "- 다음 공식 실험은 같은 TF-IDF 입력의 multinomial Logistic Regression을 우선합니다.",
        "- 별도 calibration은 Logistic Regression 결과보다 명확한 필요가 있을 때만 nested 방식으로 진행합니다.",
    ]
    (REPORT_DIR / "README.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
