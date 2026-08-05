#!/usr/bin/env python
"""Run one controlled parser N4 legacy/compatibility/native experiment."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from open_cancer.parser_baseline_features import (
    ParserBaselineFoldBuilder,
    validate_controlled_parser_baseline_config,
)
from open_cancer.robust_mutation_parser import (
    STOP_NOTATION_PARSER_CONTRACT,
    normalize_stop_notation_token,
    parse_stop_notation_invariant_cell,
)
from run_hotspot_xgb import ROOT, TEST_PATH, TRAIN_PATH, main


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    return parser.parse_args()


def run(config_path: Path) -> None:
    resolved_path = config_path.resolve()
    config = yaml.safe_load(resolved_path.read_text(encoding="utf-8"))
    representation = validate_controlled_parser_baseline_config(config)
    builder = (
        None
        if representation == "legacy"
        else ParserBaselineFoldBuilder(
            representation=representation,  # type: ignore[arg-type]
            train_path=TRAIN_PATH,
            test_path=TEST_PATH,
        )
    )
    main(
        resolved_path,
        fold_feature_builder=builder,
        mutation_cell_parser=parse_stop_notation_invariant_cell,
        mutation_parser_contract=STOP_NOTATION_PARSER_CONTRACT,
        hotspot_token_normalizer=normalize_stop_notation_token,
        runner_command=(
            "uv run python scripts/run_parser_v4_baseline.py --config "
            f"{resolved_path.relative_to(ROOT)}"
        ),
    )


if __name__ == "__main__":
    run(parse_args().config)
