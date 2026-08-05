from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from scipy import sparse


def _load_module():
    root = Path(__file__).resolve().parents[1]
    scripts = root / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location(
            "run_exp005_dashboard_test",
            scripts / "run_exp005_xgb_mutation_features.py",
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


def test_dashboard_skips_missing_optional_highlight(tmp_path: Path) -> None:
    module = _load_module()
    module.ROOT = tmp_path
    feature_dir = tmp_path / "features"
    feature_dir.mkdir()
    (feature_dir / "feature_names.json").write_text(
        json.dumps(["mutation__present"]), encoding="utf-8"
    )
    sparse.save_npz(
        feature_dir / "train_features.npz",
        sparse.csr_matrix(np.asarray([[0.0], [1.0]], dtype=np.float32)),
    )
    sparse.save_npz(
        feature_dir / "test_features.npz",
        sparse.csr_matrix(np.asarray([[1.0]], dtype=np.float32)),
    )
    metrics = {
        "experiment_id": "EXP-TEST",
        "folds": [
            {"fold": 0, "macro_f1": 0.5, "accuracy": 0.5, "log_loss": 1.0}
        ],
        "oof": {
            "macro_f1": 0.5,
            "fold_mean": 0.5,
            "fold_std": 0.0,
            "accuracy": 0.5,
            "per_class_f1": {"A": 0.5},
        },
    }

    output = module.write_local_dashboard(
        artifact_slug="no_hotspot",
        metrics=metrics,
        feature_dir=feature_dir,
        highlighted_features=("hotspot__known_hotspot_total_count",),
        comparison_metrics_path=None,
    )
    assert output.is_file()
    assert "EXP-TEST" in output.read_text(encoding="utf-8")
