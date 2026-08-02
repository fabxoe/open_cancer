#!/usr/bin/env python
"""Compare train/test mutation tokenization without using test labels."""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from open_cancer.mutation_features import classify_mutation_token

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "data" / "raw" / "train.csv"
TEST = ROOT / "data" / "raw" / "test.csv"
OUT = ROOT / "reports" / "analysis" / "tokenization_ood"
TOKEN_RE = re.compile(r"\s+")


def summarize(path: Path, genes: list[str]) -> tuple[pd.DataFrame, dict[str, float]]:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    values = frame[genes].to_numpy(dtype=object)
    gene_rows: list[dict[str, float | str]] = []
    row_token_counts = np.zeros(len(frame), dtype=np.int32)
    row_complex_counts = np.zeros(len(frame), dtype=np.int32)
    for col, gene in enumerate(genes):
        cell_tokens: list[int] = []
        complex_tokens = 0
        mutated_cells = 0
        for value in values[:, col]:
            text = str(value).strip()
            if not text or text == "WT":
                cell_tokens.append(0)
                continue
            tokens = [token for token in TOKEN_RE.split(text) if token]
            mutated_cells += 1
            cell_tokens.append(len(tokens))
            for token in tokens:
                row_token_counts[len(cell_tokens) - 1] += 1
                kind = classify_mutation_token(token)
                if kind == "complex":
                    complex_tokens += 1
                    row_complex_counts[len(cell_tokens) - 1] += 1
        counts = np.asarray(cell_tokens, dtype=np.int32)
        token_total = int(counts.sum())
        gene_rows.append(
            {
                "gene": gene,
                "n_rows": len(frame),
                "mutated_cell_rate": mutated_cells / len(frame),
                "token_total": token_total,
                "tokens_per_row_mean": float(counts.mean()),
                "tokens_per_row_median": float(np.median(counts)),
                "tokens_per_row_p95": float(np.percentile(counts, 95)),
                "complex_token_fraction": complex_tokens / token_total if token_total else 0.0,
            }
        )
    return pd.DataFrame(gene_rows), {
        "n_rows": float(len(frame)),
        "row_token_count_mean": float(row_token_counts.mean()),
        "row_token_count_median": float(np.median(row_token_counts)),
        "row_token_count_p95": float(np.percentile(row_token_counts, 95)),
        "row_complex_count_mean": float(row_complex_counts.mean()),
        "row_complex_presence_rate": float(np.mean(row_complex_counts > 0)),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    train_header = pd.read_csv(TRAIN, nrows=0).columns.tolist()
    test_header = pd.read_csv(TEST, nrows=0).columns.tolist()
    genes = [column for column in train_header if column not in {"ID", "SUBCLASS"}]
    if test_header != ["ID", *genes]:
        raise ValueError("train/test feature columns or order differ")
    train, train_rows = summarize(TRAIN, genes)
    test, test_rows = summarize(TEST, genes)
    merged = train.merge(test, on="gene", suffixes=("_train", "_test"))
    merged["mutated_cell_rate_diff"] = merged["mutated_cell_rate_test"] - merged["mutated_cell_rate_train"]
    merged["token_mean_ratio_test_over_train"] = merged.apply(
        lambda row: row.tokens_per_row_mean_test / row.tokens_per_row_mean_train
        if row.tokens_per_row_mean_train else np.nan,
        axis=1,
    )
    merged["complex_fraction_diff"] = merged["complex_token_fraction_test"] - merged["complex_token_fraction_train"]
    merged["token_total_ratio_test_over_train"] = merged.apply(
        lambda row: row.token_total_test / row.token_total_train
        if row.token_total_train else np.nan,
        axis=1,
    )
    merged["abs_shift_score"] = (
        merged["mutated_cell_rate_diff"].abs()
        + merged["complex_fraction_diff"].abs()
        + (np.log1p(merged["token_mean_ratio_test_over_train"]) - np.log(2)).abs().fillna(0)
    )
    merged.sort_values("abs_shift_score", ascending=False).to_csv(OUT / "gene_tokenization_shift.csv", index=False)
    pd.DataFrame([train_rows, test_rows], index=["train", "test"]).to_csv(OUT / "row_tokenization_summary.csv")
    top = merged.head(25)[["gene", "abs_shift_score", "mutated_cell_rate_diff", "complex_fraction_diff", "token_mean_ratio_test_over_train"]]
    (OUT / "README.md").write_text(
        """# Train/Test tokenization OOD QC

이 탐색 분석은 test의 `SUBCLASS`나 모델 예측을 사용하지 않고, 같은 유전자 컬럼에
대해 train/test의 토큰화·표기 분포만 비교한다. 결과는 피처 채택이나 Public 제출을
결정하는 근거가 아니라 기술적 batch effect 후보를 찾는 QC 자료다.

- `gene_tokenization_shift.csv`: 유전자별 변이 셀 비율, token 수, complex 비율과 차이
- `row_tokenization_summary.csv`: 샘플별 전체 token/complex 요약
- `abs_shift_score`: 후보 유전자를 찾기 위한 탐색 정렬값이며 통계적 유의성 검정값이 아님

해석 순서:

1. `mutated_cell_rate_diff`가 큰 유전자는 호출·필터·패널 차이 후보로 확인한다.
2. `token_mean_ratio_test_over_train`가 큰 유전자는 한 셀의 다중 token 표기 차이를 확인한다.
3. `complex_fraction_diff`가 큰 유전자는 complex 표기/파서 차이를 확인한다.
4. 이 결과만으로 Feature Spec을 변경하지 않고, 필요하면 별도 negative control과
   EXP-094 incremental ablation으로 검증한다.
""",
        encoding="utf-8",
    )
    (OUT / "top_shift_genes.json").write_text(
        json.dumps(top.to_dict(orient="records"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"genes": len(genes), "train_rows": int(train_rows["n_rows"]), "test_rows": int(test_rows["n_rows"]), "output": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
