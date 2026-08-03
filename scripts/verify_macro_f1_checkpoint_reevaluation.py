#!/usr/bin/env python
"""Post-hoc macro-f1-checkpoint re-evaluation of D/E/Cell-Cycle-A/B (no retraining).

EXP-219 and EXP-223 showed that selecting each fold's checkpoint by
validation Macro F1 (instead of validation mlogloss) improves EXP-094's own
OOF by +0.0053 with zero feature changes. Every feature-ablation gate
decision in this session (EXP-170, EXP-173, EXP-181, EXP-226) was judged
under the mlogloss-checkpoint policy. This script re-scores each of their
already-saved fold checkpoints (which retain the full boosting-round
history XGBoost wrote during early stopping) using the same fold-safe
`audit_xgboost_validation_iterations` machinery EXP-219/223 used, with NO
retraining.

The correct baseline for an apples-to-apples comparison under the new
policy is EXP-219 (EXP-094 + macro-f1-checkpoint), not EXP-094's original
mlogloss-checkpoint OOF -- otherwise the checkpoint-policy effect and the
feature effect would be conflated.

RUN_MODE=explore: diagnostic only, no new EXP-ID or History row. Findings
are folded back into the existing EXP-170/173/181/226 reports.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy import sparse
from sklearn.metrics import f1_score, log_loss

from open_cancer.checkpoint_selection import audit_xgboost_validation_iterations
from open_cancer.constants import CLASS_LABELS
from open_cancer.feature_family import transform_checked
from open_cancer.frozen_feature_specs import materialize_frozen_feature_spec
from open_cancer.pathway_aggregation_features import (
    cell_cycle_any_nonsilent_family,
    cell_cycle_lof_in_tsg_family,
)
from open_cancer.pole_ed_features import (
    pole_ed_driver_extended_family,
    pole_hotspot5_family,
)

ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "data" / "raw" / "train.csv"
TEST = ROOT / "data" / "raw" / "test.csv"
SPLIT = ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"

WATCH_CLASSES = ["COAD", "UCEC", "DLBC"]

CELL_CYCLE_KNOWLEDGE = ROOT / "knowledge" / "tcga_pancanatlas_table_s3_cell_cycle_v1.json"

TARGETS: dict[str, dict[str, Any]] = {
    "EXP-170": {
        "slug": "exp170_cellcycle_any_nonsilent",
        "family_fitter": lambda: cell_cycle_any_nonsilent_family(CELL_CYCLE_KNOWLEDGE),
        "mlogloss_metrics": "reports/exp170_cellcycle_any_nonsilent/metrics.json",
    },
    "EXP-173": {
        "slug": "exp173_cellcycle_lof_tsg",
        "family_fitter": lambda: cell_cycle_lof_in_tsg_family(CELL_CYCLE_KNOWLEDGE),
        "mlogloss_metrics": "reports/exp173_cellcycle_lof_tsg/metrics.json",
    },
    "EXP-181": {
        "slug": "exp181_pole_hotspot5",
        "family_fitter": pole_hotspot5_family,
        "mlogloss_metrics": "reports/exp181_pole_hotspot5/metrics.json",
    },
    "EXP-226": {
        "slug": "exp226_pole_ed_driver_extended",
        "family_fitter": pole_ed_driver_extended_family,
        "mlogloss_metrics": "reports/exp226_pole_ed_driver_extended/metrics.json",
    },
}


def load_base_matrices() -> tuple[sparse.csr_matrix, pd.DataFrame, np.ndarray, np.ndarray]:
    feature_dir = ROOT / "data" / "processed" / "macro_f1_reeval_v1_features"
    materialize_frozen_feature_spec(
        root=ROOT, name="v1", output_dir=feature_dir, train_path=TRAIN, test_path=TEST
    )
    x_base = sparse.load_npz(feature_dir / "train_features.npz").tocsr()
    train_raw = pd.read_csv(TRAIN, dtype=str, keep_default_na=False)
    split = train_raw[["ID"]].merge(
        pd.read_csv(SPLIT, dtype={"ID": str, "fold": int}),
        on="ID",
        how="left",
        validate="one_to_one",
        sort=False,
    )
    folds = split["fold"].to_numpy(dtype=np.int32)
    label_index = {label: index for index, label in enumerate(CLASS_LABELS)}
    targets = train_raw["SUBCLASS"].map(label_index).to_numpy(dtype=np.int32)
    return x_base, train_raw, folds, targets


def reevaluate(
    experiment_id: str,
    slug: str,
    family_fitter: Callable[[], Any],
    x_base: sparse.csr_matrix,
    train_raw: pd.DataFrame,
    folds: np.ndarray,
    targets: np.ndarray,
) -> dict[str, Any]:
    fitted_family = family_fitter().fit(train_raw)
    extra = transform_checked(fitted_family, train_raw)
    x_all = sparse.hstack([x_base, extra], format="csr")

    model_dir = ROOT / "models" / slug
    oof_proba = np.full((len(targets), len(CLASS_LABELS)), np.nan, dtype=np.float64)
    fold_reports = []
    for fold in range(5):
        valid_mask = folds == fold
        x_valid = x_all[valid_mask]
        y_valid = targets[valid_mask]
        model = xgb.XGBClassifier()
        model.load_model(model_dir / f"fold_{fold:02d}.json")
        audit = audit_xgboost_validation_iterations(model, x_valid, y_valid)
        best_iteration = int(audit["macro_f1_best"]["iteration"])
        probabilities = model.predict_proba(x_valid, iteration_range=(0, best_iteration + 1))
        oof_proba[valid_mask] = probabilities
        fold_reports.append(
            {
                "fold": fold,
                "mlogloss_best_iteration": int(model.best_iteration),
                "macro_f1_best_iteration": best_iteration,
                "mlogloss_checkpoint_macro_f1": audit["training_metric_best"]["macro_f1"],
                "macro_f1_checkpoint_macro_f1": audit["macro_f1_best"]["macro_f1"],
                "delta": audit["macro_f1_delta"],
            }
        )

    assert not np.isnan(oof_proba).any()
    pred = oof_proba.argmax(axis=1)
    fold_scores = np.array([row["macro_f1_checkpoint_macro_f1"] for row in fold_reports])
    per_class_f1 = {
        label: float(value)
        for label, value in zip(
            CLASS_LABELS,
            f1_score(targets, pred, average=None, labels=np.arange(len(CLASS_LABELS)), zero_division=0),
            strict=True,
        )
    }
    return {
        "experiment_id": experiment_id,
        "slug": slug,
        "fold_reports": fold_reports,
        "oof_macro_f1": float(f1_score(targets, pred, average="macro")),
        "fold_mean": float(fold_scores.mean()),
        "fold_std": float(fold_scores.std()),
        "log_loss": float(log_loss(targets, oof_proba, labels=np.arange(len(CLASS_LABELS)))),
        "per_class_f1": {cls: per_class_f1[cls] for cls in WATCH_CLASSES},
        "per_class_f1_full": per_class_f1,
    }


def main() -> None:
    exp219 = json.loads((ROOT / "reports/exp219_macro_f1_checkpoint_selection/metrics.json").read_text(encoding="utf-8"))
    exp219_oof = exp219["oof"]

    x_base, train_raw, folds, targets = load_base_matrices()

    results = {}
    for experiment_id, spec in TARGETS.items():
        mlogloss_metrics = json.loads((ROOT / spec["mlogloss_metrics"]).read_text(encoding="utf-8"))
        reeval = reevaluate(
            experiment_id, spec["slug"], spec["family_fitter"], x_base, train_raw, folds, targets
        )
        delta_vs_exp219 = reeval["oof_macro_f1"] - exp219_oof["macro_f1"]
        delta_vs_own_mlogloss = reeval["oof_macro_f1"] - mlogloss_metrics["oof"]["macro_f1"]
        gate_vs_exp219 = {
            "macro_f1_gate_passed": delta_vs_exp219 >= 0.001,
            "fold_std_gate_passed": (reeval["fold_std"] - exp219_oof["fold_std"]) < 0.002,
            "log_loss_gate_passed": (reeval["log_loss"] - exp219_oof["log_loss"]) <= 0,
            "per_class_f1_gate_passed": min(
                reeval["per_class_f1_full"][label] - exp219_oof["per_class_f1"][label]
                for label in CLASS_LABELS
            )
            >= 0,
        }
        gate_vs_exp219["adopted"] = all(gate_vs_exp219.values())
        results[experiment_id] = {
            **reeval,
            "own_mlogloss_checkpoint_oof_macro_f1": mlogloss_metrics["oof"]["macro_f1"],
            "delta_vs_own_mlogloss_checkpoint": delta_vs_own_mlogloss,
            "exp219_macro_f1_checkpoint_baseline_oof_macro_f1": exp219_oof["macro_f1"],
            "delta_vs_exp219_macro_f1_checkpoint_baseline": delta_vs_exp219,
            "watch_class_delta_vs_exp219": {
                cls: reeval["per_class_f1"][cls] - exp219_oof["per_class_f1"][cls]
                for cls in WATCH_CLASSES
            },
            "gate_vs_exp219_macro_f1_checkpoint_baseline": gate_vs_exp219,
        }

    output_path = ROOT / "reports" / "analysis" / "pole_cellcycle_macro_f1_checkpoint_reevaluation.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: {
        "oof_macro_f1": v["oof_macro_f1"],
        "delta_vs_exp219": v["delta_vs_exp219_macro_f1_checkpoint_baseline"],
        "delta_vs_own_mlogloss": v["delta_vs_own_mlogloss_checkpoint"],
        "adopted_vs_exp219": v["gate_vs_exp219_macro_f1_checkpoint_baseline"]["adopted"],
        "watch_class_delta_vs_exp219": v["watch_class_delta_vs_exp219"],
    } for k, v in results.items()}, ensure_ascii=False, indent=2))
    print(f"\nwrote {output_path}")


if __name__ == "__main__":
    main()
