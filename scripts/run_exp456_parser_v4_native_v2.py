#!/usr/bin/env python
"""Run EXP-456 through the controlled parser baseline runner."""

from run_parser_v4_baseline import ROOT, run


if __name__ == "__main__":
    run(ROOT / "configs" / "exp456_parser_v4_native_v2.yaml")
