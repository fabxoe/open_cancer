#!/usr/bin/env python
"""DominoEffect-style panel-wide hotspot screening (Vera Health criteria).

RUN_MODE=explore (target-independent: does not read SUBCLASS during
candidate generation). No EXP-ID, no model training, no fold-safety
machinery. Goal is only to check whether new hotspot candidates exist
outside the already-adopted 34-position table (`hotspot_features.py`'s
`EXTENDED_HOTSPOTS`).

Criteria (Vera Health, as specified in Issue #295's originating
screening):
- residue observed in >= 5 train rows (reference-aware: same (gene,
  position) must share one consistent reference AA)
- within a 250aa window centered on that residue (position +/- 125,
  the midpoint of the requested 200-300aa range), that residue's own
  count is >= 15% of ALL variant tokens (any position, any type) in
  that gene's window

Output: `reports/analysis/dominoeffect_screening_candidates.csv` (all
candidates) is the fixed, reproducible input consumed by
`screen_hotspot_burden_confound.py`'s Issue #295 sweep.

Usage: uv run python scripts/screen_domino_effect_hotspots.py
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from open_cancer.hashing import sha256_file
from open_cancer.hotspot_features import EXTENDED_HOTSPOTS
from open_cancer.mutation_features import parse_mutation_token

ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
OUT_PATH = ROOT / "reports" / "analysis" / "dominoeffect_screening_candidates.csv"

WINDOW_HALF_WIDTH = 125  # -> 250aa window, midpoint of requested 200-300aa range
MIN_TRAIN_COUNT = 5
MIN_WINDOW_CONCENTRATION = 0.15

EXISTING_HOTSPOT_POSITIONS = {(gene, position) for gene, position, _ref in EXTENDED_HOTSPOTS}


def main() -> None:
    train = pd.read_csv(TRAIN_PATH, dtype=str, keep_default_na=False)
    gene_columns = [c for c in train.columns if c not in {"ID", "SUBCLASS"}]
    print(f"패널 유전자 수: {len(gene_columns)}, train 행 수: {len(train)}")
    print(f"기존 hotspot-34 제외 대상: {len(EXISTING_HOTSPOT_POSITIONS)}개 (gene, position) 쌍")

    # gene -> list of (position, ref, row_index) for every parsed token with a
    # residue position (any mutation type; used both for candidate counting and
    # for the window denominator). Target-independent: SUBCLASS not read here.
    gene_tokens: dict[str, list[tuple[int, str, int]]] = defaultdict(list)

    gene_frame = train.loc[:, gene_columns]
    for row_index, row in enumerate(gene_frame.itertuples(index=False, name=None)):
        for gene, cell in zip(gene_columns, row):
            if not cell or cell == "WT":
                continue
            for token_str in cell.split():
                if token_str == "WT":
                    continue
                token = parse_mutation_token(token_str)
                if not token.residue_positions or token.reference_amino_acid is None:
                    continue
                position = token.residue_positions[0]
                gene_tokens[gene].append((position, token.reference_amino_acid, row_index))

    print(f"위치 정보가 있는 토큰을 가진 유전자 수: {len(gene_tokens)}")

    candidates = []
    for gene, tokens in gene_tokens.items():
        by_position: dict[int, list[tuple[str, int]]] = defaultdict(list)
        for position, ref, row_index in tokens:
            by_position[position].append((ref, row_index))

        all_positions_sorted = sorted(p for p, _, _ in tokens)

        for position, ref_rows in by_position.items():
            if (gene, position) in EXISTING_HOTSPOT_POSITIONS:
                continue
            ref_counts = Counter(ref for ref, _ in ref_rows)
            dominant_ref, dominant_ref_count = ref_counts.most_common(1)[0]
            if dominant_ref_count < MIN_TRAIN_COUNT:
                continue
            matching_rows = [row_index for ref, row_index in ref_rows if ref == dominant_ref]
            train_count = len(matching_rows)
            if train_count < MIN_TRAIN_COUNT:
                continue

            window_lo, window_hi = position - WINDOW_HALF_WIDTH, position + WINDOW_HALF_WIDTH
            window_total = sum(1 for p in all_positions_sorted if window_lo <= p <= window_hi)
            concentration = train_count / window_total if window_total else 0.0
            if concentration < MIN_WINDOW_CONCENTRATION:
                continue

            candidates.append(
                {
                    "gene": gene,
                    "position": position,
                    "reference_aa": dominant_ref,
                    "train_count": train_count,
                    "window_total": window_total,
                    "window_concentration": round(concentration, 4),
                }
            )

    print(f"\n=== 통과 후보 수: {len(candidates)} ===\n")
    candidates.sort(key=lambda c: c["train_count"], reverse=True)

    result_df = pd.DataFrame(candidates)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(OUT_PATH, index=False)
    print(f"저장: {OUT_PATH}")
    print(f"input SHA-256 (train.csv): {sha256_file(TRAIN_PATH)}")
    print(f"output SHA-256 (candidates csv): {sha256_file(OUT_PATH)}")


if __name__ == "__main__":
    main()
