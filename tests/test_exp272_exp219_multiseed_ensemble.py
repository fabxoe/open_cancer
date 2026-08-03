from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import yaml

from open_cancer.constants import PROBABILITY_COLUMNS


def load_runner(root: Path):
    path = root / "scripts/run_exp272_exp219_multiseed_ensemble.py"
    sys.path.insert(0, str(root / "scripts"))
    spec = importlib.util.spec_from_file_location("run_exp272", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_exp272_identity_and_prefixed_multiseed_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load(
        (root / "configs/exp272_exp219_multiseed_ensemble.yaml").read_text(
            encoding="utf-8"
        )
    )
    runner = (root / "scripts/run_exp272_exp219_multiseed_ensemble.py").read_text(
        encoding="utf-8"
    )

    assert config["experiment_id"] == "EXP-272"
    assert config["issue_number"] == 272
    assert config["parent_experiment"] == "EXP-219"
    assert config["split"] == {
        "path": "data/splits/stratified_5fold_seed42.csv",
        "n_splits": 5,
    }
    assert config["multiseed"]["seeds"] == [42, 142, 242, 342, 442]
    assert config["multiseed"]["weights"] == [0.2] * 5
    assert config["multiseed"]["weights_fixed_before_evaluation"] is True
    assert config["multiseed"]["seed_selection_after_evaluation"] is False
    assert config["training"]["checkpoint_selection"] == "macro_f1_validation"
    assert "EXPECTED_SEEDS = (42, 142, 242, 342, 442)" in runner
    assert "EXPECTED_WEIGHTS = (0.2, 0.2, 0.2, 0.2, 0.2)" in runner


def test_exp272_seed_paths_do_not_collide() -> None:
    root = Path(__file__).resolve().parents[1]
    runner = load_runner(root)

    paths = [runner.seed_paths(seed) for seed in runner.EXPECTED_SEEDS]
    for key in ("metrics", "manifest", "resolved_config", "oof", "test_probability", "models"):
        values = [item[key] for item in paths]
        assert len(values) == len(set(values))
    assert all("seeds/seed_" in item["oof"].as_posix() for item in paths)


def test_exp272_probability_normalization_is_deterministic() -> None:
    root = Path(__file__).resolve().parents[1]
    runner = load_runner(root)
    frame = pd.DataFrame({"ID": ["A", "B"]})
    values = np.zeros((2, len(PROBABILITY_COLUMNS)), dtype=float)
    values[0, 0] = 2.0
    values[0, 1] = 1.0
    values[1, 2] = 4.0
    frame.loc[:, list(PROBABILITY_COLUMNS)] = values

    normalized = runner.normalized_probabilities(frame)

    np.testing.assert_allclose(normalized.sum(axis=1), 1.0)
    np.testing.assert_allclose(normalized[0, :2], [2.0 / 3.0, 1.0 / 3.0])
    assert normalized[1, 2] == 1.0
