#!/usr/bin/env python
"""Run EXP-093: mutation type + max residue position + clean hotspots."""

from run_hotspot_xgb import ROOT, main


if __name__ == "__main__":
    main(ROOT / "configs" / "exp093_mutation_position_hotspot.yaml")
