#!/usr/bin/env python
"""Burden-confound and shared-carrier-ID cluster check for hotspot candidates.

RUN_MODE=explore, **target-informed exploratory QC** (not
target-independent): `screen_burden_confound` reads `SUBCLASS` to compute
each candidate's dominant cancer type and the carrier/non-carrier burden
comparison within that class. This is the standard methodology addition
adopted from Issue #295: a DominoEffect-style recurrence/window screening
(e.g. `screen_domino_effect_hotspots.py`'s candidate table) can surface
"hotspots" that are really a side effect of a handful of hypermutated
samples in a naturally low-TMB (or hypermutator-subtype-prone) cancer type
recurring across many unrelated gene positions -- discovered via a 6-gene
ACC cluster (LRIG1 x2, SOWAHC, CMPK2, PEX6, NFKB2, TM7SF2) that all turned
out to share carriers from a set of high-burden ACC samples.

Two independent checks are applied to every candidate:

1. Burden ratio: mean `mutated_gene_count` (count of non-WT gene columns per
   sample) among carriers vs non-carriers, computed *within the candidate's
   dominant cancer type* (not globally -- baseline burden varies a lot by
   cancer type, e.g. UCEC/SKCM/COAD hypermutator subtypes are naturally
   higher than ACC). A high ratio with a small `n_in_dominant_class`
   (e.g. 1-2) is weak evidence -- it can be a single extreme-TMB sample --
   so the ratio should be read together with `n_in_dominant_class`.
2. Shared-carrier-ID clustering: candidates whose carrier sets overlap
   heavily (Jaccard >= 0.3) with another candidate's carriers *in the same
   dominant cancer type* are flagged regardless of burden ratio -- this is
   what actually caught SOWAHC/NFKB2 in the original ACC cluster, since
   their own individual burden ratios were not elevated (0.65 / 1.00) even
   though they share most of their carriers with the other 4 ACC genes.

A high burden ratio does **not** prove a candidate is a fake/spurious
mutation call -- a real hypermutator subtype (e.g. UCEC POLE/MSI) driving
broad recurrence is itself known real biology, not corrupted data. Flagged
candidates are labeled "burden-confounded" (their in-panel recurrence
signal cannot be trusted at face value without independent literature
support), not "artifact" -- that stronger word is deliberately avoided
throughout this module and its outputs.

## Scope boundaries for any future *official* (EXP-ID) use

(a) The exclusion list this script produces is computed from the full
    train label column and is for explanation / hypothesis generation
    only. Do not wire it directly into an official OOF feature-selection
    step.
(b) If a future official experiment wants to use this filter, dominant
    class and the exclusion list must be recomputed independently within
    each outer-train fold; the resulting fixed mask is then applied to
    that fold's validation/test rows -- never fit on validation/test rows
    themselves.
(c) See above: report/label candidates as "burden-confounded", not
    "artifact" -- the ratio is evidence the panel-recurrence signal may be
    inflated by a hypermutator subtype, not proof the mutation call itself
    is spurious.
(d) `BURDEN_CONFOUND_RATIO`/`BURDEN_MILD_CONCERN_RATIO`/
    `CLUSTER_JACCARD_THRESHOLD` below are **exploratory thresholds**, not
    pre-registered ones -- `BURDEN_CONFOUND_RATIO=1.8` was set to match the
    ACC cluster's own observed ratio (43.9/23.75 ~= 1.85) *after* seeing
    that data, and `CLUSTER_JACCARD_THRESHOLD=0.3` was likewise chosen by
    inspecting the observed pair distribution. Treat any exclusion decision
    built on these specific cutoffs as provisional, not as a validated gate
    threshold in the sense the project's official EXP acceptance gates are.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd

from open_cancer.hashing import sha256_file
from open_cancer.mutation_features import parse_mutation_token

REPO_ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = REPO_ROOT / "data" / "raw" / "train.csv"
RESULTS_PATH = REPO_ROOT / "reports" / "analysis" / "hotspot_screening_burden_control_results.csv"
CLUSTERS_PATH = REPO_ROOT / "reports" / "analysis" / "hotspot_screening_burden_control_clusters.csv"

# Exploratory thresholds -- see docstring boundary (d) above.
BURDEN_MILD_CONCERN_RATIO = 1.4
BURDEN_CONFOUND_RATIO = 1.8
RELIABLE_MIN_N_IN_DOMINANT_CLASS = 5
CLUSTER_JACCARD_THRESHOLD = 0.3


def _carrier_row_indices(gene_series: pd.Series, position: int, reference_aa: str) -> list[int]:
    rows = []
    for row_index, cell in enumerate(gene_series.to_numpy()):
        if not cell or cell == "WT":
            continue
        for token_str in cell.split():
            if token_str == "WT":
                continue
            token = parse_mutation_token(token_str)
            if not token.residue_positions or token.reference_amino_acid is None:
                continue
            if token.residue_positions[0] == position and token.reference_amino_acid == reference_aa:
                rows.append(row_index)
                break
    return rows


def screen_burden_confound(
    candidates: pd.DataFrame,
    train_path: Path = TRAIN_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the burden-ratio and shared-ID cluster check over a candidate table.

    Target-informed: reads `SUBCLASS` from `train_path` to compute each
    candidate's dominant cancer type. See module docstring boundaries
    (a)-(d) before wiring this into any official (EXP-ID) experiment.

    `candidates` must have columns: gene, position, reference_aa (as
    produced by `screen_domino_effect_hotspots.py`'s candidate table).
    Returns (per_candidate_results, cluster_pairs).
    """

    train = pd.read_csv(train_path, dtype=str, keep_default_na=False)
    gene_columns = [c for c in train.columns if c not in {"ID", "SUBCLASS"}]
    subclass = train["SUBCLASS"].to_numpy()
    ids = train["ID"].to_numpy()
    burden = (train[gene_columns] != "WT").sum(axis=1).to_numpy()

    results = []
    carrier_id_sets: dict[str, frozenset[str]] = {}
    dominant_class_by_key: dict[str, str | None] = {}

    for _, row in candidates.iterrows():
        gene, position, reference_aa = row["gene"], int(row["position"]), row["reference_aa"]
        key = f"{gene}_{position}"
        if gene not in train.columns:
            continue
        row_indices = _carrier_row_indices(train[gene], position, reference_aa)
        if not row_indices:
            continue
        carrier_id_sets[key] = frozenset(ids[row_indices])

        classes = [subclass[i] for i in row_indices]
        dominant_class, dominant_count = Counter(classes).most_common(1)[0]
        dominant_class_by_key[key] = dominant_class
        dominant_share = dominant_count / len(classes)

        class_mask = subclass == dominant_class
        carrier_mask_in_class = pd.Series(False, index=range(len(train)))
        carrier_mask_in_class.iloc[row_indices] = True
        carrier_mask_in_class = carrier_mask_in_class.to_numpy() & class_mask
        non_carrier_mask_in_class = class_mask & ~carrier_mask_in_class

        carrier_burden = burden[carrier_mask_in_class]
        non_carrier_burden = burden[non_carrier_mask_in_class]
        carrier_mean = float(carrier_burden.mean()) if len(carrier_burden) else float("nan")
        non_carrier_mean = float(non_carrier_burden.mean()) if len(non_carrier_burden) else float("nan")
        ratio = carrier_mean / non_carrier_mean if non_carrier_mean else float("nan")

        results.append(
            {
                "gene": gene,
                "position": position,
                "reference_aa": reference_aa,
                "train_count": row.get("train_count"),
                "dominant_class": dominant_class,
                "dominant_class_share": round(dominant_share, 4),
                "n_in_dominant_class": int(carrier_mask_in_class.sum()),
                "carrier_burden_mean_in_class": round(carrier_mean, 2),
                "non_carrier_burden_mean_in_class": round(non_carrier_mean, 2),
                "burden_ratio": round(ratio, 3) if ratio == ratio else None,
            }
        )

    result_df = pd.DataFrame(results)
    result_df["burden_flag"] = pd.cut(
        result_df["burden_ratio"],
        bins=[-float("inf"), BURDEN_MILD_CONCERN_RATIO, BURDEN_CONFOUND_RATIO, float("inf")],
        labels=["clean", "mild_concern", "burden_confounded_candidate"],
    )
    result_df["burden_reliable"] = result_df["n_in_dominant_class"] >= RELIABLE_MIN_N_IN_DOMINANT_CLASS

    keys = list(carrier_id_sets)
    cluster_rows = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            key_a, key_b = keys[i], keys[j]
            class_a, class_b = dominant_class_by_key[key_a], dominant_class_by_key[key_b]
            if class_a != class_b or class_a is None:
                continue
            set_a, set_b = carrier_id_sets[key_a], carrier_id_sets[key_b]
            intersection = set_a & set_b
            union = set_a | set_b
            jaccard = len(intersection) / len(union) if union else 0.0
            if jaccard >= CLUSTER_JACCARD_THRESHOLD:
                cluster_rows.append(
                    {
                        "candidate_a": key_a,
                        "candidate_b": key_b,
                        "dominant_class": class_a,
                        "shared_ids": len(intersection),
                        "jaccard": round(jaccard, 3),
                    }
                )
    cluster_df = pd.DataFrame(cluster_rows)
    return result_df, cluster_df


def recommended_exclusions(result_df: pd.DataFrame, cluster_df: pd.DataFrame) -> set[str]:
    """Union of (reliable high burden ratio) and (shared-ID cluster member).

    Hypothesis-generation output only -- see module docstring boundary (a).
    """

    reliable_confounded = result_df[
        (result_df["burden_flag"] == "burden_confounded_candidate") & result_df["burden_reliable"]
    ]
    reliable_keys = set(reliable_confounded["gene"] + "_" + reliable_confounded["position"].astype(str))
    cluster_members: set[str] = set()
    if len(cluster_df):
        cluster_members |= set(cluster_df["candidate_a"]) | set(cluster_df["candidate_b"])
    return reliable_keys | cluster_members


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: uv run python scripts/screen_hotspot_burden_confound.py <candidates.csv>"
        )
    candidates_path = Path(sys.argv[1])
    candidates_table = pd.read_csv(candidates_path)
    results, clusters = screen_burden_confound(candidates_table)
    exclusions = recommended_exclusions(results, clusters)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(RESULTS_PATH, index=False)
    clusters.to_csv(CLUSTERS_PATH, index=False)
    print(
        f"후보 {len(candidates_table)}건 중 {len(exclusions)}건 제외 권고"
        "(가설 생성용, 공식 feature 선택 직접 사용 금지)"
    )
    print(sorted(exclusions))
    print(f"저장: {RESULTS_PATH}")
    print(f"SHA-256: {sha256_file(RESULTS_PATH)}")
    print(f"저장: {CLUSTERS_PATH}")
    print(f"SHA-256: {sha256_file(CLUSTERS_PATH)}")
