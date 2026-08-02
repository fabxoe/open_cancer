#!/usr/bin/env python
"""Create target-aware, label-descriptive violin plots for the mutation table.

This is exploratory analysis only. It does not fit a model, choose features, or
write anything under ``configs/`` or ``EXPERIMENT_HISTORY.md``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from open_cancer.mutation_features import classify_mutation_token


ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "data" / "raw" / "train.csv"
TEST = ROOT / "data" / "raw" / "test.csv"
OUT = ROOT / "reports" / "analysis" / "eda_violin"
TOKEN_RE = re.compile(r"\s+")


def classify(token: str) -> str:
    token = token.strip()
    if not token:
        return "blank"
    return classify_mutation_token(token)


def build_summary(path: Path = TRAIN, with_label: bool = True) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    labels = frame.pop("SUBCLASS") if with_label else None
    frame.pop("ID")
    values = frame.to_numpy(dtype=object)
    mutation = (values != "") & (values != "WT")
    out = pd.DataFrame(index=frame.index)
    if labels is not None:
        out["SUBCLASS"] = labels.to_numpy()
    out["mutated_gene_count"] = mutation.sum(axis=1)
    token_counts = np.zeros((len(frame), 5), dtype=np.int32)
    type_names = ("missense", "synonymous", "nonsense", "frameshift", "complex")
    for row, col in zip(*np.where(mutation)):
        for token in TOKEN_RE.split(str(values[row, col]).strip()):
            kind = classify(token)
            if kind != "blank":
                token_counts[row, type_names.index(kind)] += 1
    for index, name in enumerate(type_names):
        out[f"{name}_count"] = token_counts[:, index]
    out["total_variant_count"] = token_counts.sum(axis=1)
    out["truncating_count"] = out["nonsense_count"] + out["frameshift_count"]
    return out


def build_ood_summary(train: pd.DataFrame, test: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    rows = []
    for metric in metrics:
        train_values = train[metric].to_numpy(dtype=float)
        test_values = test[metric].to_numpy(dtype=float)
        train_median = float(np.median(train_values))
        test_median = float(np.median(test_values))
        rows.append(
            {
                "metric": metric,
                "train_n": len(train_values),
                "test_n": len(test_values),
                "train_median": train_median,
                "test_median": test_median,
                "median_ratio_test_over_train": (test_median / train_median if train_median else np.nan),
                "train_iqr": float(np.percentile(train_values, 75) - np.percentile(train_values, 25)),
                "test_iqr": float(np.percentile(test_values, 75) - np.percentile(test_values, 25)),
                "train_p95": float(np.percentile(train_values, 95)),
                "test_p95": float(np.percentile(test_values, 95)),
                "train_p99": float(np.percentile(train_values, 99)),
                "test_p99": float(np.percentile(test_values, 99)),
                "train_zero_rate": float(np.mean(train_values == 0)),
                "test_zero_rate": float(np.mean(test_values == 0)),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    summary = build_summary()
    test_summary = build_summary(TEST, with_label=False)
    metrics = [
        "mutated_gene_count",
        "total_variant_count",
        "missense_count",
        "nonsense_count",
        "frameshift_count",
        "complex_count",
        "truncating_count",
    ]
    plot_data = summary[["SUBCLASS", *metrics]].melt(
        id_vars="SUBCLASS", var_name="metric", value_name="value"
    )
    sns.set_theme(style="whitegrid", context="notebook")
    fig, axes = plt.subplots(4, 2, figsize=(22, 25), constrained_layout=True)
    axes = axes.ravel()
    order = sorted(summary["SUBCLASS"].unique())
    for axis, metric in zip(axes, metrics):
        subset = plot_data[plot_data["metric"] == metric]
        sns.violinplot(
            data=subset,
            x="SUBCLASS",
            y="value",
            order=order,
            cut=0,
            inner="quartile",
            density_norm="width",
            linewidth=0.6,
            ax=axis,
        )
        axis.set_title(metric)
        axis.set_xlabel("")
        axis.tick_params(axis="x", rotation=70, labelsize=8)
    axes[-1].axis("off")
    fig.suptitle("Train mutation burden distribution by cancer subclass", fontsize=18)
    fig.savefig(OUT / "train_mutation_violin.png", dpi=180)
    plt.close(fig)

    # Heavy-tailed mutation counts hide the central distribution on a raw axis.
    log_plot_data = plot_data.copy()
    log_plot_data["value"] = np.log1p(log_plot_data["value"])
    fig, axes = plt.subplots(4, 2, figsize=(22, 25), constrained_layout=True)
    axes = axes.ravel()
    for axis, metric in zip(axes, metrics):
        subset = log_plot_data[log_plot_data["metric"] == metric]
        sns.violinplot(
            data=subset,
            x="SUBCLASS",
            y="value",
            order=order,
            cut=0,
            inner="quartile",
            density_norm="width",
            linewidth=0.6,
            ax=axis,
        )
        axis.set_title(f"log1p({metric})")
        axis.set_xlabel("")
        axis.tick_params(axis="x", rotation=70, labelsize=8)
    axes[-1].axis("off")
    fig.suptitle("Log-scaled train mutation distribution by cancer subclass", fontsize=18)
    fig.savefig(OUT / "train_mutation_violin_log1p.png", dpi=180)
    plt.close(fig)

    summary_stats = (
        summary.groupby("SUBCLASS")[metrics]
        .agg(["count", "median", "mean", "std", "min", "max"])
        .round(6)
    )
    summary_stats.columns = [f"{metric}_{stat}" for metric, stat in summary_stats.columns]
    summary_stats.index.name = "SUBCLASS"
    summary_stats.to_csv(OUT / "summary_by_subclass.csv")
    build_ood_summary(summary, test_summary, metrics).to_csv(
        OUT / "train_test_burden_ood.csv", index=False
    )
    (OUT / "README.md").write_text(
        """# Train mutation violin EDA

이 분석은 모델 학습·피처 선택·제출에 사용하지 않는 탐색용 산출물입니다.

- 입력: `data/raw/train.csv`
- 그룹: `SUBCLASS` 26개
- 수치: mutated gene 수, 전체 변이 token 수, 변이 유형별 token 수, truncating 수
- 변이 분류: 프로젝트의 보수적 문자열 규칙을 단순화해 사용
- 결과: `train_mutation_violin.png`, `train_mutation_violin_log1p.png`, `summary_by_subclass.csv`
- train/test 비교: `train_test_burden_ood.csv` (test에는 암종 라벨을 사용하지 않음)
- 단일 피처 OOF: `single_feature_oof.csv` (별도 `scripts/run_eda_burden_oof.py` 실행)

분포 차이는 후속 실험의 가설을 세우는 데만 사용하며, OOF 평가 없이 피처 채택 근거로 사용하지 않습니다.
""",
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(summary), "classes": len(order), "output": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
