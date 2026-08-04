#!/usr/bin/env python
"""Diagnostic-only: ElasticNet logistic regression on the EXP-334 feature set,
swept over regularization strength, to check whether a linear model is more
robust to the train/test shift than XGBoost (EXP-334 baseline).

Not an official experiment: no EXP-ID, no EXPERIMENT_HISTORY entry, no
schema-validated artifacts. Reuses EXP-334's exact base-feature config
(configs/exp334_exp285_isoform_residue_mask.yaml) and the same
PathwayMutationTypeFoldBuilder fold-safe pathway augmentation, so the
feature set is identical to EXP-334 -- only the model changes.

train_domain_propensity.csv (adversarial validation OOF, #292) is used
read-only as a diagnostic subset selector (top-quartile "test-like" rows),
never as training input or a feature-selection criterion -- the same
boundary EXP-351's finalization used.

Usage: uv run python scripts/diagnose_elasticnet_shift_robustness.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import sparse
from sklearn.metrics import f1_score, log_loss
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.constants import CLASS_LABELS
from open_cancer.feature_family import drop_named_base_features
from open_cancer.hotspot_features import (
    build_hotspot_augmented_features,
    resolve_hotspot_config,
)
from open_cancer.isoform_position_mask import resolve_isoform_position_mask_from_config
from open_cancer.isoform_relative_position import (
    resolve_isoform_relative_position_from_config,
)
from open_cancer.model_runner import LogisticRegressionAdapter
from open_cancer.mutation_features import (
    resolve_position_features_from_config,
    resolve_position_options_from_config,
)
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder

ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
CONFIG_PATH = ROOT / "configs" / "exp334_exp285_isoform_residue_mask.yaml"
SPLIT_PATH = ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"
BASELINE_OOF_PATH = ROOT / "oof" / "exp334_exp285_isoform_residue_mask.csv"
BASELINE_METRICS_PATH = ROOT / "reports" / "exp334_exp285_isoform_residue_mask" / "metrics.json"
PROPENSITY_PATH = ROOT / "reports" / "analysis" / "adversarial_validation" / "train_domain_propensity.csv"
FEATURE_DIR = ROOT / "data" / "processed" / "diagnostic_elasticnet_exp334_features"
OUT_DIR = ROOT / "reports" / "analysis" / "elasticnet_shift_robustness_diagnostic"

C_CANDIDATES = (0.01, 1.0)
L1_RATIO = 0.5
SOLVER_TOL = 1e-3


def build_base_features(config: dict) -> tuple[sparse.csr_matrix, sparse.csr_matrix, tuple[str, ...]]:
    hotspot_config = config.get("hotspots", {})
    hotspots, _evidence_hotspots, _minimum_matching_rows = resolve_hotspot_config(hotspot_config)
    selected_position_features = resolve_position_features_from_config(config)
    position_options = resolve_position_options_from_config(config)
    position_token_filter, mask_semantic_contract = resolve_isoform_position_mask_from_config(
        config, root=ROOT
    )
    position_token_transformer, relative_semantic_contract = (
        resolve_isoform_relative_position_from_config(config, root=ROOT)
    )
    position_semantic_contract = relative_semantic_contract or mask_semantic_contract
    selected_robust_aggregates = tuple(config.get("features", {}).get("robust_aggregates", []))
    build_hotspot_augmented_features(
        TRAIN_PATH,
        TEST_PATH,
        FEATURE_DIR,
        hotspots=hotspots,
        base_feature_options={
            "selected_robust_aggregates": selected_robust_aggregates,
            "selected_position_features": selected_position_features,
            "position_token_filter": position_token_filter,
            "position_token_transformer": position_token_transformer,
            "position_semantic_contract": position_semantic_contract,
            **position_options,
        },
    )
    x_train = sparse.load_npz(FEATURE_DIR / "train_features.npz")
    x_test = sparse.load_npz(FEATURE_DIR / "test_features.npz")
    feature_names = tuple(
        json.loads((FEATURE_DIR / "feature_names.json").read_text(encoding="utf-8"))
    )
    return x_train, x_test, feature_names


def main() -> None:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    x_all, x_test, all_feature_names = build_base_features(config)

    train_meta = pd.read_csv(TRAIN_PATH, usecols=["ID", "SUBCLASS"], dtype=str)
    split = pd.read_csv(SPLIT_PATH, dtype={"ID": str, "fold": int})
    train = train_meta.merge(split, on="ID", how="left", validate="one_to_one", sort=False)
    if train["fold"].isna().any():
        raise ValueError("공용 split에 없는 train ID가 있습니다.")
    label_encoder = LabelEncoder().fit(list(CLASS_LABELS))
    y = label_encoder.transform(train["SUBCLASS"]).astype(np.int32)
    n_splits = config["split"]["n_splits"]
    seed = config["seed"]

    propensity = pd.read_csv(PROPENSITY_PATH).set_index("ID")
    propensity_aligned = propensity.loc[train["ID"]]
    test_like_threshold = float(propensity["oof_test_domain_probability"].quantile(0.75))
    test_like_mask = (
        propensity_aligned["oof_test_domain_probability"] >= test_like_threshold
    ).to_numpy()

    baseline_metrics = json.loads(BASELINE_METRICS_PATH.read_text(encoding="utf-8"))
    baseline_oof_frame = pd.read_csv(BASELINE_OOF_PATH).set_index("ID").loc[train["ID"]]
    baseline_proba_columns = [f"PROBA_{label}" for label in CLASS_LABELS]
    baseline_pred = baseline_oof_frame[baseline_proba_columns].to_numpy().argmax(axis=1)
    baseline_test_like_f1 = float(
        f1_score(y[test_like_mask], baseline_pred[test_like_mask], average="macro")
    )

    fold_builder = PathwayMutationTypeFoldBuilder(
        membership_path=OUT_DIR / "pathway_membership.json"
    )

    oof_proba = {
        c: np.full((len(train), len(CLASS_LABELS)), np.nan, dtype=np.float64) for c in C_CANDIDATES
    }
    fold_macro_f1 = {c: [] for c in C_CANDIDATES}

    for fold in range(n_splits):
        valid_mask = train["fold"].eq(fold).to_numpy()
        train_indices = np.flatnonzero(~valid_mask)
        valid_indices = np.flatnonzero(valid_mask)
        y_train, y_valid = y[train_indices], y[valid_indices]
        x_train_base = x_all[train_indices]
        x_valid_base = x_all[valid_indices]

        extra = fold_builder(
            fold=fold,
            train_indices=train_indices,
            valid_indices=valid_indices,
            base_train=x_train_base,
            base_validation=x_valid_base,
            base_test=x_test,
            base_feature_names=all_feature_names,
            target=y_train,
        )
        x_train_dropped, x_valid_dropped, _, _ = drop_named_base_features(
            x_train_base, x_valid_base, x_test, all_feature_names, extra.base_feature_names_to_drop
        )
        x_train_fold = sparse.hstack([x_train_dropped, extra.train], format="csr", dtype=np.float32)
        x_valid_fold = sparse.hstack(
            [x_valid_dropped, extra.validation], format="csr", dtype=np.float32
        )
        sample_weight = compute_sample_weight(class_weight="balanced", y=y_train)

        for c in C_CANDIDATES:
            adapter = LogisticRegressionAdapter(
                {
                    "penalty": "elasticnet",
                    "l1_ratio": L1_RATIO,
                    "C": c,
                    "scale": "max_abs",
                    "max_iter": 3000,
                    "tol": SOLVER_TOL,
                },
                seed=seed + fold,
            )
            adapter.fit(x_train_fold, y_train, x_valid_fold, y_valid, sample_weight)
            valid_proba = adapter.predict_proba(x_valid_fold)
            oof_proba[c][valid_indices] = valid_proba
            f1 = float(f1_score(y_valid, valid_proba.argmax(axis=1), average="macro"))
            fold_macro_f1[c].append(f1)
            print(f"fold={fold} C={c} macro_f1={f1:.6f}")

    results = {}
    for c in C_CANDIDATES:
        proba = oof_proba[c]
        if np.isnan(proba).any():
            raise ValueError(f"C={c} OOF 확률에 채워지지 않은 값이 있습니다.")
        pred = proba.argmax(axis=1)
        overall_f1 = float(f1_score(y, pred, average="macro"))
        per_class_f1 = {
            label: float(v)
            for label, v in zip(
                CLASS_LABELS,
                f1_score(y, pred, average=None, labels=np.arange(len(CLASS_LABELS)), zero_division=0),
                strict=True,
            )
        }
        test_like_f1 = float(f1_score(y[test_like_mask], pred[test_like_mask], average="macro"))
        results[c] = {
            "oof_macro_f1": overall_f1,
            "oof_macro_f1_delta_vs_exp334_xgboost": overall_f1 - baseline_metrics["oof"]["macro_f1"],
            "fold_macro_f1": fold_macro_f1[c],
            "fold_std": float(np.std(fold_macro_f1[c])),
            "log_loss": float(log_loss(y, proba, labels=np.arange(len(CLASS_LABELS)))),
            "per_class_f1": per_class_f1,
            "test_like_subset": {
                "n_test_like": int(test_like_mask.sum()),
                "macro_f1_test_like": test_like_f1,
                "macro_f1_test_like_delta_vs_exp334_xgboost": test_like_f1 - baseline_test_like_f1,
            },
        }
        oof_frame = pd.DataFrame({"ID": train["ID"]})
        oof_frame.loc[:, list(CLASS_LABELS)] = proba
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        oof_frame.to_csv(OUT_DIR / f"oof_elasticnet_C{c}.csv", index=False, lineterminator="\n")

    report = {
        "purpose": "diagnostic_only",
        "record_role": "diagnostic",
        "note": "official EXP 아님 -- EXPERIMENT_HISTORY 미등록, 공식 아티팩트 아님",
        "model": "sklearn.LogisticRegression(penalty=elasticnet, solver=saga, multinomial)",
        "l1_ratio": L1_RATIO,
        "c_candidates": list(C_CANDIDATES),
        "feature_set": (
            "EXP-334 그대로: base_mutation_type + hotspot_34 + fixed_pathway_burden "
            "+ pathway_mutation_type_composition (fold-safe, PathwayMutationTypeFoldBuilder)"
        ),
        "fold_safe": True,
        "test_or_public_used_for_selection": False,
        "baseline": {
            "experiment_id": "EXP-334",
            "model": "xgboost",
            "oof_macro_f1": baseline_metrics["oof"]["macro_f1"],
            "test_like_macro_f1": baseline_test_like_f1,
            "test_like_threshold_quantile": 0.75,
            "test_like_threshold_value": test_like_threshold,
        },
        "candidates": results,
    }
    report_path = OUT_DIR / "diagnostic_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nsaved: {report_path}")
    best_c = max(results, key=lambda c: results[c]["oof_macro_f1"])
    print(f"best C by OOF macro F1: {best_c} ({results[best_c]['oof_macro_f1']:.6f})")


if __name__ == "__main__":
    main()
