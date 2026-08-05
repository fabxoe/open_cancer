#!/usr/bin/env python
"""Run EXP-444 through the controlled parser baseline runner."""

from run_parser_v4_baseline import ROOT, run


if __name__ == "__main__":
    run(ROOT / "configs" / "exp444_parser_v4_supported_range_hybrid.yaml")
