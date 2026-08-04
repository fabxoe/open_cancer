from __future__ import annotations

from pathlib import Path

import yaml


def test_exp302_keeps_exp229_training_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    parent = yaml.safe_load(
        (root / "configs/exp229_pathway_mutation_types.yaml").read_text(encoding="utf-8")
    )
    candidate = yaml.safe_load(
        (root / "configs/exp302_observable_marker_proxies.yaml").read_text(
            encoding="utf-8"
        )
    )
    for key in ("seed", "split", "features", "hotspots", "external_knowledge", "model"):
        assert candidate[key] == parent[key]
    assert candidate["training"]["balanced_sample_weight"] is True
    assert candidate["training"]["checkpoint_selection"] == "macro_f1_validation"
    assert candidate["parent_experiment"] == "EXP-229"
    marker = candidate["marker_external_knowledge"]
    assert marker["candidate_output_dimension"] == 20
    assert marker["fit_scope"] == "stateless"
    assert marker["interpretation"] == "mutation_proxy_not_clinical_biomarker"


def test_exp302_uses_issue_derived_identity_and_runner() -> None:
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load(
        (root / "configs/exp302_observable_marker_proxies.yaml").read_text(
            encoding="utf-8"
        )
    )
    runner = (root / "scripts" / "run_exp302_observable_marker_proxies.py").read_text(
        encoding="utf-8"
    )
    assert config["experiment_id"] == "EXP-302"
    assert config["issue_number"] == 302
    assert "exp302_observable_marker_proxies.yaml" in runner
    assert "EXP-302" in runner
