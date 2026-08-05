#!/usr/bin/env python
"""Run EXP-479 through the controlled parser baseline runner."""

from run_parser_v4_baseline import ROOT, run


if __name__ == "__main__":
    run(ROOT / "configs" / "exp479_parser_v4_native_semantic_range.yaml")
