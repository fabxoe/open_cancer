#!/usr/bin/env python
"""Run EXP-448 through the controlled parser baseline runner."""

from run_parser_v4_baseline import ROOT, run


if __name__ == "__main__":
    run(ROOT / "configs" / "exp448_parser_v4_native_no_provenance.yaml")
