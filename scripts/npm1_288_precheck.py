#!/usr/bin/env python
"""NPM1 288(WQ) precheck steps 1-4 (Issue #329).

RUN_MODE=explore, no EXP-ID. Steps: (1) Vera gates per fold, (2) burden
confound via screen_hotspot_burden_confound.py's logic, (3) cancer-type
distribution, (4) semantic equivalence vs frozen v1 (hotspot-34 +
co-mutation features).

Reference-AA note: the raw NPM1 column has TWO distinct tokens at position
288 -- `W288fs` (1 row) and `WQ288fs` (21 rows), both frameshift, both
LAML-only, zero row overlap. This is almost certainly the same underlying
NPM1 exon-12 frameshift driver mutation (the classic AML "NPM1c" event)
annotated with two different reference-AA lengths, not two different
mutations. hotspot__NPM1_288 is defined here as "any frameshift token at
position 288, regardless of 1- vs 2-letter reference annotation" -- a
deliberate deviation from strict single-reference matching, justified by
the fold sanity check below.

Usage: uv run python scripts/npm1_288_precheck.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.feature_family import find_semantically_equivalent_features
from open_cancer.frozen_feature_specs import materialize_frozen_feature_spec
from open_cancer.mutation_features import CO_MUTATION_PAIRS, parse_mutation_token

# NOTE: Issue #295's scripts/screen_hotspot_burden_confound.py (the general
# burden-ratio + cluster sweep tool) is on a separate not-yet-merged branch
# (PR #320) as of this writing, so this script does its own self-contained
# burden check below rather than importing across branches.

ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"
SPLIT_PATH = ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"
FEATURE_DIR = ROOT / "reports" / "analysis" / "npm1_288_precheck_data" / "_v1_features"

train = pd.read_csv(TRAIN_PATH, dtype=str, keep_default_na=False)
split = pd.read_csv(SPLIT_PATH)
assert set(train["ID"]) == set(split["ID"])
fold_of_row = train[["ID"]].merge(split, on="ID", how="left")["fold"].to_numpy()
y = train["SUBCLASS"].to_numpy()


def compute_npm1_288_flag(frame: pd.DataFrame) -> np.ndarray:
    flags = np.zeros(len(frame), dtype=np.float32)
    for row_index, cell in enumerate(frame["NPM1"]):
        if not cell or cell == "WT":
            continue
        for token_str in cell.split():
            if token_str == "WT":
                continue
            token = parse_mutation_token(token_str)
            if (
                token.mutation_type == "frameshift"
                and token.residue_positions
                and token.residue_positions[0] == 288
            ):
                flags[row_index] = 1.0
                break
    return flags


def main() -> None:
    flags = compute_npm1_288_flag(train)
    print("=== 정의 확인: hotspot__NPM1_288 (position 288 frameshift, ref 무관) ===")
    print(f"train 양성: {int(flags.sum())}건 (W288fs 1 + WQ288fs 21 = 22 기대)")
    print()

    # --- Step 1: Vera gates per fold ---
    GATE_A_SUPPORT, GATE_A_P0 = 10, 0.997
    GATE_B_SUPPORT = 5
    GATE_C_DOMINANCE = 0.8

    print("=== Step 1: Vera 게이트 (fold별) ===")
    rows = []
    for fold_id in sorted(split["fold"].unique()):
        train_mask = fold_of_row != fold_id
        flags_train = flags[train_mask]
        y_train = y[train_mask]
        support_train = int(flags_train.sum())
        n_train = len(flags_train)
        p0_train = float((flags_train == 0).sum() / n_train)
        positive_mask = flags_train == 1
        if support_train > 0:
            classes, counts = np.unique(y_train[positive_mask], return_counts=True)
            top_idx = int(np.argmax(counts))
            dominant_class, dominance = classes[top_idx], float(counts[top_idx] / support_train)
        else:
            dominant_class, dominance = "N/A", float("nan")
        gate_a = support_train >= GATE_A_SUPPORT and p0_train <= GATE_A_P0
        gate_b = support_train >= GATE_B_SUPPORT
        gate_c_blocked = (not np.isnan(dominance)) and dominance >= GATE_C_DOMINANCE
        rows.append(
            {
                "fold": fold_id,
                "support_train": support_train,
                "p0_train": round(p0_train, 6),
                "dominant_class": dominant_class,
                "dominance": None if np.isnan(dominance) else round(dominance, 4),
                "gate_A_pass": gate_a,
                "gate_B_pass": gate_b,
                "gate_C_blocked": gate_c_blocked,
            }
        )
    gate_df = pd.DataFrame(rows)
    pd.set_option("display.width", 200)
    print(gate_df.to_string(index=False))
    print()
    print(f"Gate A 전부 통과: {gate_df['gate_A_pass'].all()}")
    print(f"Gate B 전부 통과: {gate_df['gate_B_pass'].all()}")
    print(f"Gate C 발동(차단) 여부: {gate_df['gate_C_blocked'].any()}")
    print()

    # --- Step 2: burden confound (self-contained; see NOTE above on #295) ---
    print("=== Step 2: burden 교란 체크 ===")
    gene_columns = [c for c in train.columns if c not in {"ID", "SUBCLASS"}]
    burden = (train[gene_columns] != "WT").sum(axis=1).to_numpy()
    laml_mask = y == "LAML"
    carrier_mask = flags.astype(bool) & laml_mask
    non_carrier_mask = laml_mask & ~carrier_mask
    carrier_mean = burden[carrier_mask].mean()
    non_carrier_mean = burden[non_carrier_mask].mean()
    print(
        f"union(22) 기준 LAML 내부: carrier(n={carrier_mask.sum()}) 평균 burden="
        f"{carrier_mean:.2f} vs non-carrier(n={non_carrier_mask.sum()}) 평균 burden="
        f"{non_carrier_mean:.2f}, ratio={carrier_mean / non_carrier_mean:.3f}"
    )
    print()
    print("암종별 평균 burden 순위(낮을수록 저-변이부담, LAML 위치 확인):")
    burden_by_class = (
        pd.DataFrame({"class": y, "burden": burden}).groupby("class")["burden"].mean().sort_values()
    )
    print(burden_by_class.to_string())
    print(f"\nLAML 순위: {list(burden_by_class.index).index('LAML') + 1} / {len(burden_by_class)} (낮을수록 저-변이부담)")
    print()

    # --- Step 3: cancer-type distribution ---
    print("=== Step 3: 암종 분포 (오염 여부) ===")
    carrier_classes = y[flags.astype(bool)]
    print(pd.Series(carrier_classes).value_counts().to_string())
    print(f"LAML 100% 집중 여부: {(carrier_classes == 'LAML').all()}")
    print()

    # --- Step 4: semantic equivalence vs frozen v1 + co-mutation pairs ---
    print("=== Step 4: 기존 hotspot-34/co-mutation feature와 semantic equivalence ===")
    print(
        "NPM1이 관여하는 기존 CO_MUTATION_PAIRS: "
        f"{[p for p in CO_MUTATION_PAIRS if 'NPM1' in p]} (없으면 co-mutation 축과는 무관)"
    )

    manifest = materialize_frozen_feature_spec(
        root=ROOT, name="v1", output_dir=FEATURE_DIR, train_path=TRAIN_PATH, test_path=TEST_PATH
    )
    x_train_base = sparse.load_npz(FEATURE_DIR / "train_features.npz").tocsr()
    base_names = json.loads((FEATURE_DIR / "feature_names.json").read_text(encoding="utf-8"))
    candidate_matrix = sparse.csr_matrix(flags[:, None])
    matches = find_semantically_equivalent_features(
        candidate_matrix, ["hotspot__NPM1_288"], x_train_base, base_names
    )
    print(f"semantic_equivalence_matches: {matches}")
    print("(빈 dict면 v1의 기존 컬럼 중 어느 것과도 byte-identical하지 않다는 뜻)")
    print(f"feature spec identity: base_feature_spec_sha256={manifest['base_feature_spec_sha256']}")


if __name__ == "__main__":
    main()
