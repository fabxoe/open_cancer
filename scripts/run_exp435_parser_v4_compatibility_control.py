#!/usr/bin/env python
"""Run EXP-435 through the controlled parser baseline runner."""

from run_parser_v4_baseline import ROOT, run


if __name__ == "__main__":
    run(ROOT / "configs" / "exp435_parser_v4_compatibility_control.yaml")
