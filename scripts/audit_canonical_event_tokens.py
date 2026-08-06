#!/usr/bin/env python
"""Audit parser-v4 patient event-token support without fitting a model."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from open_cancer.canonical_event_tokenizer import (
    CANONICAL_EVENT_TOKENIZER_VERSION,
    PatientEventTokens,
    build_event_vocabulary,
    summarize_event_tokens,
    tokenize_patient_event_row,
)
from open_cancer.event_token_audit import (
    SUPPORT_THRESHOLDS,
    integer_quantiles,
    summarize_oov,
    token_document_frequency,
    token_key,
    vocabulary_at_support,
)
from open_cancer.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", type=Path, default=ROOT / "data/raw/train.csv")
    parser.add_argument("--test", type=Path, default=ROOT / "data/raw/test.csv")
    parser.add_argument(
        "--split", type=Path,
        default=ROOT / "data/splits/stratified_5fold_seed42.csv",
    )
    parser.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "reports/analysis/parser_v4_event_token_audit",
    )
    parser.add_argument("--position-bin-width", type=int, default=100)
    return parser.parse_args()


def _tokenize(
    frame: pd.DataFrame, gene_columns: tuple[str, ...], *, position_bin_width: int
) -> tuple[PatientEventTokens, ...]:
    output: list[PatientEventTokens] = []
    for index, (_, row) in enumerate(frame.iterrows(), start=1):
        output.append(
            tokenize_patient_event_row(
                row, gene_columns, position_bin_width=position_bin_width
            )
        )
        if index % 500 == 0 or index == len(frame):
            print(f"tokenized {index}/{len(frame)}", flush=True)
    return tuple(output)


def _support_table(
    train_df: Counter[str], test_df: Counter[str]
) -> list[dict[str, object]]:
    rows = []
    for token in sorted(set(train_df) | set(test_df)):
        rows.append({
            "token": token,
            "key": token_key(token),
            "train_document_frequency": train_df[token],
            "test_document_frequency": test_df[token],
        })
    return rows


def main() -> None:
    args = _parse_args()
    train = pd.read_csv(args.train, dtype=str, keep_default_na=False)
    test = pd.read_csv(args.test, dtype=str, keep_default_na=False)
    split = pd.read_csv(args.split, dtype={"ID": str, "fold": int})
    gene_columns = tuple(c for c in train.columns if c not in {"ID", "SUBCLASS"})
    if tuple(c for c in test.columns if c != "ID") != gene_columns:
        raise ValueError("train/test gene column order differs")
    if train["ID"].tolist() != split["ID"].tolist():
        raise ValueError("canonical split ID order differs from train")

    train_tokens = _tokenize(
        train, gene_columns, position_bin_width=args.position_bin_width
    )
    test_tokens = _tokenize(
        test, gene_columns, position_bin_width=args.position_bin_width
    )
    train_df = token_document_frequency(train_tokens)
    test_df = token_document_frequency(test_tokens)
    full_vocabulary = build_event_vocabulary(train_tokens)

    threshold_results: dict[str, object] = {}
    for threshold in SUPPORT_THRESHOLDS:
        vocabulary = vocabulary_at_support(train_df, threshold)
        threshold_results[str(threshold)] = {
            "vocabulary_size": len(vocabulary),
            "train": asdict(summarize_oov(train_tokens, vocabulary)),
            "test": asdict(summarize_oov(test_tokens, vocabulary)),
        }

    fold_results: list[dict[str, object]] = []
    folds = split["fold"].to_numpy()
    for fold in sorted(set(folds.tolist())):
        fit = tuple(x for x, value in zip(train_tokens, folds) if value != fold)
        valid = tuple(x for x, value in zip(train_tokens, folds) if value == fold)
        fit_df = token_document_frequency(fit)
        thresholds: dict[str, object] = {}
        for threshold in SUPPORT_THRESHOLDS:
            vocabulary = vocabulary_at_support(fit_df, threshold)
            thresholds[str(threshold)] = {
                "vocabulary_size": len(vocabulary),
                "validation": asdict(summarize_oov(valid, vocabulary)),
            }
        fold_results.append({"fold": int(fold), "thresholds": thresholds})

    key_counts_train: Counter[str] = Counter()
    key_counts_test: Counter[str] = Counter()
    for token, count in train_df.items():
        key_counts_train[token_key(token)] += count
    for token, count in test_df.items():
        key_counts_test[token_key(token)] += count

    maximum_token_length = max(map(len, set(train_df) | set(test_df)), default=0)
    suspicious_exact_peptides = sorted(
        token for token in set(train_df) | set(test_df)
        if len(token) > 200
    )
    result = {
        "audit_type": "parser_v4_canonical_event_token_support_oov",
        "tokenizer_version": CANONICAL_EVENT_TOKENIZER_VERSION,
        "position_bin_width": args.position_bin_width,
        "inputs": {
            "train": {"rows": len(train), "sha256": sha256_file(args.train)},
            "test": {"rows": len(test), "sha256": sha256_file(args.test)},
            "split": {"rows": len(split), "sha256": sha256_file(args.split)},
            "gene_count": len(gene_columns),
        },
        "train_summary": asdict(summarize_event_tokens(train_tokens)),
        "test_summary": asdict(summarize_event_tokens(test_tokens)),
        "full_train_vocabulary_sha256": full_vocabulary.sha256,
        "full_train_vocabulary_test_oov": asdict(
            summarize_oov(test_tokens, frozenset(full_vocabulary.tokens))
        ),
        "lengths": {
            "train_source_events": integer_quantiles(x.source_event_count for x in train_tokens),
            "test_source_events": integer_quantiles(x.source_event_count for x in test_tokens),
            "train_token_occurrences": integer_quantiles(x.token_occurrence_count for x in train_tokens),
            "test_token_occurrences": integer_quantiles(x.token_occurrence_count for x in test_tokens),
            "train_unique_tokens": integer_quantiles(x.unique_token_count for x in train_tokens),
            "test_unique_tokens": integer_quantiles(x.unique_token_count for x in test_tokens),
        },
        "thresholds": threshold_results,
        "canonical_folds": fold_results,
        "token_key_document_frequency": {
            "train": dict(sorted(key_counts_train.items())),
            "test": dict(sorted(key_counts_test.items())),
        },
        "vocabulary_safety": {
            "maximum_token_length": maximum_token_length,
            "tokens_over_200_characters": suspicious_exact_peptides,
        },
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "audit.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    support = pd.DataFrame(_support_table(train_df, test_df))
    support["maximum_document_frequency"] = support[
        ["train_document_frequency", "test_document_frequency"]
    ].max(axis=1)
    support.sort_values(
        ["maximum_document_frequency", "train_document_frequency", "token"],
        ascending=[False, False, True],
    ).head(5_000).drop(columns="maximum_document_frequency").to_csv(
        args.output_dir / "token_support_top5000.csv", index=False
    )
    print(args.output_dir / "audit.json")


if __name__ == "__main__":
    main()
