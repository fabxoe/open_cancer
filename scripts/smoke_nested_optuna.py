#!/usr/bin/env python
"""Run a tiny CPU-only nested Optuna smoke test without competition data."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
from scipy import sparse

from open_cancer.nested_optuna import NestedOptunaFoldTuner


def main() -> None:
    rng = np.random.default_rng(42)
    class_count = 26
    rows_per_class = 6
    target = np.repeat(np.arange(class_count, dtype=np.int32), rows_per_class)
    matrix = sparse.random(
        target.size,
        64,
        density=0.08,
        random_state=rng,
        format="csr",
        dtype=np.float32,
    )
    with tempfile.TemporaryDirectory(prefix="open-cancer-optuna-smoke-") as directory:
        tuner = NestedOptunaFoldTuner(
            artifact_slug="smoke_nested_optuna",
            root=Path(directory),
            n_trials=1,
            inner_n_splits=3,
            seed=42,
        )
        result = tuner(
            fold=0,
            features=matrix,
            target=target,
            base_model_parameters={
                "objective": "multi:softprob",
                "n_estimators": 12,
                "eval_metric": "mlogloss",
                "early_stopping_rounds": 3,
                "tree_method": "hist",
                "device": "cpu",
                "n_jobs": 2,
                "verbosity": 0,
            },
        )
        print(
            {
                "best_parameters": result.parameters,
                "best_value": result.record["best_value"],
                "completed_trials": result.record["completed_trials"],
            }
        )


if __name__ == "__main__":
    main()
