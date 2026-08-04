#!/usr/bin/env python
"""Recompute the Issue #251 5-seed DLBC noise-floor summary from raw data.

Reads the 5 raw per-seed OOF CSVs committed under
`reports/analysis/dlbc_noise_floor_data/` plus the official EXP-094 baseline
OOF (fetch first via `scripts/fetch_experiment_artifacts.py --experiment
EXP-094` if `oof/exp094_feature_spec_v1.csv` is not already present locally)
and reproduces every number quoted in
`reports/analysis/sparse_binary_feature_dlbc_sensitivity.md`'s "5-seed 노이즈
바닥" section: per-seed delta mean/std, the 5-seed std distribution, the
pairwise correlation matrix, and where the 3 feature-added diagnostics
(#246) fall relative to the noise floor.

Usage: uv run python scripts/dlbc_5seed_noise_floor.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "reports" / "analysis" / "dlbc_noise_floor_data"
BASELINE_PATH = ROOT / "oof" / "exp094_feature_spec_v1.csv"

CLASS_ORDER = [
    "ACC", "BLCA", "BRCA", "CESC", "COAD", "DLBC", "GBMLGG", "HNSC", "KIPAN",
    "KIRC", "LAML", "LGG", "LIHC", "LUAD", "LUSC", "OV", "PAAD", "PCPG",
    "PRAD", "SARC", "SKCM", "STES", "TGCT", "THCA", "THYM", "UCEC",
]

SEEDS = [1001, 1002, 2001, 2002, 2003]

FEATURE_ADDED_STD = {
    "원래 EXP-170 (colsample=0.8,n_jobs=8)": 0.054009,
    "진단1 (colsample=1.0)": 0.063833,
    "진단2 (n_jobs=1)": 0.059927,
}


def main() -> None:
    if not BASELINE_PATH.is_file():
        raise SystemExit(
            f"{BASELINE_PATH} 없음 -- 먼저 실행: "
            "uv run python scripts/fetch_experiment_artifacts.py --experiment EXP-094"
        )

    baseline_raw = pd.read_csv(BASELINE_PATH)
    baseline = baseline_raw.rename(columns={f"PROBA_{c}": c for c in CLASS_ORDER}).set_index("ID")
    baseline_truth = baseline["SUBCLASS_TRUE"]
    mask = baseline_truth == "DLBC"
    ids = baseline.index[mask]
    baseline_prob = baseline.loc[ids, "DLBC"]

    noise_floor = {}
    for seed in SEEDS:
        diag = pd.read_csv(DATA_DIR / f"diag_exp094_seed{seed}_oof.csv").set_index("ID")
        diag = diag.loc[baseline.index]
        delta = diag.loc[ids, "DLBC"] - baseline_prob
        noise_floor[seed] = delta

    stds = pd.Series({seed: d.std() for seed, d in noise_floor.items()})
    means = pd.Series({seed: d.mean() for seed, d in noise_floor.items()})

    print("########## 5-seed 노이즈 바닥 ##########")
    for seed in SEEDS:
        print(f"seed_base={seed}: delta mean={means[seed]:+.6f}, delta std={stds[seed]:.6f}")

    print()
    print(
        f"5-seed std 분포: mean={stds.mean():.6f}, std={stds.std():.6f}, "
        f"min={stds.min():.6f}, max={stds.max():.6f}"
    )
    print(
        f"5-seed mean(delta) 분포: mean={means.mean():.6f}, std={means.std():.6f}, "
        f"min={means.min():.6f}, max={means.max():.6f}"
    )

    print()
    print("--- pairwise correlation (5x5) ---")
    delta_frame = pd.DataFrame(noise_floor)
    print(delta_frame.corr().round(3).to_string())
    avg_offdiag_corr = (delta_frame.corr().to_numpy().sum() - 5) / (5 * 4)
    print(f"평균 off-diagonal correlation: {avg_offdiag_corr:.4f}")

    print()
    print("########## feature 추가 3건이 노이즈 분포에서 차지하는 위치 ##########")
    noise_stds_sorted = sorted(stds.tolist())
    print(f"노이즈 바닥 std 5개 정렬: {[round(s, 4) for s in noise_stds_sorted]}")
    for name, std_val in FEATURE_ADDED_STD.items():
        n_below = sum(1 for s in noise_stds_sorted if s < std_val)
        percentile = n_below / len(noise_stds_sorted) * 100
        print(f"  {name}: std={std_val:.6f} -> 노이즈 5개 중 {n_below}개보다 큼 (백분위 ~{percentile:.0f}%)")

    noise_std_mean = stds.mean()
    noise_std_std = stds.std()
    print()
    print(f"참고: feature 추가 3건의 std 평균 = {np.mean(list(FEATURE_ADDED_STD.values())):.6f}")
    print(f"      노이즈 바닥 5개의 std 평균 = {noise_std_mean:.6f} (표준편차 {noise_std_std:.6f}, n=5)")
    ratio = np.mean(list(FEATURE_ADDED_STD.values())) / noise_std_mean
    print(f"      비율 = {ratio:.2f}배")


if __name__ == "__main__":
    main()
