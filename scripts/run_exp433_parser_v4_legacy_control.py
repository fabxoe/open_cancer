#!/usr/bin/env python
"""Run EXP-433 through the controlled parser baseline runner."""

from run_parser_v4_baseline import ROOT, run


if __name__ == "__main__":
    run(ROOT / "configs" / "exp433_parser_v4_legacy_control.yaml")
