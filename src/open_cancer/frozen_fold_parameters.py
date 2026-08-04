"""Reuse an immutable parent experiment's fold-specific model parameters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from open_cancer.hashing import sha256_file
from open_cancer.nested_optuna import FoldTuningResult


class FrozenFoldParameterSelector:
    """Return predeclared fold parameters without inspecting current fold data."""

    def __init__(
        self,
        *,
        root: Path,
        source_experiment: str,
        fold_records: list[dict[str, Any]],
    ) -> None:
        self.root = root
        self.source_experiment = source_experiment
        self._records = {int(record["fold"]): record for record in fold_records}
        if len(self._records) != len(fold_records):
            raise ValueError("frozen fold parameter records contain duplicate folds")

    def __call__(
        self,
        *,
        fold: int,
        features: Any,
        target: Any,
        base_model_parameters: dict[str, Any],
    ) -> FoldTuningResult:
        del features, target, base_model_parameters
        if fold not in self._records:
            raise ValueError(f"missing frozen parameters for outer fold {fold}")
        declared = self._records[fold]
        source_path = self.root / declared["source_path"]
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        actual_sha256 = sha256_file(source_path)
        if actual_sha256 != declared["source_sha256"]:
            raise ValueError(
                f"frozen parameter source hash mismatch for fold {fold}: "
                f"expected {declared['source_sha256']}, got {actual_sha256}"
            )
        source = json.loads(source_path.read_text(encoding="utf-8"))
        if int(source["outer_fold"]) != fold:
            raise ValueError(
                f"frozen parameter source outer fold mismatch: "
                f"expected {fold}, got {source['outer_fold']}"
            )
        parameters = dict(source["best_parameters"])
        if parameters != declared["parameters"]:
            raise ValueError(f"declared parameters differ from source for fold {fold}")

        record = {
            "outer_fold": fold,
            "fit_scope": "frozen_parent_outer_fold_parameters",
            "test_or_outer_validation_used_for_selection": False,
            "study_name": source["study_name"],
            "sampler": "frozen_from_parent_optuna",
            "sampler_seed": source["sampler_seed"],
            "inner_n_splits": source["inner_n_splits"],
            "requested_trials": source["requested_trials"],
            "completed_trials": source["completed_trials"],
            "best_trial": source["best_trial"],
            "best_value": source["best_value"],
            "best_parameters": parameters,
            "database_path": source["database_path"],
            "parameter_source_experiment": self.source_experiment,
            "parameter_source_path": declared["source_path"],
            "parameter_source_sha256": actual_sha256,
            "retuned_for_current_features": False,
        }
        return FoldTuningResult(
            parameters=parameters,
            record=record,
            artifact_paths=(source_path,),
        )
