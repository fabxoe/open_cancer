#!/usr/bin/env python
"""RUN_MODE=explore: out-of-fold TreeSHAP diagnostic for EXP-052 co-mutation features.

Used to decide EXP-058 (#58 / PR #76): instead of gating co-mutation
features by cancer type (which would require the unknown test SUBCLASS --
target leakage, rejected before implementation), this checks whether
XGBoost already learned a class-specific association for each curated pair
on its own, by inspecting exact TreeSHAP contributions
(`xgboost.Booster.predict(pred_contribs=True)`) restricted to the samples
where each pair fires.

OOF-SAFETY (reviewer question on PR #76, answered here in code, not just
prose): for every sample, contributions come ONLY from the checkpoint of
the fold that did NOT train on it -- i.e. `models/<slug>/fold_XX.json` is
applied only to `fold_map == XX` rows, exactly mirroring how EXP-052's own
OOF predictions were assembled. No sample is ever scored by a model that
saw it during training, so this is genuine out-of-fold SHAP, not an
average across all 5 checkpoints (which would leak in-sample information
for 4 of the 5 folds).

This is a selection diagnostic, not an independent validation of EXP-058:
the same canonical OOF that motivated dropping APC/CTNNB1 here is also the
OOF EXP-058 was scored against, so the resulting improvement should be
read as "consistent with this diagnosis," not as proof the diagnosis was
correct (see reports/exp058_cooccurrence_pair_ablation/README.md).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
from scipy import sparse

from open_cancer.constants import CLASS_LABELS

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_SLUG = "exp052_hotspot_cooccurrence"
FEATURE_DIR = ROOT / "data" / "processed" / "feature_factory" / "v1" / ARTIFACT_SLUG
MODEL_DIR = ROOT / "models" / ARTIFACT_SLUG
SPLIT_PATH = ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"
OUTPUT_JSON_PATH = ROOT / "reports" / ARTIFACT_SLUG / "cooccurrence_shap_diagnostic.json"
OUTPUT_CSV_PATH = ROOT / "reports" / ARTIFACT_SLUG / "cooccurrence_shap_diagnostic.csv"
N_SPLITS = 5

# Biologically-expected class(es) per curated co-mutation pair, used only to
# report a rank/gap -- not used to select or filter samples.
EXPECTED_CLASSES: dict[str, list[str]] = {
    "sample__comut_IDH1_IDH2": ["LGG", "GBMLGG"],
    "sample__comut_APC_CTNNB1": ["COAD"],
    "sample__comut_PIK3CA_PTEN": ["UCEC"],
}


def main() -> None:
    names = json.loads((FEATURE_DIR / "feature_names.json").read_text(encoding="utf-8"))
    x_all = sparse.load_npz(FEATURE_DIR / "train_features.npz").tocsr()
    train_ids = pd.read_csv(FEATURE_DIR / "train_ids.csv", dtype=str)["ID"]
    folds = pd.read_csv(SPLIT_PATH, dtype={"ID": str, "fold": int})
    fold_map = folds.set_index("ID").loc[train_ids, "fold"].to_numpy()

    co_features = list(EXPECTED_CLASSES.keys())
    co_indices = [names.index(name) for name in co_features]
    n_features = len(names)
    n_classes = len(CLASS_LABELS)
    class_index = {label: index for index, label in enumerate(CLASS_LABELS)}

    co_matrix = x_all[:, co_indices].toarray()
    active_mask = co_matrix.sum(axis=1) > 0

    # feature_name -> list of per-sample 26-class contribution vectors,
    # collected only from that sample's own out-of-fold checkpoint.
    contributions: dict[str, list[np.ndarray]] = {name: [] for name in co_features}

    for fold in range(N_SPLITS):
        # OOF-SAFETY: this fold's checkpoint is applied ONLY to this fold's
        # own validation rows (fold_map == fold), never to rows it trained on.
        fold_active = np.flatnonzero((fold_map == fold) & active_mask)
        if len(fold_active) == 0:
            continue
        booster = xgb.Booster()
        booster.load_model(str(MODEL_DIR / f"fold_{fold:02d}.json"))
        dmatrix = xgb.DMatrix(x_all[fold_active])
        raw_contribs = np.asarray(booster.predict(dmatrix, pred_contribs=True))
        raw_contribs = raw_contribs.reshape(len(fold_active), n_classes, n_features + 1)
        for row_position, sample_index in enumerate(fold_active):
            for feature_position, feature_name in enumerate(co_features):
                if co_matrix[sample_index, feature_position] <= 0:
                    continue
                contributions[feature_name].append(
                    raw_contribs[row_position, :, co_indices[feature_position]]
                )

    report: dict[str, Any] = {
        "artifact_slug": ARTIFACT_SLUG,
        "method": "xgboost.Booster.predict(pred_contribs=True) (exact TreeSHAP)",
        "oof_safety": (
            "each sample scored only by the checkpoint of the fold that did "
            "not train on it, matching EXP-052's own OOF assembly"
        ),
        "features": {},
    }
    csv_rows: list[dict[str, Any]] = []

    for feature_name, expected in EXPECTED_CLASSES.items():
        vectors = contributions[feature_name]
        entry: dict[str, Any] = {
            "expected_classes": expected,
            "active_sample_count": len(vectors),
        }
        if vectors:
            matrix = np.array(vectors)
            mean_by_class = matrix.mean(axis=0)
            expected_positions = [class_index[label] for label in expected]
            other_positions = [i for i in range(n_classes) if i not in expected_positions]
            order = np.argsort(mean_by_class)[::-1]
            rank_by_class = {CLASS_LABELS[position]: int(list(order).index(position)) + 1 for position in expected_positions}
            entry.update(
                {
                    "expected_mean_contribution": float(mean_by_class[expected_positions].mean()),
                    "other_classes_mean_contribution": float(mean_by_class[other_positions].mean()),
                    "other_classes_std_contribution": float(mean_by_class[other_positions].std()),
                    "expected_class_rank_1_is_highest": rank_by_class,
                    "top5_classes": [
                        {"class": CLASS_LABELS[position], "mean_contribution": float(mean_by_class[position])}
                        for position in order[:5]
                    ],
                }
            )
            for position, label in enumerate(CLASS_LABELS):
                csv_rows.append(
                    {
                        "feature": feature_name,
                        "class": label,
                        "mean_contribution": float(mean_by_class[position]),
                        "is_expected_class": label in expected,
                    }
                )
        report["features"][feature_name] = entry

    OUTPUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pd.DataFrame(csv_rows).to_csv(OUTPUT_CSV_PATH, index=False, lineterminator="\n")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nwritten: {OUTPUT_JSON_PATH}")
    print(f"written: {OUTPUT_CSV_PATH}")


if __name__ == "__main__":
    main()
