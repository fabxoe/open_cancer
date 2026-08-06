from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_exp545_identity_and_single_change_contract() -> None:
    config = yaml.safe_load(
        (ROOT / "configs/exp545_hierarchical_tfidf_linear.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert config["experiment_id"] == "EXP-545"
    assert config["issue_number"] == 545
    assert config["parent_experiment"] == "EXP-541"
    assert config["split"] == {
        "path": "data/splits/stratified_5fold_seed42.csv",
        "n_splits": 5,
    }
    assert config["features"]["adapter"] == "hierarchical_event_adapter_v1"
    assert config["features"]["normalization"] == "raw"
    assert config["features"]["tfidf"] == {
        "norm": "l2",
        "use_idf": True,
        "smooth_idf": True,
        "sublinear_tf": False,
    }
    assert config["model"]["class"] == "sklearn.svm.LinearSVC"
    assert config["training"]["primary_metric"] == "macro_f1"

