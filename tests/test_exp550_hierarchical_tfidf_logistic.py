from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_exp550_identity_and_probability_model_contract() -> None:
    config = yaml.safe_load(
        (ROOT / "configs/exp550_hierarchical_tfidf_logistic.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert config["experiment_id"] == "EXP-550"
    assert config["issue_number"] == 550
    assert config["parent_experiment"] == "EXP-545"
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
    assert config["model"]["class"] == "sklearn.linear_model.LogisticRegression"
    assert config["model"]["solver"] == "lbfgs"
    assert config["training"]["checkpoint_selection"] == "fitted_probability_model"
    assert config["training"]["primary_metric"] == "macro_f1"
