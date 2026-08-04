from __future__ import annotations

import json

import pytest

from open_cancer.frozen_fold_parameters import FrozenFoldParameterSelector
from open_cancer.hashing import sha256_file


def _source(tmp_path):
    source = tmp_path / "optuna_outer_00.json"
    source.write_text(
        json.dumps(
            {
                "outer_fold": 0,
                "study_name": "parent_outer_00",
                "sampler_seed": 42,
                "inner_n_splits": 3,
                "requested_trials": 30,
                "completed_trials": 30,
                "best_trial": 4,
                "best_value": 0.4,
                "best_parameters": {"max_depth": 6, "learning_rate": 0.05},
                "database_path": "models/parent/outer_00.sqlite3",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return source


def test_frozen_fold_parameters_are_hash_verified_and_reused(tmp_path) -> None:
    source = _source(tmp_path)
    selector = FrozenFoldParameterSelector(
        root=tmp_path,
        source_experiment="EXP-285",
        fold_records=[
            {
                "fold": 0,
                "source_path": source.name,
                "source_sha256": sha256_file(source),
                "parameters": {"max_depth": 6, "learning_rate": 0.05},
            }
        ],
    )
    result = selector(
        fold=0,
        features=None,
        target=None,
        base_model_parameters={},
    )
    assert result.parameters == {"max_depth": 6, "learning_rate": 0.05}
    assert result.record["parameter_source_experiment"] == "EXP-285"
    assert result.record["retuned_for_current_features"] is False
    assert result.record["test_or_outer_validation_used_for_selection"] is False


def test_frozen_fold_parameters_reject_source_hash_mismatch(tmp_path) -> None:
    source = _source(tmp_path)
    selector = FrozenFoldParameterSelector(
        root=tmp_path,
        source_experiment="EXP-285",
        fold_records=[
            {
                "fold": 0,
                "source_path": source.name,
                "source_sha256": "0" * 64,
                "parameters": {"max_depth": 6, "learning_rate": 0.05},
            }
        ],
    )
    with pytest.raises(ValueError, match="source hash mismatch"):
        selector(fold=0, features=None, target=None, base_model_parameters={})
