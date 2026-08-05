#!/usr/bin/env python
"""Audit N4 L/C/N prediction deltas and native feature support."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.parser_native_features import ParserNativeSemanticFamily


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "analysis" / "parser_v4_n4_comparison"
EXPERIMENTS = {
    "legacy": (433, "parser_v4_legacy_control"),
    "compatibility": (435, "parser_v4_compatibility_control"),
    "native": (438, "parser_v4_native_semantic_baseline"),
}


def _paths(experiment: int, slug: str) -> tuple[Path, Path, Path]:
    stem = f"exp{experiment}_{slug}"
    return (
        ROOT / "reports" / stem / "metrics.json",
        ROOT / "oof" / f"{stem}.csv",
        ROOT / "preds" / f"{stem}_test_proba.csv",
    )


def _probabilities(frame: pd.DataFrame) -> np.ndarray:
    return frame.filter(regex=r"^PROBA_").to_numpy(dtype=np.float64)


def main() -> None:
    metrics: dict[str, dict] = {}
    oof: dict[str, pd.DataFrame] = {}
    test: dict[str, pd.DataFrame] = {}
    for name, (number, slug) in EXPERIMENTS.items():
        metrics_path, oof_path, test_path = _paths(number, slug)
        metrics[name] = json.loads(metrics_path.read_text(encoding="utf-8"))
        oof[name] = pd.read_csv(oof_path)
        test[name] = pd.read_csv(test_path)
    reference_ids = oof["legacy"]["ID"]
    if any(not frame["ID"].equals(reference_ids) for frame in oof.values()):
        raise ValueError("OOF ID 순서가 다릅니다.")
    test_ids = test["legacy"]["ID"]
    if any(not frame["ID"].equals(test_ids) for frame in test.values()):
        raise ValueError("test probability ID 순서가 다릅니다.")

    pairs: dict[str, dict] = {}
    for left, right in (("legacy", "compatibility"), ("compatibility", "native"), ("legacy", "native")):
        left_oof, right_oof = _probabilities(oof[left]), _probabilities(oof[right])
        left_test, right_test = _probabilities(test[left]), _probabilities(test[right])
        left_error = oof[left]["SUBCLASS_PRED"].ne(oof[left]["SUBCLASS_TRUE"]).astype(float)
        right_error = oof[right]["SUBCLASS_PRED"].ne(oof[right]["SUBCLASS_TRUE"]).astype(float)
        pairs[f"{right}_minus_{left}"] = {
            "oof_macro_f1_delta": metrics[right]["oof"]["macro_f1"] - metrics[left]["oof"]["macro_f1"],
            "fold_std_delta": metrics[right]["oof"]["fold_std"] - metrics[left]["oof"]["fold_std"],
            "log_loss_delta": metrics[right]["oof"]["log_loss"] - metrics[left]["oof"]["log_loss"],
            "oof_argmax_changed_rows": int(oof[left]["SUBCLASS_PRED"].ne(oof[right]["SUBCLASS_PRED"]).sum()),
            "test_argmax_changed_rows": int(
                np.count_nonzero(np.argmax(left_test, axis=1) != np.argmax(right_test, axis=1))
            ),
            "oof_probability_mean_abs_delta": float(np.mean(np.abs(right_oof - left_oof))),
            "oof_probability_max_abs_delta": float(np.max(np.abs(right_oof - left_oof))),
            "test_probability_mean_abs_delta": float(np.mean(np.abs(right_test - left_test))),
            "test_probability_max_abs_delta": float(np.max(np.abs(right_test - left_test))),
            "oof_error_correlation": float(np.corrcoef(left_error, right_error)[0, 1]),
            "per_class_f1_delta": {
                label: metrics[right]["oof"]["per_class_f1"][label] - value
                for label, value in metrics[left]["oof"]["per_class_f1"].items()
            },
        }

    train = pd.read_csv(ROOT / "data/raw/train.csv", dtype=str, keep_default_na=False)
    raw_test = pd.read_csv(ROOT / "data/raw/test.csv", dtype=str, keep_default_na=False)
    genes = tuple(train.columns[2:])
    fitted = ParserNativeSemanticFamily(genes).fit(train)
    train_matrix = sparse.csr_matrix(fitted.transform(train))
    test_matrix = sparse.csr_matrix(fitted.transform(raw_test))
    names = fitted.descriptor.feature_names
    support: dict[str, dict] = {}
    for index, name in enumerate(names[:12]):
        train_column = train_matrix[:, index]
        test_column = test_matrix[:, index]
        support[name] = {
            "train_nonzero_rows": int(train_column.getnnz()),
            "test_nonzero_rows": int(test_column.getnnz()),
            "train_prevalence": float(train_column.getnnz() / train_matrix.shape[0]),
            "test_prevalence": float(test_column.getnnz() / test_matrix.shape[0]),
            "train_mean": float(train_column.mean()),
            "test_mean": float(test_column.mean()),
        }
    consequence_support: dict[str, dict] = {}
    for consequence in (
        "missense", "no_change", "nonsense", "frameshift",
        "range_replacement", "non_simple_or_unresolved",
    ):
        indices = [i for i, name in enumerate(names) if name.endswith(f"__native_{consequence}_any")]
        train_block = train_matrix[:, indices]
        test_block = test_matrix[:, indices]
        consequence_support[consequence] = {
            "dimension": len(indices),
            "train_nnz": int(train_block.nnz),
            "test_nnz": int(test_block.nnz),
            "train_rows_any": int(np.count_nonzero(np.asarray(train_block.sum(axis=1)).ravel())),
            "test_rows_any": int(np.count_nonzero(np.asarray(test_block.sum(axis=1)).ravel())),
            "train_active_gene_columns": int(np.count_nonzero(np.asarray(train_block.getnnz(axis=0)))),
            "test_active_gene_columns": int(np.count_nonzero(np.asarray(test_block.getnnz(axis=0)))),
        }

    result = {
        "experiments": {
            name: {
                "experiment_id": metrics[name]["experiment_id"],
                "oof_macro_f1": metrics[name]["oof"]["macro_f1"],
                "fold_std": metrics[name]["oof"]["fold_std"],
                "accuracy": metrics[name]["oof"]["accuracy"],
                "log_loss": metrics[name]["oof"]["log_loss"],
            }
            for name in EXPERIMENTS
        },
        "pairwise": pairs,
        "native_sample_feature_support": support,
        "native_gene_consequence_support": consequence_support,
        "decision": {
            "parser_correctness": "retain_v4",
            "native_adapter_v1": "revise",
            "next_experiment": "compatibility_five_family_plus_non_equivalent_native_semantics",
            "selection_used_test_or_public": False,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "audit.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
