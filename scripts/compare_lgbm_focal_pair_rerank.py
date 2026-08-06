#!/usr/bin/env python
"""Compare LightGBM focal loss and two fold-safe confusion-pair specialists."""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.constants import CLASS_LABELS
from open_cancer.hotspot_features import build_hotspot_augmented_features
from open_cancer.lgbm_focal import make_sigmoid_focal_objective, softmax
from open_cancer.parser_baseline_features import legacy_five_family_feature_names
from open_cancer.parser_native_v3_features import ParserNativeV3SemanticRangeFamily
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
)


ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "data/raw/train.csv"
TEST = ROOT / "data/raw/test.csv"
OUTPUT = ROOT / "reports/analysis/lgbm_focal_pair_rerank_2x2"
CACHE = ROOT / "data/processed/task622_lgbm_focal_pair_rerank"
SPLIT_SEED = 20240807
MODEL_SEED = 42
ALPHA = 0.25
GAMMA = 1.0

BASE_PARAMETERS = {
    "learning_rate": 0.03,
    "num_leaves": 31,
    "max_depth": -1,
    "min_child_samples": 20,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_alpha": 0.0,
    "reg_lambda": 1.0,
    "verbosity": -1,
    "deterministic": True,
    "force_col_wise": True,
    "num_threads": 8,
    "seed": MODEL_SEED,
}
PAIR_SPECS = {
    "KIPAN_KIRC": {
        "labels": ("KIPAN", "KIRC"),
        "num_leaves": 20,
        "n_estimators": 10,
        "learning_rate": 0.1,
        "min_child_samples": 20,
    },
    "GBMLGG_LGG": {
        "labels": ("GBMLGG", "LGG"),
        "num_leaves": 20,
        "n_estimators": 100,
        "learning_rate": 0.02,
        "min_child_samples": 10,
    },
}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def macro_metric(predictions: np.ndarray, dataset):
    labels = np.asarray(dataset.get_label(), dtype=np.int32)
    scores = np.asarray(predictions)
    if scores.ndim == 1:
        scores = scores.reshape(labels.size, len(CLASS_LABELS), order="F")
    return (
        "macro_f1",
        float(f1_score(labels, scores.argmax(axis=1), average="macro", zero_division=0)),
        True,
    )


def build_features() -> tuple[sparse.csr_matrix, tuple[str, ...], pd.DataFrame]:
    CACHE.mkdir(parents=True, exist_ok=True)
    base_report = build_hotspot_augmented_features(
        TRAIN,
        TEST,
        CACHE / "base",
        hotspots=(),
        base_feature_options={
            "selected_robust_aggregates": (),
            "selected_position_features": (),
            "mutation_cell_parser": parse_stop_notation_invariant_cell,
            "mutation_parser_contract": STOP_NOTATION_PARSER_CONTRACT,
        },
        hotspot_token_normalizer=normalize_stop_notation_token,
    )
    base_dir = Path(str(base_report["base_dir"]))
    base_matrix = sparse.load_npz(base_dir / "train_features.npz").tocsr()
    base_names = tuple(json.loads((base_dir / "feature_names.json").read_text()))
    train = pd.read_csv(TRAIN, dtype=str, keep_default_na=False)
    genes = tuple(train.columns[2:])
    legacy = frozenset(legacy_five_family_feature_names(genes))
    keep_indices = np.fromiter(
        (index for index, name in enumerate(base_names) if name not in legacy),
        dtype=np.int64,
    )
    native = ParserNativeV3SemanticRangeFamily(genes).fit(train)
    native_matrix = native.transform(train)
    matrix = sparse.hstack(
        [base_matrix[:, keep_indices], native_matrix], format="csr", dtype=np.float32
    )
    names = tuple(base_names[index] for index in keep_indices) + native.descriptor.feature_names
    return matrix, names, train


def train_base(
    mode: str,
    x_train,
    y_train: np.ndarray,
    x_valid,
    y_valid: np.ndarray,
    *,
    fold: int,
) -> tuple[np.ndarray, int]:
    parameters = {**BASE_PARAMETERS, "seed": MODEL_SEED + fold, "num_class": len(CLASS_LABELS)}
    train_weight = None
    if mode == "balanced":
        parameters.update(objective="multiclass", metric="None")
        train_weight = compute_sample_weight("balanced", y_train)
    elif mode == "focal":
        parameters.update(
            objective=make_sigmoid_focal_objective(
                alpha=ALPHA, gamma=GAMMA, num_class=len(CLASS_LABELS)
            ),
            metric="None",
        )
    else:
        raise ValueError(mode)
    train_set = lgb.Dataset(x_train, label=y_train, weight=train_weight, free_raw_data=False)
    valid_set = lgb.Dataset(x_valid, label=y_valid, reference=train_set, free_raw_data=False)
    booster = lgb.train(
        parameters,
        train_set,
        num_boost_round=1200,
        valid_sets=[valid_set],
        valid_names=["validation"],
        feval=macro_metric,
        callbacks=[lgb.early_stopping(60, first_metric_only=True, verbose=False)],
    )
    prediction = booster.predict(
        x_valid,
        num_iteration=booster.best_iteration,
        raw_score=mode == "focal",
    )
    probabilities = softmax(prediction) if mode == "focal" else np.asarray(prediction)
    return probabilities, int(booster.best_iteration)


def fit_pair_specialists(x_train, y_train: np.ndarray, fold: int):
    models = {}
    for name, spec in PAIR_SPECS.items():
        left, right = (CLASS_LABELS.index(label) for label in spec["labels"])
        mask = np.isin(y_train, [left, right])
        binary = (y_train[mask] == right).astype(np.int32)
        model = lgb.LGBMClassifier(
            objective="binary",
            random_state=MODEL_SEED + fold,
            verbosity=-1,
            deterministic=True,
            force_col_wise=True,
            n_jobs=8,
            reg_alpha=0.0,
            reg_lambda=0.0,
            **{key: value for key, value in spec.items() if key not in {"labels"}},
        )
        model.fit(x_train[mask], binary)
        models[name] = (model, left, right)
    return models


def rerank_predictions(
    base_predictions: np.ndarray,
    x_valid,
    models,
) -> tuple[np.ndarray, dict[str, object]]:
    corrected = base_predictions.copy()
    audit: dict[str, object] = {}
    for name, (model, left, right) in models.items():
        gate = np.isin(corrected, [left, right])
        before = corrected[gate].copy()
        if gate.any():
            binary = model.predict(x_valid[gate]).astype(np.int32)
            corrected[gate] = np.where(binary == 1, right, left)
        audit[name] = {
            "gated_rows": int(gate.sum()),
            "changed_rows": int(np.sum(before != corrected[gate])),
        }
    return corrected, audit


def summarize(y: np.ndarray, predictions: np.ndarray, fold_assignments: np.ndarray) -> dict:
    fold_scores = [
        float(f1_score(y[fold_assignments == fold], predictions[fold_assignments == fold], average="macro", zero_division=0))
        for fold in range(5)
    ]
    return {
        "macro_f1": float(f1_score(y, predictions, average="macro", zero_division=0)),
        "accuracy": float(accuracy_score(y, predictions)),
        "fold_scores": fold_scores,
        "fold_mean": float(np.mean(fold_scores)),
        "fold_std": float(np.std(fold_scores)),
        "per_class_f1": {
            label: float(score)
            for label, score in zip(
                CLASS_LABELS,
                f1_score(y, predictions, labels=np.arange(len(CLASS_LABELS)), average=None, zero_division=0),
                strict=True,
            )
        },
        "confusion_matrix": confusion_matrix(y, predictions, labels=np.arange(len(CLASS_LABELS))).tolist(),
    }


def main() -> None:
    started = time.perf_counter()
    matrix, feature_names, train = build_features()
    encoder = LabelEncoder().fit(list(CLASS_LABELS))
    y = encoder.transform(train["SUBCLASS"]).astype(np.int32)
    splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=SPLIT_SEED)
    folds = np.full(len(train), -1, dtype=np.int32)
    oof_probability = {
        "balanced": np.full((len(train), len(CLASS_LABELS)), np.nan),
        "focal": np.full((len(train), len(CLASS_LABELS)), np.nan),
    }
    oof_reranked = {
        "balanced": np.full(len(train), -1, dtype=np.int32),
        "focal": np.full(len(train), -1, dtype=np.int32),
    }
    fold_audit = []
    for fold, (train_indices, valid_indices) in enumerate(splitter.split(matrix, y)):
        folds[valid_indices] = fold
        pair_models = fit_pair_specialists(matrix[train_indices], y[train_indices], fold)
        item = {"fold": fold, "train_rows": len(train_indices), "validation_rows": len(valid_indices)}
        for mode in ("balanced", "focal"):
            probability, best_iteration = train_base(
                mode,
                matrix[train_indices],
                y[train_indices],
                matrix[valid_indices],
                y[valid_indices],
                fold=fold,
            )
            oof_probability[mode][valid_indices] = probability
            reranked, rerank_audit = rerank_predictions(
                probability.argmax(axis=1), matrix[valid_indices], pair_models
            )
            oof_reranked[mode][valid_indices] = reranked
            item[mode] = {
                "best_iteration": best_iteration,
                "base_macro_f1": float(f1_score(y[valid_indices], probability.argmax(axis=1), average="macro", zero_division=0)),
                "reranked_macro_f1": float(f1_score(y[valid_indices], reranked, average="macro", zero_division=0)),
                "rerank": rerank_audit,
            }
        fold_audit.append(item)
        print(json.dumps(item, ensure_ascii=False))

    results = {}
    for mode in ("balanced", "focal"):
        base_prediction = oof_probability[mode].argmax(axis=1)
        results[f"{mode}_base"] = {
            **summarize(y, base_prediction, folds),
            "log_loss": float(log_loss(y, oof_probability[mode], labels=np.arange(len(CLASS_LABELS)))),
        }
        results[f"{mode}_pair_rerank"] = {
            **summarize(y, oof_reranked[mode], folds),
            "log_loss": None,
            "log_loss_note": "label-only specialist rerank; base probabilities are not recalibrated",
            "changed_rows": int(np.sum(base_prediction != oof_reranked[mode])),
        }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"ID": train["ID"], "SUBCLASS": train["SUBCLASS"], "fold": folds}).to_csv(
        OUTPUT / "split_assignments.csv", index=False, lineterminator="\n"
    )
    oof = pd.DataFrame({"ID": train["ID"], "SUBCLASS_TRUE": train["SUBCLASS"], "fold": folds})
    for mode in ("balanced", "focal"):
        oof[f"{mode}_base"] = encoder.inverse_transform(oof_probability[mode].argmax(axis=1))
        oof[f"{mode}_pair_rerank"] = encoder.inverse_transform(oof_reranked[mode])
    oof.to_csv(OUTPUT / "oof_labels.csv", index=False, lineterminator="\n")
    payload = {
        "status": "COMPLETED",
        "run_mode": "explore",
        "issue": 622,
        "split": {
            "class": "StratifiedKFold",
            "n_splits": 5,
            "shuffle": True,
            "random_state": SPLIT_SEED,
            "canonical_split_used": False,
        },
        "features": {
            "representation": "parser_v4_native_v3_semantic_range",
            "shape": list(matrix.shape),
            "nonzero": int(matrix.nnz),
            "feature_count": len(feature_names),
        },
        "models": {
            "base_parameters": BASE_PARAMETERS,
            "focal": {"alpha": ALPHA, "gamma": GAMMA, "form": "one_vs_rest_sigmoid"},
            "pair_specialists": PAIR_SPECS,
        },
        "results": results,
        "fold_audit": fold_audit,
        "runtime_seconds": time.perf_counter() - started,
    }
    write_json(OUTPUT / "metrics.json", payload)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
