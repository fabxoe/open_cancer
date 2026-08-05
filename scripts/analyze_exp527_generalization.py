#!/usr/bin/env python
"""Audit EXP-527 profile shift and OOF error structure without model fitting.

The only fitted diagnostic model is an adversarial train-vs-test classifier.
It never sees SUBCLASS and its output must not select a feature, weight, or
leaderboard submission.  Parser-v4 class profiles are reconstructed exactly
as in EXP-527: each OOF row is transformed by its outer-train centroid and the
test score is the mean of the five outer-train transforms.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold

from open_cancer.class_semantic_profiles import ClassSemanticProfileFamily
from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.hashing import sha256_file
from open_cancer.patient_semantic_vector import PatientSemanticVectorFamily
from run_adversarial_validation import fit_domain_auc, top_features_from_gain


ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data/raw/train.csv"
TEST_PATH = ROOT / "data/raw/test.csv"
SPLIT_PATH = ROOT / "data/splits/stratified_5fold_seed42.csv"
OOF_374 = ROOT / "oof/exp374_stop_isoform_residue_mask.csv"
OOF_527 = ROOT / "oof/exp527_parser_v4_class_cosine_loo.csv"
TEST_PROBA_374 = ROOT / "preds/exp374_stop_isoform_residue_mask_test_proba.csv"
TEST_PROBA_527 = ROOT / "preds/exp527_parser_v4_class_cosine_loo_test_proba.csv"
OUTPUT_DIR = ROOT / "reports/analysis/exp527_generalization_audit"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def entropy(probability: np.ndarray) -> np.ndarray:
    clipped = np.clip(probability, 1e-15, 1.0)
    return -np.sum(clipped * np.log(clipped), axis=1)


def prediction_summary(probability: np.ndarray) -> dict[str, float]:
    ordered = np.sort(probability, axis=1)
    return {
        "mean_max_probability": float(np.max(probability, axis=1).mean()),
        "mean_margin": float((ordered[:, -1] - ordered[:, -2]).mean()),
        "mean_entropy": float(entropy(probability).mean()),
    }


def reconstruct_profile_scores(
    train: pd.DataFrame,
    test: pd.DataFrame,
    fold_by_row: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    gene_columns = tuple(column for column in train.columns if column not in {"ID", "SUBCLASS"})
    vectorizer = PatientSemanticVectorFamily(gene_columns).fit(train.iloc[:1])
    train_semantic = vectorizer.transform(train)
    test_semantic = vectorizer.transform(test)
    oof_scores = np.zeros((len(train), len(CLASS_LABELS)), dtype=np.float32)
    test_scores = np.zeros((len(test), len(CLASS_LABELS)), dtype=np.float64)
    fold_records: list[dict[str, Any]] = []
    labels = train["SUBCLASS"].to_numpy(dtype=str)
    for fold in range(5):
        train_indices = np.flatnonzero(fold_by_row != fold)
        valid_indices = np.flatnonzero(fold_by_row == fold)
        fitted = ClassSemanticProfileFamily(tuple(CLASS_LABELS), method="cosine").fit(
            train_semantic[train_indices], labels[train_indices]
        )
        oof_scores[valid_indices] = fitted.transform(train_semantic[valid_indices]).toarray()
        test_scores += fitted.transform(test_semantic).toarray() / 5.0
        fold_records.append({"fold": fold, **fitted.audit_record()})
    audit = {
        "semantic_dimension": int(train_semantic.shape[1]),
        "train_semantic_nnz": int(train_semantic.nnz),
        "test_semantic_nnz": int(test_semantic.nnz),
        "train_zero_rows": int(np.sum(np.asarray(train_semantic.sum(axis=1)).ravel() == 0)),
        "test_zero_rows": int(np.sum(np.asarray(test_semantic.sum(axis=1)).ravel() == 0)),
        "fold_profiles": fold_records,
    }
    return oof_scores, test_scores.astype(np.float32), audit


def profile_distribution(
    train_scores: np.ndarray, test_scores: np.ndarray
) -> pd.DataFrame:
    rows = []
    for index, label in enumerate(CLASS_LABELS):
        left = train_scores[:, index].astype(np.float64)
        right = test_scores[:, index].astype(np.float64)
        pooled = np.sqrt((left.var(ddof=1) + right.var(ddof=1)) / 2.0)
        row: dict[str, Any] = {
            "profile_class": label,
            "train_mean": float(left.mean()),
            "test_mean": float(right.mean()),
            "mean_delta_test_minus_train": float(right.mean() - left.mean()),
            "standardized_mean_difference": float(
                (right.mean() - left.mean()) / pooled if pooled > 0 else 0.0
            ),
            "train_std": float(left.std(ddof=1)),
            "test_std": float(right.std(ddof=1)),
        }
        for name, quantile in (("p01", .01), ("p10", .10), ("p50", .50), ("p90", .90), ("p99", .99)):
            row[f"train_{name}"] = float(np.quantile(left, quantile))
            row[f"test_{name}"] = float(np.quantile(right, quantile))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        "standardized_mean_difference", key=lambda values: values.abs(), ascending=False
    )


def domain_audit(train_scores: np.ndarray, test_scores: np.ndarray) -> dict[str, Any]:
    matrix = sparse.csr_matrix(np.vstack([train_scores, test_scores]))
    target = np.concatenate([np.zeros(len(train_scores)), np.ones(len(test_scores))]).astype(np.int32)
    folds = list(StratifiedKFold(n_splits=5, shuffle=True, random_state=42).split(matrix, target))
    result, _ = fit_domain_auc(
        x_full=matrix,
        y=target,
        column_indices=None,
        fold_splits=folds,
        seed=42,
        n_estimators=200,
        max_depth=3,
        learning_rate=0.05,
        early_stopping_rounds=20,
        compute_gain=True,
    )
    names = [f"class_cosine__{label}" for label in CLASS_LABELS]
    return {
        "analysis_only": True,
        "subclass_used": False,
        "public_lb_used": False,
        "domain_target": "OOF-train=0,test=1",
        "overall_auc": result["overall_auc"],
        "fold_auc": result["fold_auc"],
        "top_gain": top_features_from_gain(result["mean_gain"], names, 26),
    }


def compare_oof() -> tuple[dict[str, Any], pd.DataFrame]:
    parent = pd.read_csv(OOF_374, dtype={"ID": str})
    source = pd.read_csv(OOF_527, dtype={"ID": str})
    if parent["ID"].tolist() != source["ID"].tolist():
        raise ValueError("EXP-374/527 OOF ID order mismatch")
    if parent["SUBCLASS_TRUE"].tolist() != source["SUBCLASS_TRUE"].tolist():
        raise ValueError("EXP-374/527 OOF target mismatch")
    truth = source["SUBCLASS_TRUE"].to_numpy(dtype=str)
    parent_pred = parent["SUBCLASS_PRED"].to_numpy(dtype=str)
    source_pred = source["SUBCLASS_PRED"].to_numpy(dtype=str)
    parent_correct = parent_pred == truth
    source_correct = source_pred == truth
    parent_probability = parent[list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)
    source_probability = source[list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)
    error_correlation = float(np.corrcoef(~parent_correct, ~source_correct)[0, 1])
    summary = {
        "rows": len(source),
        "error_indicator_correlation": error_correlation,
        "both_correct": int(np.sum(parent_correct & source_correct)),
        "exp374_only_correct": int(np.sum(parent_correct & ~source_correct)),
        "exp527_only_correct": int(np.sum(~parent_correct & source_correct)),
        "both_wrong": int(np.sum(~parent_correct & ~source_correct)),
        "prediction_changed": int(np.sum(parent_pred != source_pred)),
        "prediction_changed_ratio": float(np.mean(parent_pred != source_pred)),
        "mean_absolute_probability_delta": float(np.mean(np.abs(source_probability - parent_probability))),
        "exp374_prediction": prediction_summary(parent_probability),
        "exp527_prediction": prediction_summary(source_probability),
        "exp374_oof_sha256": sha256_file(OOF_374),
        "exp527_oof_sha256": sha256_file(OOF_527),
    }
    rows = []
    for label in CLASS_LABELS:
        y_binary = truth == label
        parent_binary = parent_pred == label
        source_binary = source_pred == label
        parent_f1 = float(f1_score(y_binary, parent_binary, zero_division=0))
        source_f1 = float(f1_score(y_binary, source_binary, zero_division=0))
        rows.append({
            "class": label,
            "support": int(y_binary.sum()),
            "exp374_f1": parent_f1,
            "exp527_f1": source_f1,
            "f1_delta": source_f1 - parent_f1,
        })
    return summary, pd.DataFrame(rows).sort_values("f1_delta")


def blank_row_audit(test: pd.DataFrame) -> tuple[dict[str, Any], pd.DataFrame]:
    gene_columns = [column for column in test.columns if column != "ID"]
    blank_mask = test[gene_columns].eq("")
    affected = blank_mask.any(axis=1).to_numpy()
    blank_count = blank_mask.sum(axis=1).to_numpy(dtype=np.int32)
    parent = pd.read_csv(TEST_PROBA_374, dtype={"ID": str})
    source = pd.read_csv(TEST_PROBA_527, dtype={"ID": str})
    if parent["ID"].tolist() != test["ID"].tolist() or source["ID"].tolist() != test["ID"].tolist():
        raise ValueError("test probability ID order mismatch")
    parent_p = parent[list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)
    source_p = source[list(PROBABILITY_COLUMNS)].to_numpy(dtype=np.float64)
    class_array = np.asarray(CLASS_LABELS)
    rows = pd.DataFrame({
        "ID": test["ID"],
        "blank_gene_cells": blank_count,
        "exp374_pred": class_array[np.argmax(parent_p, axis=1)],
        "exp527_pred": class_array[np.argmax(source_p, axis=1)],
        "prediction_changed": np.argmax(parent_p, axis=1) != np.argmax(source_p, axis=1),
        "exp374_confidence": np.max(parent_p, axis=1),
        "exp527_confidence": np.max(source_p, axis=1),
        "mean_absolute_probability_delta": np.mean(np.abs(source_p - parent_p), axis=1),
    }).loc[affected]
    summary: dict[str, Any] = {
        "actual_blank_cells": int(blank_mask.to_numpy().sum()),
        "affected_rows": int(affected.sum()),
        "causal_interpretation_allowed": False,
        "note": "Association-only: no checkpoint counterfactual blank-to-WT inference was run.",
    }
    for name, mask in (("affected", affected), ("unaffected", ~affected)):
        summary[name] = {
            "rows": int(mask.sum()),
            "exp374": prediction_summary(parent_p[mask]),
            "exp527": prediction_summary(source_p[mask]),
            "mean_absolute_exp527_minus_exp374_probability_delta": float(
                np.mean(np.abs(source_p[mask] - parent_p[mask]))
            ),
            "prediction_disagreement_ratio": float(
                np.mean(np.argmax(source_p[mask], axis=1) != np.argmax(parent_p[mask], axis=1))
            ),
        }
    return summary, rows


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    train = pd.read_csv(TRAIN_PATH, dtype=str, keep_default_na=False)
    test = pd.read_csv(TEST_PATH, dtype=str, keep_default_na=False)
    split = pd.read_csv(SPLIT_PATH, dtype={"ID": str, "fold": int})
    merged = train[["ID"]].merge(split, on="ID", how="left", validate="one_to_one", sort=False)
    if merged["fold"].isna().any() or merged["ID"].tolist() != train["ID"].tolist():
        raise ValueError("canonical split mismatch")
    train_scores, test_scores, profile_audit = reconstruct_profile_scores(
        train, test, merged["fold"].to_numpy(dtype=np.int32)
    )
    distribution = profile_distribution(train_scores, test_scores)
    adversarial = domain_audit(train_scores, test_scores)
    oof_summary, class_table = compare_oof()
    blank_summary, blank_rows = blank_row_audit(test)
    distribution.to_csv(OUTPUT_DIR / "profile_score_distribution.csv", index=False)
    class_table.to_csv(OUTPUT_DIR / "class_f1_comparison.csv", index=False)
    blank_rows.to_csv(OUTPUT_DIR / "test_blank_affected_rows.csv", index=False)
    write_json(OUTPUT_DIR / "profile_reconstruction.json", profile_audit)
    write_json(OUTPUT_DIR / "adversarial_auc.json", adversarial)
    write_json(OUTPUT_DIR / "oof_comparison.json", oof_summary)
    write_json(OUTPUT_DIR / "test_blank_audit.json", blank_summary)
    summary = {
        "issue": 530,
        "analysis_only": True,
        "profile_domain_auc": adversarial["overall_auc"],
        "profile_domain_fold_auc": adversarial["fold_auc"],
        "largest_absolute_profile_shift": distribution.iloc[0].to_dict(),
        "oof": oof_summary,
        "blank_test": blank_summary,
        "input_sha256": {
            "train": sha256_file(TRAIN_PATH),
            "test": sha256_file(TEST_PATH),
            "split": sha256_file(SPLIT_PATH),
        },
    }
    write_json(OUTPUT_DIR / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
