from __future__ import annotations

import pytest

from open_cancer.mutation_features import (
    resolve_position_features_from_config,
    resolve_position_options_from_config,
)


def test_exp047_residue_defaults_remain_backward_compatible() -> None:
    config = {
        "features": {
            "mutation_type": {"enabled": True},
            "residue_position": {"enabled": True, "aggregates": ["min"]},
        }
    }
    assert resolve_position_features_from_config(config) == ("min_residue_position",)
    assert resolve_position_options_from_config(config) == {
        "position_missing_policy": "zero",
        "position_token_scope": "include_complex",
        "position_transform": "raw",
        "position_bin_width": 100,
    }


def test_residue_extension_config_resolves_all_options() -> None:
    config = {
        "features": {
            "mutation_type": {"enabled": True},
            "residue_position": {
                "enabled": True,
                "aggregates": ["min", "max", "span"],
                "missing_policy": "indicator",
                "complex_tokens": "exclude",
                "transform": "coarse_bin",
                "bin_width": 50,
            },
        }
    }
    assert resolve_position_features_from_config(config) == (
        "min_residue_position",
        "max_residue_position",
        "residue_position_span",
    )
    assert resolve_position_options_from_config(config) == {
        "position_missing_policy": "indicator",
        "position_token_scope": "exclude_complex",
        "position_transform": "coarse_bin",
        "position_bin_width": 50,
    }


def test_residue_config_rejects_unknown_aggregate_or_complex_scope() -> None:
    with pytest.raises(ValueError, match="aggregate"):
        resolve_position_features_from_config(
            {
                "features": {
                    "residue_position": {
                        "enabled": True,
                        "aggregates": ["median"],
                    }
                }
            }
        )
    with pytest.raises(ValueError, match="complex_tokens"):
        resolve_position_options_from_config(
            {
                "features": {
                    "residue_position": {
                        "enabled": True,
                        "aggregates": ["min"],
                        "complex_tokens": "sometimes",
                    }
                }
            }
        )
