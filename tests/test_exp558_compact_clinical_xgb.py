from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_exp558_identity_and_fold_safe_contract() -> None:
    config = yaml.safe_load(
        (ROOT / "configs" / "exp558_compact_clinical_xgb.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert config["experiment_id"] == "EXP-558"
    assert config["issue_number"] == 558
    compact = config["compact_clinical_features"]
    assert compact["semantic_authority"] == "parser_v4"
    assert compact["fit_scope"] == "fold_train"
    assert compact["recurrent_support_unit"] == "unique_patient"
    assert compact["test_distribution_used_for_fit"] is False
    assert config["training"]["checkpoint_selection"] == "macro_f1_validation"


def test_exp558_runner_drops_common_base_features() -> None:
    source = (
        ROOT / "scripts" / "run_exp558_compact_clinical_xgb.py"
    ).read_text(encoding="utf-8")
    assert "base_feature_names_to_drop=tuple(base_feature_names)" in source
    assert "self.family.fit(self.train.iloc[train_indices])" in source
    assert "fitted.transform(self.test)" in source
