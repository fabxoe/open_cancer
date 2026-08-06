#!/usr/bin/env python
"""Train-only notation-shift subgroup audit for EXP-640.

Subgroup boundaries are fitted on each outer-training partition and applied to
that fold's validation rows.  Test predictions and Public scores are not read.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, log_loss

from exp527_lightgbm_ablation_builders import build_parser_plus_cosine_features
from exp640_hierarchical_event_builders import EVENT_FAMILIES, summarize_hierarchical_events
from open_cancer.constants import CLASS_LABELS


ROOT = Path(__file__).resolve().parents[1]
ARMS = ("base", "event_family", "parser_qc", "combined")
OUTPUT_PATH = ROOT / "reports/exp640_hierarchical_event_stress/notation_shift_audit.json"


def fitted_subgroup_masks(
    train_event: np.ndarray,
    valid_event: np.ndarray,
    train_qc: np.ndarray,
    valid_qc: np.ndarray,
) -> tuple[dict[str, np.ndarray], dict[str, object]]:
    """Fit target-free subgroup definitions on outer-train and transform valid."""

    family_train = train_event[:, 0::3][:, : len(EVENT_FAMILIES)]
    family_valid = valid_event[:, 0::3][:, : len(EVENT_FAMILIES)]
    burden_train = family_train.sum(axis=1)
    burden_valid = family_valid.sum(axis=1)
    burden_q25, burden_q75 = np.quantile(burden_train, [0.25, 0.75])

    unresolved_q75 = float(np.quantile(train_qc[:, 2], 0.75))
    complex_q75 = float(np.quantile(train_qc[:, 7], 0.75))
    multi_q75 = float(np.quantile(train_qc[:, 9], 0.75))
    family_prevalence = (family_train > 0).mean(axis=0)
    rare_indices = np.flatnonzero(
        (family_prevalence > 0) & (family_prevalence <= 0.01)
    )
    rare_valid = (
        (family_valid[:, rare_indices] > 0).any(axis=1)
        if len(rare_indices)
        else np.zeros(len(valid_event), dtype=bool)
    )
    masks = {
        "unresolved_high": (valid_qc[:, 2] > unresolved_q75)
        & (valid_qc[:, 2] > 0),
        "complex_high": (valid_qc[:, 7] > complex_q75) & (valid_qc[:, 7] > 0),
        "multi_token_high": (valid_qc[:, 9] > multi_q75)
        & (valid_qc[:, 9] > 0),
        "nonstandard_present": valid_qc[:, 1:4].sum(axis=1) > 0,
        "burden_low": burden_valid <= burden_q25,
        "burden_high": burden_valid >= burden_q75,
        "rare_event_family_present": rare_valid,
    }
    metadata = {
        "burden_q25": float(burden_q25),
        "burden_q75": float(burden_q75),
        "unresolved_ratio_q75": unresolved_q75,
        "complex_gene_count_q75": complex_q75,
        "multi_token_ratio_q75": multi_q75,
        "rare_family_max_train_prevalence": 0.01,
        "rare_families": [EVENT_FAMILIES[index] for index in rare_indices],
    }
    return masks, metadata


def subgroup_metrics(frame: pd.DataFrame, mask: np.ndarray) -> dict[str, object]:
    subset = frame.loc[mask]
    if subset.empty:
        return {
            "support": 0,
            "coverage": 0.0,
            "macro_f1": None,
            "accuracy": None,
            "log_loss": None,
        }
    probability_columns = [f"PROBA_{label}" for label in CLASS_LABELS]
    return {
        "support": int(len(subset)),
        "coverage": float(len(subset) / len(frame)),
        "macro_f1": float(
            f1_score(
                subset["SUBCLASS_TRUE"],
                subset["SUBCLASS_PRED"],
                labels=list(CLASS_LABELS),
                average="macro",
                zero_division=0,
            )
        ),
        "accuracy": float(
            accuracy_score(subset["SUBCLASS_TRUE"], subset["SUBCLASS_PRED"])
        ),
        "log_loss": float(
            log_loss(
                subset["SUBCLASS_TRUE"],
                subset[probability_columns].to_numpy(),
                labels=list(CLASS_LABELS),
            )
        ),
    }


def main() -> None:
    parent = build_parser_plus_cosine_features()
    event_matrix, qc_matrix = summarize_hierarchical_events(
        parent.train, tuple(parent.gene_columns)
    )
    event_array = event_matrix.toarray()
    qc_array = qc_matrix.toarray()
    oof_by_arm = {
        arm: pd.read_csv(ROOT / f"oof/exp640_hierarchical_event_stress_{arm}.csv")
        for arm in ARMS
    }
    reference = oof_by_arm["base"][["ID", "FOLD"]]
    subgroup_names = (
        "unresolved_high",
        "complex_high",
        "multi_token_high",
        "nonstandard_present",
        "burden_low",
        "burden_high",
        "rare_event_family_present",
    )
    fitted_masks = {
        name: np.zeros(len(reference), dtype=bool) for name in subgroup_names
    }
    fold_metadata: list[dict[str, object]] = []
    for fold in range(5):
        valid_indices = np.flatnonzero(reference["FOLD"].to_numpy() == fold)
        train_indices = np.flatnonzero(reference["FOLD"].to_numpy() != fold)
        masks, metadata = fitted_subgroup_masks(
            event_array[train_indices],
            event_array[valid_indices],
            qc_array[train_indices],
            qc_array[valid_indices],
        )
        for name, mask in masks.items():
            fitted_masks[name][valid_indices] = mask
        fold_metadata.append({"fold": fold, **metadata})

    subgroup_results: dict[str, object] = {}
    for name, mask in fitted_masks.items():
        arm_results = {
            arm: subgroup_metrics(oof_by_arm[arm], mask) for arm in ARMS
        }
        base = arm_results["base"]
        for arm in ARMS[1:]:
            current = arm_results[arm]
            current["delta_vs_base"] = {
                metric: (
                    None
                    if current[metric] is None or base[metric] is None
                    else float(current[metric] - base[metric])
                )
                for metric in ("macro_f1", "accuracy", "log_loss")
            }
        subgroup_results[name] = {"arms": arm_results}

    payload = {
        "experiment_id": "EXP-640",
        "scope": "canonical outer-validation rows; rules fitted per outer-train",
        "test_data_used": False,
        "public_leaderboard_used": False,
        "fold_fit_metadata": fold_metadata,
        "subgroups": subgroup_results,
    }
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
