#!/usr/bin/env python
"""Single-fold parser-v4 gene-event TF-IDF screening for Issue #498."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics import accuracy_score, f1_score
from sklearn.svm import LinearSVC

from open_cancer.constants import CLASS_LABELS
from open_cancer.hashing import sha256_file, sha256_lines
from open_cancer.tfidf_gene_event import (
    build_sparse_screening_views,
    native_gene_event_indices,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = ROOT / "data" / "processed" / "issue475_native_v3_analysis"
DEFAULT_OUTPUT = ROOT / "reports" / "analysis" / "tfidf_gene_event_screening"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fold", type=int, default=0)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def row_norm_summary(matrix: sparse.csr_matrix) -> dict[str, float]:
    norms = np.sqrt(np.asarray(matrix.multiply(matrix).sum(axis=1)).ravel())
    return {
        "min": float(norms.min()),
        "median": float(np.median(norms)),
        "mean": float(norms.mean()),
        "max": float(norms.max()),
        "zero_rows": int(np.count_nonzero(norms == 0.0)),
    }


def main() -> None:
    args = parse_args()
    started = time.perf_counter()
    train_path = ROOT / "data" / "raw" / "train.csv"
    split_path = ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"
    cache = args.cache_dir.resolve()
    manifest = json.loads((cache / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("train_csv_sha256") != sha256_file(train_path):
        raise ValueError("cache와 train.csv SHA-256이 다릅니다.")

    all_names = tuple(
        json.loads((cache / "feature_names.json").read_text(encoding="utf-8"))
    )
    full_matrix = sparse.load_npz(cache / "train_features.npz").tocsr()
    if full_matrix.shape[1] != len(all_names):
        raise ValueError("cache feature matrix/name dimension이 다릅니다.")
    selected = native_gene_event_indices(all_names)
    names = tuple(all_names[index] for index in selected)
    matrix = sparse.csr_matrix(full_matrix[:, selected], dtype=np.float32)

    meta = pd.read_csv(train_path, usecols=["ID", "SUBCLASS"], dtype=str)
    folds = pd.read_csv(split_path, dtype={"ID": str, "fold": int})
    aligned = meta.merge(folds, on="ID", how="left", validate="one_to_one", sort=False)
    if aligned["fold"].isna().any() or not aligned["ID"].equals(meta["ID"]):
        raise ValueError("canonical split ID 정렬에 실패했습니다.")
    if args.fold not in set(aligned["fold"]):
        raise ValueError(f"존재하지 않는 fold: {args.fold}")
    train_mask = aligned["fold"].to_numpy() != args.fold
    valid_mask = ~train_mask
    views = build_sparse_screening_views(matrix[train_mask], matrix[valid_mask])
    y_train = aligned.loc[train_mask, "SUBCLASS"].to_numpy()
    y_valid = aligned.loc[valid_mask, "SUBCLASS"].to_numpy()

    arms = {
        "raw_binary": (views.raw_train, views.raw_validation),
        "row_l2_only": (views.l2_train, views.l2_validation),
        "tfidf_row_l2": (views.tfidf_l2_train, views.tfidf_l2_validation),
    }
    results: dict[str, dict[str, object]] = {}
    predictions: dict[str, np.ndarray] = {}
    for arm, (x_train, x_valid) in arms.items():
        arm_started = time.perf_counter()
        model = LinearSVC(
            C=1.0,
            class_weight="balanced",
            dual="auto",
            max_iter=10_000,
            random_state=42,
        )
        model.fit(x_train, y_train)
        prediction = model.predict(x_valid)
        predictions[arm] = prediction
        per_class = f1_score(
            y_valid,
            prediction,
            labels=CLASS_LABELS,
            average=None,
            zero_division=0,
        )
        results[arm] = {
            "macro_f1": float(
                f1_score(y_valid, prediction, average="macro", zero_division=0)
            ),
            "accuracy": float(accuracy_score(y_valid, prediction)),
            "per_class_f1": dict(zip(CLASS_LABELS, per_class.tolist(), strict=True)),
            "fit_predict_seconds": float(time.perf_counter() - arm_started),
            "n_iter_max": int(np.max(model.n_iter_)),
        }

    baseline = float(results["raw_binary"]["macro_f1"])
    for result in results.values():
        result["macro_f1_delta_vs_raw"] = float(result["macro_f1"]) - baseline
    label_agreement = {
        f"{left}__vs__{right}": float(np.mean(predictions[left] == predictions[right]))
        for left, right in (
            ("raw_binary", "row_l2_only"),
            ("raw_binary", "tfidf_row_l2"),
            ("row_l2_only", "tfidf_row_l2"),
        )
    }
    report = {
        "issue": 498,
        "analysis_only": True,
        "official_experiment": False,
        "source_experiment_cache": manifest.get("source_experiment"),
        "fold": args.fold,
        "train_rows": int(train_mask.sum()),
        "validation_rows": int(valid_mask.sum()),
        "feature_dimension": int(matrix.shape[1]),
        "matrix_nnz": int(matrix.nnz),
        "feature_names_sha256": sha256_lines(names),
        "train_csv_sha256": sha256_file(train_path),
        "split_csv_sha256": sha256_file(split_path),
        "transform_contract": {
            "vocabulary": "parser-v4 native-v3 gene-level semantic any indicators",
            "sample_aggregates_included": False,
            "idf_fit_scope": "canonical outer-train only",
            "smooth_idf": True,
            "sublinear_tf": False,
            "row_norm": "l2",
            "model": "LinearSVC(C=1.0,class_weight=balanced)",
        },
        "idf": {
            "min": float(views.idf.min()),
            "median": float(np.median(views.idf)),
            "mean": float(views.idf.mean()),
            "max": float(views.idf.max()),
        },
        "row_norms": {
            "raw_train": row_norm_summary(views.raw_train),
            "l2_train": row_norm_summary(views.l2_train),
            "tfidf_l2_train": row_norm_summary(views.tfidf_l2_train),
        },
        "results": results,
        "prediction_label_agreement": label_agreement,
        "total_seconds": float(time.perf_counter() - started),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    best_arm = max(results, key=lambda arm: float(results[arm]["macro_f1"]))
    lines = [
        "# Parser v4 gene-event TF-IDF 단일-fold screening",
        "",
        "> Issue #498의 분석 전용 결과입니다. 공식 5-fold 실험이나 제출 결과가 아닙니다.",
        "",
        "## 설계",
        "",
        f"- canonical validation fold: `{args.fold}`",
        f"- 행: train `{int(train_mask.sum())}`, validation `{int(valid_mask.sum())}`",
        f"- parser-v4 native gene-event 피처: `{matrix.shape[1]:,}`개",
        "- sample aggregate 제외, validation/test IDF fit 금지",
        "- 공통 모델: `LinearSVC(C=1.0, class_weight=balanced)`",
        "",
        "## 결과",
        "",
        "| arm | Macro F1 | raw 대비 | Accuracy | 시간(초) |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm, result in results.items():
        lines.append(
            f"| {arm} | {float(result['macro_f1']):.10f} | "
            f"{float(result['macro_f1_delta_vs_raw']):+.10f} | "
            f"{float(result['accuracy']):.10f} | "
            f"{float(result['fit_predict_seconds']):.2f} |"
        )
    lines.extend(
        [
            "",
            "## 해석 제한",
            "",
            f"- 이 fold에서 최고 arm은 `{best_arm}`입니다.",
            "- 단일 fold screening이므로 채택·기각 또는 EXPERIMENT_HISTORY 갱신에 사용하지 않습니다.",
            "- TF-IDF 효과와 행 정규화 효과를 분리하기 위해 row-L2-only arm을 함께 두었습니다.",
            "- 유망하면 새 Experiment Issue에서 canonical 5-fold로 재검증해야 합니다.",
            "",
            "## 재실행",
            "",
            "```bash",
            "uv run python scripts/screen_parser_v4_gene_event_tfidf.py --fold 0",
            "```",
        ]
    )
    (args.output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
