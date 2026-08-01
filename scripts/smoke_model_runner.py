#!/usr/bin/env python
"""Run a score-free synthetic smoke test of the common model runner."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
from scipy import sparse

from open_cancer.constants import CLASS_LABELS
from open_cancer.model_runner import create_model_adapter, run_canonical_cv


def main() -> None:
    rows = len(CLASS_LABELS) * 5
    targets = np.tile(np.arange(len(CLASS_LABELS)), 5)
    folds = np.repeat(np.arange(5), len(CLASS_LABELS))
    features = sparse.csr_matrix(np.eye(rows, 32, dtype=np.float32))
    test = features[:13]
    with tempfile.TemporaryDirectory(prefix="open-cancer-model-smoke-") as directory:
        output = run_canonical_cv(
            train_features=features,
            test_features=test,
            targets=targets,
            folds=folds,
            adapter_factory=lambda fold: create_model_adapter(
                "logistic_regression",
                {"solver": "lbfgs", "max_iter": 50},
                42 + fold,
            ),
            model_dir=Path(directory),
        )
    print(
        json.dumps(
            {
                "status": "SMOKE_PASSED",
                "score_computed_on_competition_data": False,
                "oof_shape": list(output.oof_probabilities.shape),
                "test_shape": list(output.test_probabilities.shape),
                "fold_count": len(output.fold_metrics),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
