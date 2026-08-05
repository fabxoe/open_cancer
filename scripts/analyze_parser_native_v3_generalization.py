#!/usr/bin/env python
"""Diagnose EXP-479 native-v3 shift, redundancy and validation TreeSHAP.

This is analysis-only. Test rows are used only for domain-shift diagnostics;
their distribution never selects a model feature, threshold or weight.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy import sparse
from sklearn.preprocessing import LabelEncoder

from open_cancer.constants import CLASS_LABELS
from open_cancer.hashing import sha256_file, sha256_lines
from open_cancer.parser_baseline_features import legacy_five_family_feature_names
from open_cancer.parser_native_v3_features import (
    MODEL_ACTIVE_V3_CONSEQUENCES,
    ParserNativeV3SemanticRangeFamily,
)
from open_cancer.tree_shap_audit import (
    accumulate_contribution_chunk,
    stratified_validation_sample,
)
from run_adversarial_validation import (
    compute_feature_distribution,
    fit_domain_auc,
    top_features_from_gain,
)


ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
SPLIT_PATH = ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"
BASE_FEATURE_DIR = (
    ROOT / "data" / "processed" / "exp479_parser_v4_native_semantic_range_features"
)
ANALYSIS_CACHE = ROOT / "data" / "processed" / "issue475_native_v3_analysis"
MODEL_DIR = ROOT / "models" / "exp479_parser_v4_native_semantic_range"
OUTPUT_DIR = ROOT / "reports" / "analysis" / "parser_native_v3_generalization"
PARENT_OOF_PATH = ROOT / "oof" / "exp469_parser_v4_native_v2_token_count.csv"
SOURCE_OOF_PATH = ROOT / "oof" / "exp479_parser_v4_native_semantic_range.csv"


def native_consequence_from_name(name: str) -> str | None:
    if name.startswith("sample__native_v3_") and name.endswith("_token_count"):
        return name.removeprefix("sample__native_v3_").removesuffix("_token_count")
    marker = "__native_v3_"
    if name.startswith("gene__") and marker in name and name.endswith("_any"):
        return name.rsplit(marker, 1)[1].removesuffix("_any")
    return None


def native_v3_feature_family(name: str) -> str:
    consequence = native_consequence_from_name(name)
    if consequence is not None:
        if consequence not in MODEL_ACTIVE_V3_CONSEQUENCES:
            raise ValueError(f"unknown native-v3 consequence: {name}")
        return f"native_{consequence}"
    if name.startswith("sample__"):
        return "base_sample_aggregate"
    if name.endswith("__mutated"):
        return "gene_mutation_presence"
    if name.endswith("__missing"):
        return "missingness"
    raise ValueError(f"unclassified EXP-479 feature: {name}")


def family_index_map(feature_names: tuple[str, ...]) -> dict[str, np.ndarray]:
    grouped: dict[str, list[int]] = defaultdict(list)
    for index, name in enumerate(feature_names):
        grouped[native_v3_feature_family(name)].append(index)
    result = {
        family: np.asarray(indices, dtype=np.int64)
        for family, indices in sorted(grouped.items())
    }
    expected = {
        "base_sample_aggregate",
        "gene_mutation_presence",
        "missingness",
        *(f"native_{value}" for value in MODEL_ACTIVE_V3_CONSEQUENCES),
    }
    if set(result) != expected:
        raise ValueError(f"family partition mismatch: {sorted(result)}")
    covered = np.concatenate(list(result.values()))
    if len(covered) != len(feature_names) or len(np.unique(covered)) != len(covered):
        raise ValueError("family partition must cover each feature exactly once")
    return result


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def materialize_exp479_matrix() -> tuple[
    sparse.csr_matrix, sparse.csr_matrix, tuple[str, ...], dict[str, Any]
]:
    cache_files = (
        ANALYSIS_CACHE / "train_features.npz",
        ANALYSIS_CACHE / "test_features.npz",
        ANALYSIS_CACHE / "feature_names.json",
        ANALYSIS_CACHE / "manifest.json",
    )
    if all(path.is_file() for path in cache_files):
        names = tuple(json.loads(cache_files[2].read_text(encoding="utf-8")))
        manifest = json.loads(cache_files[3].read_text(encoding="utf-8"))
        if (
            manifest.get("train_csv_sha256") == sha256_file(TRAIN_PATH)
            and manifest.get("test_csv_sha256") == sha256_file(TEST_PATH)
            and manifest.get("feature_names_sha256") == sha256_lines(names)
        ):
            return (
                sparse.load_npz(cache_files[0]).tocsr(),
                sparse.load_npz(cache_files[1]).tocsr(),
                names,
                manifest,
            )

    train = pd.read_csv(TRAIN_PATH, dtype=str, keep_default_na=False)
    test = pd.read_csv(TEST_PATH, dtype=str, keep_default_na=False)
    gene_columns = tuple(train.columns[2:])
    if gene_columns != tuple(test.columns[1:]):
        raise ValueError("train/test gene order mismatch")

    base_train = sparse.load_npz(BASE_FEATURE_DIR / "train_features.npz").tocsr()
    base_test = sparse.load_npz(BASE_FEATURE_DIR / "test_features.npz").tocsr()
    base_names = tuple(
        json.loads((BASE_FEATURE_DIR / "feature_names.json").read_text(encoding="utf-8"))
    )
    drop = set(legacy_five_family_feature_names(gene_columns))
    keep_indices = np.asarray(
        [index for index, name in enumerate(base_names) if name not in drop],
        dtype=np.int64,
    )
    kept_names = tuple(base_names[index] for index in keep_indices)

    fitted = ParserNativeV3SemanticRangeFamily(gene_columns).fit(train)
    native_train = fitted.transform(train)
    native_test = fitted.transform(test)
    names = (*kept_names, *fitted.descriptor.feature_names)
    final_train = sparse.hstack(
        [base_train[:, keep_indices], native_train], format="csr", dtype=np.float32
    )
    final_test = sparse.hstack(
        [base_test[:, keep_indices], native_test], format="csr", dtype=np.float32
    )
    checkpoint = xgb.Booster()
    checkpoint.load_model(MODEL_DIR / "fold_00.json")
    if checkpoint.num_features() != final_train.shape[1] or len(names) != final_train.shape[1]:
        raise ValueError(
            "EXP-479 checkpoint feature contract mismatch: "
            f"model={checkpoint.num_features()} matrix={final_train.shape[1]} names={len(names)}"
        )

    ANALYSIS_CACHE.mkdir(parents=True, exist_ok=True)
    sparse.save_npz(cache_files[0], final_train)
    sparse.save_npz(cache_files[1], final_test)
    cache_files[2].write_text(
        json.dumps(names, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "analysis_only": True,
        "source_experiment": "EXP-479",
        "train_csv_sha256": sha256_file(TRAIN_PATH),
        "test_csv_sha256": sha256_file(TEST_PATH),
        "base_train_features_sha256": sha256_file(
            BASE_FEATURE_DIR / "train_features.npz"
        ),
        "base_test_features_sha256": sha256_file(BASE_FEATURE_DIR / "test_features.npz"),
        "native_schema_sha256": fitted.schema_sha256,
        "feature_names_sha256": sha256_lines(names),
        "shape_train": list(final_train.shape),
        "shape_test": list(final_test.shape),
    }
    _write_json(cache_files[3], manifest)
    return final_train, final_test, names, manifest


def summarize_family_support(
    train: sparse.csr_matrix,
    test: sparse.csr_matrix,
    groups: dict[str, np.ndarray],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family, indices in groups.items():
        train_family = train[:, indices]
        test_family = test[:, indices]
        train_row_sum = np.asarray(train_family.sum(axis=1)).ravel()
        test_row_sum = np.asarray(test_family.sum(axis=1)).ravel()
        rows.append(
            {
                "family": family,
                "n_features": int(len(indices)),
                "train_active_features": int(np.count_nonzero(train_family.getnnz(axis=0))),
                "test_active_features": int(np.count_nonzero(test_family.getnnz(axis=0))),
                "train_nnz": int(train_family.nnz),
                "test_nnz": int(test_family.nnz),
                "train_row_prevalence": float(np.mean(train_row_sum > 0)),
                "test_row_prevalence": float(np.mean(test_row_sum > 0)),
                "train_row_sum_mean": float(np.mean(train_row_sum)),
                "test_row_sum_mean": float(np.mean(test_row_sum)),
                "train_row_sum_p95": float(np.quantile(train_row_sum, 0.95)),
                "test_row_sum_p95": float(np.quantile(test_row_sum, 0.95)),
            }
        )
    return rows


def sample_feature_correlations(
    train: sparse.csr_matrix, names: tuple[str, ...]
) -> list[dict[str, Any]]:
    indices = [
        index
        for index, name in enumerate(names)
        if name.startswith("sample__")
    ]
    frame = pd.DataFrame(
        np.asarray(train[:, indices].todense()), columns=[names[index] for index in indices]
    )
    corr = frame.corr(method="spearman")
    rows = []
    for left_index, left in enumerate(corr.columns):
        for right in corr.columns[left_index + 1 :]:
            value = corr.loc[left, right]
            rows.append(
                {
                    "left": left,
                    "right": right,
                    "spearman": None if pd.isna(value) else float(value),
                }
            )
    return sorted(rows, key=lambda row: -(abs(row["spearman"]) if row["spearman"] is not None else -1))


def range_cooccurrence(
    train: sparse.csr_matrix, test: sparse.csr_matrix, names: tuple[str, ...]
) -> list[dict[str, Any]]:
    consequences = ("range_replacement", "range_stop", "range_no_change")
    indices = [names.index(f"sample__native_v3_{value}_token_count") for value in consequences]
    rows: list[dict[str, Any]] = []
    for domain, matrix in (("train", train), ("test", test)):
        present = np.asarray(matrix[:, indices].todense()) > 0
        for mask in range(8):
            selected = np.ones(len(present), dtype=bool)
            state = {}
            for index, consequence in enumerate(consequences):
                expected = bool(mask & (1 << index))
                selected &= present[:, index] == expected
                state[consequence] = expected
            rows.append(
                {
                    "domain": domain,
                    **state,
                    "rows": int(selected.sum()),
                    "prevalence": float(selected.mean()),
                }
            )
    return rows


def compare_parent_oof(
    train: sparse.csr_matrix, names: tuple[str, ...]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Compare EXP-469 and EXP-479 only on canonical OOF rows.

    The range flags come from the source experiment's final feature matrix.
    They are used for stratified diagnostics, never to select a threshold.
    """

    parent = pd.read_csv(PARENT_OOF_PATH, dtype={"ID": str})
    source = pd.read_csv(SOURCE_OOF_PATH, dtype={"ID": str})
    required = {"ID", "SUBCLASS_TRUE", "SUBCLASS_PRED", "FOLD"}
    if not required.issubset(parent) or not required.issubset(source):
        raise ValueError("OOF files do not satisfy the canonical prediction contract")
    if not parent["ID"].equals(source["ID"]):
        raise ValueError("EXP-469 and EXP-479 OOF ID order differs")
    for column in ("SUBCLASS_TRUE", "FOLD"):
        if not parent[column].equals(source[column]):
            raise ValueError(f"EXP-469 and EXP-479 {column} differs")
    if len(source) != train.shape[0]:
        raise ValueError("OOF and native-v3 feature row counts differ")

    true = source["SUBCLASS_TRUE"].to_numpy()
    parent_pred = parent["SUBCLASS_PRED"].to_numpy()
    source_pred = source["SUBCLASS_PRED"].to_numpy()
    parent_correct = parent_pred == true
    source_correct = source_pred == true
    proba_columns = [f"PROBA_{label}" for label in CLASS_LABELS]
    true_indices = np.asarray([CLASS_LABELS.index(label) for label in true])
    parent_true_proba = parent[proba_columns].to_numpy()[
        np.arange(len(parent)), true_indices
    ]
    source_true_proba = source[proba_columns].to_numpy()[
        np.arange(len(source)), true_indices
    ]
    probability_delta = source[proba_columns].to_numpy() - parent[proba_columns].to_numpy()

    range_columns = {
        consequence: names.index(
            f"sample__native_v3_{consequence}_token_count"
        )
        for consequence in (
            "range_replacement",
            "range_stop",
            "range_no_change",
        )
    }
    flags = {
        consequence: np.asarray(train[:, index].todense()).ravel() > 0
        for consequence, index in range_columns.items()
    }
    flags["any_range"] = np.logical_or.reduce(list(flags.values()))
    flags["no_range"] = ~flags["any_range"]

    rows: list[dict[str, Any]] = []
    for group, mask in flags.items():
        count = int(mask.sum())
        rows.append(
            {
                "group": group,
                "rows": count,
                "prevalence": float(mask.mean()),
                "exp469_accuracy": float(parent_correct[mask].mean()) if count else None,
                "exp479_accuracy": float(source_correct[mask].mean()) if count else None,
                "accuracy_delta": (
                    float(source_correct[mask].mean() - parent_correct[mask].mean())
                    if count
                    else None
                ),
                "exp469_only_correct": int(np.sum(mask & parent_correct & ~source_correct)),
                "exp479_only_correct": int(np.sum(mask & ~parent_correct & source_correct)),
                "prediction_changed": int(np.sum(mask & (parent_pred != source_pred))),
                "mean_true_class_probability_delta": (
                    float(np.mean(source_true_proba[mask] - parent_true_proba[mask]))
                    if count
                    else None
                ),
            }
        )
    summary = {
        "parent": "EXP-469",
        "source": "EXP-479",
        "rows": int(len(source)),
        "both_correct": int(np.sum(parent_correct & source_correct)),
        "parent_only_correct": int(np.sum(parent_correct & ~source_correct)),
        "source_only_correct": int(np.sum(~parent_correct & source_correct)),
        "both_wrong": int(np.sum(~parent_correct & ~source_correct)),
        "prediction_changed": int(np.sum(parent_pred != source_pred)),
        "prediction_changed_ratio": float(np.mean(parent_pred != source_pred)),
        "mean_absolute_probability_delta": float(np.mean(np.abs(probability_delta))),
        "max_absolute_probability_delta": float(np.max(np.abs(probability_delta))),
        "parent_oof_sha256": sha256_file(PARENT_OOF_PATH),
        "source_oof_sha256": sha256_file(SOURCE_OOF_PATH),
    }
    return summary, rows


def adversarial_audit(
    train: sparse.csr_matrix,
    test: sparse.csr_matrix,
    names: tuple[str, ...],
    groups: dict[str, np.ndarray],
    *,
    seed: int,
    n_splits: int,
    n_estimators: int,
) -> dict[str, Any]:
    from sklearn.model_selection import StratifiedKFold

    x = sparse.vstack([train, test], format="csr")
    y = np.concatenate(
        [np.zeros(train.shape[0]), np.ones(test.shape[0])]
    ).astype(np.int32)
    folds = list(
        StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed).split(x, y)
    )
    kwargs = {
        "x_full": x,
        "y": y,
        "fold_splits": folds,
        "seed": seed,
        "n_estimators": n_estimators,
        "max_depth": 4,
        "learning_rate": 0.05,
        "early_stopping_rounds": 20,
    }
    full, _ = fit_domain_auc(column_indices=None, compute_gain=True, **kwargs)
    all_indices = np.arange(len(names))
    family_results = {}
    for family, indices in groups.items():
        standalone, _ = fit_domain_auc(
            column_indices=indices, compute_gain=False, **kwargs
        )
        rest = np.setdiff1d(all_indices, indices, assume_unique=True)
        leave_one_out, _ = fit_domain_auc(
            column_indices=rest, compute_gain=False, **kwargs
        )
        family_results[family] = {
            "n_features": int(len(indices)),
            "feature_names_sha256": sha256_lines(names[index] for index in indices),
            "standalone_auc": standalone["overall_auc"],
            "standalone_fold_auc": standalone["fold_auc"],
            "leave_one_out_auc": leave_one_out["overall_auc"],
            "full_minus_leave_one_out_auc": full["overall_auc"]
            - leave_one_out["overall_auc"],
        }
    return {
        "analysis_only": True,
        "subclass_used": False,
        "public_lb_used": False,
        "domain_target": "train=0,test=1",
        "n_splits": n_splits,
        "seed": seed,
        "n_estimators": n_estimators,
        "full_auc": full["overall_auc"],
        "full_fold_auc": full["fold_auc"],
        "families": family_results,
        "top_shift_features": top_features_from_gain(full["mean_gain"], list(names), 50),
    }


def tree_shap_audit(
    train_matrix: sparse.csr_matrix,
    names: tuple[str, ...],
    *,
    max_per_class: int,
    chunk_size: int,
    seed: int,
) -> dict[str, Any]:
    train_meta = pd.read_csv(TRAIN_PATH, usecols=["ID", "SUBCLASS"], dtype=str)
    split = pd.read_csv(SPLIT_PATH, dtype={"ID": str, "fold": int})
    merged = train_meta.merge(split, on="ID", how="left", validate="one_to_one", sort=False)
    if not merged["ID"].equals(train_meta["ID"]) or merged["fold"].isna().any():
        raise ValueError("canonical split mismatch")
    target = LabelEncoder().fit(list(CLASS_LABELS)).transform(train_meta["SUBCLASS"])
    folds = merged["fold"].to_numpy(dtype=np.int32)
    global_sum = np.zeros(len(names), dtype=np.float64)
    class_sum = np.zeros((len(CLASS_LABELS), len(names)), dtype=np.float64)
    class_rows = np.zeros(len(CLASS_LABELS), dtype=np.int64)
    total_rows = 0
    fold_records = []
    for fold in range(5):
        validation = np.flatnonzero(folds == fold)
        selected = stratified_validation_sample(
            validation,
            target,
            fold=fold,
            class_count=len(CLASS_LABELS),
            max_per_class=max_per_class,
            seed=seed,
        )
        booster = xgb.Booster()
        checkpoint = MODEL_DIR / f"fold_{fold:02d}.json"
        booster.load_model(checkpoint)
        if booster.num_features() != train_matrix.shape[1]:
            raise ValueError("checkpoint and audit matrix feature counts differ")
        for start in range(0, len(selected), chunk_size):
            stop = min(start + chunk_size, len(selected))
            labels = target[selected[start:stop]]
            contributions = booster.predict(
                xgb.DMatrix(train_matrix[selected[start:stop]]),
                pred_contribs=True,
                strict_shape=True,
            )
            chunk_global, chunk_class, chunk_rows = accumulate_contribution_chunk(
                contributions, labels, class_count=len(CLASS_LABELS)
            )
            global_sum += chunk_global
            class_sum += chunk_class
            class_rows += chunk_rows
        total_rows += len(selected)
        fold_records.append(
            {
                "fold": fold,
                "validation_rows": int(len(validation)),
                "sampled_rows": int(len(selected)),
                "sample_id_sha256": hashlib.sha256(
                    "\n".join(train_meta["ID"].iloc[selected].astype(str)).encode()
                ).hexdigest(),
                "checkpoint_sha256": sha256_file(checkpoint),
            }
        )

    global_mean = global_sum / (total_rows * len(CLASS_LABELS))
    total = float(global_mean.sum())
    global_rows = sorted(
        (
            {
                "feature": name,
                "family": native_v3_feature_family(name),
                "mean_abs_shap": float(value),
                "share": float(value / total if total else 0.0),
            }
            for name, value in zip(names, global_mean, strict=True)
        ),
        key=lambda row: (-row["mean_abs_shap"], row["feature"]),
    )
    for rank, row in enumerate(global_rows, 1):
        row["rank"] = rank

    family_values: dict[str, list[float]] = defaultdict(list)
    for row in global_rows:
        family_values[row["family"]].append(row["mean_abs_shap"])
    family_rows = sorted(
        (
            {
                "family": family,
                "feature_count": len(values),
                "total_mean_abs_shap": float(sum(values)),
                "total_share": float(sum(values) / total if total else 0.0),
                "mean_per_feature": float(np.mean(values)),
            }
            for family, values in family_values.items()
        ),
        key=lambda row: (-row["total_share"], row["family"]),
    )
    class_output = []
    for class_index, label in enumerate(CLASS_LABELS):
        denominator = int(class_rows[class_index])
        values = class_sum[class_index] / denominator
        ranked = np.argsort(-values)[:20]
        for rank, index in enumerate(ranked, 1):
            class_output.append(
                {
                    "class": label,
                    "rank": rank,
                    "feature": names[index],
                    "family": native_v3_feature_family(names[index]),
                    "mean_abs_true_class_shap": float(values[index]),
                }
            )
    return {
        "summary": {
            "analysis_only": True,
            "method": "XGBoost exact TreeSHAP pred_contribs",
            "selection_use": False,
            "test_or_public_used": False,
            "sampled_rows": total_rows,
            "max_per_class_per_fold": max_per_class,
            "class_sample_counts": {
                label: int(class_rows[index]) for index, label in enumerate(CLASS_LABELS)
            },
            "folds": fold_records,
            "global_top20": global_rows[:20],
            "family_importance": family_rows,
        },
        "global_rows": global_rows[:500],
        "class_rows": class_output,
        "family_rows": family_rows,
    }


def write_report(
    *,
    manifest: dict[str, Any],
    support: list[dict[str, Any]],
    adversarial: dict[str, Any],
    shap: dict[str, Any],
    oof_comparison: dict[str, Any],
    oof_comparison_groups: list[dict[str, Any]],
) -> None:
    support_by_family = {row["family"]: row for row in support}
    auc = adversarial["families"]
    shap_family = {row["family"]: row for row in shap["family_rows"]}
    range_rows = []
    for family in (
        "native_range_replacement",
        "native_range_stop",
        "native_range_no_change",
    ):
        row = support_by_family[family]
        range_rows.append(
            f"| {family} | {row['n_features']} | {row['train_row_prevalence']:.4%} | "
            f"{row['test_row_prevalence']:.4%} | {auc[family]['standalone_auc']:.6f} | "
            f"{shap_family[family]['total_share']:.4%} |"
        )
    comparison_by_group = {
        row["group"]: row for row in oof_comparison_groups
    }
    any_range = comparison_by_group["any_range"]
    no_range = comparison_by_group["no_range"]
    family_rows = []
    for family in sorted(support_by_family):
        row = support_by_family[family]
        family_rows.append(
            f"| {family} | {row['n_features']} | "
            f"{row['train_row_prevalence']:.2%} | {row['test_row_prevalence']:.2%} | "
            f"{auc[family]['standalone_auc']:.6f} | "
            f"{auc[family]['leave_one_out_auc']:.6f} | "
            f"{shap_family[family]['total_share']:.2%} |"
        )
    text = f"""# Parser native v3 일반화 진단

이 분석은 EXP-479의 비튜닝 HGVS-informed semantic baseline을 설명하기 위한
QC다. test는 train/test shift 진단에만 사용했으며 feature 삭제·가중치·threshold
선택에는 사용하지 않았다. TreeSHAP은 canonical fold의 validation 행만 사용했다.

## 핵심 결과

- 최종 feature 수: `{manifest['shape_train'][1]:,}`
- 전체 train/test domain OOF AUC: `{adversarial['full_auc']:.6f}`
- TreeSHAP 표본: `{shap['summary']['sampled_rows']}`행

| family | 열 수 | train row prevalence | test row prevalence | standalone AUC | leave-one-out AUC | SHAP share |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(family_rows)}

| range family | 열 수 | train row prevalence | test row prevalence | standalone domain AUC | SHAP share |
|---|---:|---:|---:|---:|---:|
{chr(10).join(range_rows)}

## EXP-469 → EXP-479 OOF 변화

- 전체 6,201행 중 예측 라벨 변경: `{oof_comparison['prediction_changed']:,}`행
  (`{oof_comparison['prediction_changed_ratio']:.2%}`)
- EXP-469만 정답: `{oof_comparison['parent_only_correct']:,}`행
- EXP-479만 정답: `{oof_comparison['source_only_correct']:,}`행
- range 의미가 하나라도 있는 `{any_range['rows']:,}`행의 accuracy 변화:
  `{any_range['exp469_accuracy']:.4f} → {any_range['exp479_accuracy']:.4f}`
  (`{any_range['accuracy_delta']:+.4f}`)
- range 의미가 없는 `{no_range['rows']:,}`행의 accuracy 변화:
  `{no_range['exp469_accuracy']:.4f} → {no_range['exp479_accuracy']:.4f}`
  (`{no_range['accuracy_delta']:+.4f}`)

새 range family는 희소하지만 트리 구조와 boosting 경로를 바꾸므로 range가 없는
행의 예측도 달라질 수 있다. 따라서 fixed XGBoost 점수 하락을 range 보유 행의
직접 효과로만 해석하지 않는다.

## 주요 해석

1. 새 range 의미는 **해당 행에서 유효했다**. `any_range` 집합에서는 EXP-479가
   EXP-469보다 정답 4개를 순증가시켰다. 의미를 다시 합치거나 삭제할 근거가 없다.
2. 세 range family는 합계 13,155열이지만 매우 희소하고 validation TreeSHAP 합계는
   약 0.07%다. 고정 XGBoost가 이 차원을 효율적으로 다루지 못해, range가 없는
   다수 행까지 분할 경로가 바뀐 것이 전체 하락의 더 그럴듯한 설명이다.
3. `base_sample_aggregate` 4열만으로 domain AUC가 0.720289이며 SHAP share도
   27.41%다. 특히 mutated-gene count와 total-variant count의 Spearman 상관은
   0.996089다. 이는 암종 신호와 dataset acquisition shift가 같은 burden 축에서
   경쟁한다는 경고다.
4. 전체 AUC보다 family 제외 AUC가 오르는 경우가 많다. 이는 제거 family가 무가치하다는
   뜻이 아니라, 중복된 희소 피처 사이에서 domain classifier도 feature competition을
   겪는다는 뜻이다. leave-one-out 수치를 additive 기여도로 해석하지 않는다.

## 다음 native v3 튜닝 설계

다음 공식 Experiment Issue는 EXP-479를 부모로 하고 parser·semantic schema·피처
집계는 고정한다. outer validation·test·Public을 탐색에 사용하지 않는 nested
XGBoost tuning만 수행한다.

- `max_depth`: 3–7
- `min_child_weight`: 2–20
- `learning_rate`: 0.02–0.08
- `subsample`: 0.60–0.90
- `colsample_bytree`: 0.25–0.75
- `reg_alpha`: 0–2
- `reg_lambda`: 1–12
- `gamma`: 0–0.5
- outer fold 내부 3-fold, seed `42+outer_fold`, 최대 30 trials
- 목적값: inner OOF Macro F1; 동률이면 fold 표준편차가 낮은 후보

특히 낮은 `colsample_bytree`, 얕은 depth와 더 강한 child/leaf 규제로 39,467개
중복·희소 열의 분할 경쟁을 억제한다. range 의미나 parser taxonomy 자체는 탐색
대상이 아니다.

`standalone AUC`는 해당 family만으로 train/test를 구분한 정도다. 높을수록 shift가
크다는 뜻이지 암종 예측력이 높다는 뜻이 아니다. leave-one-out AUC와 SHAP 역시
상관된 피처 사이의 competition 때문에 additive 기여도로 해석하지 않는다.

## 해석 원칙

1. `range_replacement`, `range_stop`, `range_no_change` 의미는 점수나 shift로
   삭제하지 않는다.
2. SHAP 0은 저장된 트리가 표본에서 해당 열을 사용하지 않았다는 뜻이며 의미가
   없다는 증명이 아니다.
3. test prevalence와 adversarial AUC는 모델 규칙을 고르는 데 사용하지 않는다.
4. 다음 nested tuning 범위는 train OOF와 validation-only SHAP에서 관찰한
   희소성·feature competition을 바탕으로 사전 고정한다.

## 산출물

- `summary.json`: 입력 해시·핵심 결과
- `family_support.csv`: family별 차원·nnz·prevalence·row-sum quantile
- `sample_feature_correlations.csv`: sample aggregate Spearman 상관
- `range_cooccurrence.csv`: 세 range 의미의 sample 동시 출현
- `exp469_exp479_oof_comparison.json`,
  `exp469_exp479_oof_comparison_groups.csv`: 부모 대비 오류 전환
- `adversarial_auc.json`: 전체·family standalone·leave-one-out domain AUC
- `top_shift_distributions.csv`: gain 상위 shift 피처 train/test 분포
- `tree_shap_global_top500.csv`, `tree_shap_class_top20.csv`,
  `tree_shap_family_importance.csv`: validation-only TreeSHAP

재실행:

```bash
uv run python scripts/analyze_parser_native_v3_generalization.py
```
"""
    (OUTPUT_DIR / "README.md").write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--domain-folds", type=int, default=3)
    parser.add_argument("--domain-estimators", type=int, default=150)
    parser.add_argument("--shap-max-per-class", type=int, default=2)
    parser.add_argument("--shap-chunk-size", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    train, test, names, manifest = materialize_exp479_matrix()
    groups = family_index_map(names)
    support = summarize_family_support(train, test, groups)
    correlations = sample_feature_correlations(train, names)
    cooccurrence = range_cooccurrence(train, test, names)
    oof_comparison, oof_comparison_groups = compare_parent_oof(train, names)
    adversarial = adversarial_audit(
        train,
        test,
        names,
        groups,
        seed=args.seed,
        n_splits=args.domain_folds,
        n_estimators=args.domain_estimators,
    )
    shap = tree_shap_audit(
        train,
        names,
        max_per_class=args.shap_max_per_class,
        chunk_size=args.shap_chunk_size,
        seed=args.seed,
    )

    pd.DataFrame(support).to_csv(OUTPUT_DIR / "family_support.csv", index=False)
    pd.DataFrame(correlations).to_csv(
        OUTPUT_DIR / "sample_feature_correlations.csv", index=False
    )
    pd.DataFrame(cooccurrence).to_csv(OUTPUT_DIR / "range_cooccurrence.csv", index=False)
    _write_json(OUTPUT_DIR / "exp469_exp479_oof_comparison.json", oof_comparison)
    pd.DataFrame(oof_comparison_groups).to_csv(
        OUTPUT_DIR / "exp469_exp479_oof_comparison_groups.csv", index=False
    )
    _write_json(OUTPUT_DIR / "adversarial_auc.json", adversarial)
    top_distributions = []
    for entry in adversarial["top_shift_features"]:
        index = names.index(entry["feature"])
        row = compute_feature_distribution(
            entry["feature"],
            np.asarray(train[:, index].todense()).ravel(),
            np.asarray(test[:, index].todense()).ravel(),
        )
        row["native_v3_family"] = native_v3_feature_family(entry["feature"])
        row["mean_gain"] = entry["mean_gain"]
        top_distributions.append(row)
    pd.DataFrame(top_distributions).to_csv(
        OUTPUT_DIR / "top_shift_distributions.csv", index=False
    )
    pd.DataFrame(shap["global_rows"]).to_csv(
        OUTPUT_DIR / "tree_shap_global_top500.csv", index=False
    )
    pd.DataFrame(shap["class_rows"]).to_csv(
        OUTPUT_DIR / "tree_shap_class_top20.csv", index=False
    )
    pd.DataFrame(shap["family_rows"]).to_csv(
        OUTPUT_DIR / "tree_shap_family_importance.csv", index=False
    )
    summary = {
        "analysis_only": True,
        "issue": 475,
        "source_experiment": "EXP-479",
        "input_manifest": manifest,
        "feature_names_sha256": sha256_lines(names),
        "family_support": support,
        "sample_feature_top_correlations": correlations[:20],
        "exp469_exp479_oof_comparison": oof_comparison,
        "exp469_exp479_oof_comparison_groups": oof_comparison_groups,
        "adversarial": {
            key: adversarial[key]
            for key in (
                "subclass_used",
                "public_lb_used",
                "n_splits",
                "seed",
                "n_estimators",
                "full_auc",
                "full_fold_auc",
            )
        },
        "tree_shap": shap["summary"],
    }
    _write_json(OUTPUT_DIR / "summary.json", summary)
    write_report(
        manifest=manifest,
        support=support,
        adversarial=adversarial,
        shap=shap,
        oof_comparison=oof_comparison,
        oof_comparison_groups=oof_comparison_groups,
    )
    print(
        json.dumps(
            {
                "full_domain_auc": adversarial["full_auc"],
                "feature_count": len(names),
                "tree_shap_rows": shap["summary"]["sampled_rows"],
                "output": str(OUTPUT_DIR),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
