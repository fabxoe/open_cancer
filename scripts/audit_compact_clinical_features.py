#!/usr/bin/env python
"""Audit fold-safe dimensions of the compact clinical feature builder."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from open_cancer.compact_clinical_features import CompactClinicalMutationFamily


ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
SPLIT_PATH = ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"
OUTPUT_PATH = ROOT / "reports" / "analysis" / "compact_clinical_baseline" / "audit.json"


def _compact(metadata: dict) -> dict:
    return {
        key: value for key, value in metadata.items()
        if key != "recurrent_missense_support"
    }


def main() -> None:
    train = pd.read_csv(TRAIN_PATH, dtype=str)
    split = pd.read_csv(SPLIT_PATH, dtype={"ID": str, "fold": int})
    if train["ID"].tolist() != split["ID"].tolist():
        raise ValueError("canonical split ID/order mismatch")
    genes = tuple(column for column in train.columns if column not in {"ID", "SUBCLASS"})
    family = CompactClinicalMutationFamily(genes, hotspot_min_patient_count=5)
    full = family.fit(train)
    folds = []
    for fold in sorted(split["fold"].unique()):
        fold_train = train.loc[split["fold"].ne(fold)].reset_index(drop=True)
        fitted = family.fit(fold_train)
        folds.append({"fold": int(fold), **_compact(fitted.metadata())})
    payload = {
        "source_document_claim": {
            "mutated_gene_count": 4230,
            "truncating_gene_count": 3671,
            "recurrent_missense_gene_count": 91,
            "recurrent_missense_key_count": 230,
            "feature_count": 8005,
        },
        "parser_v4_full_train": _compact(full.metadata()),
        "parser_v4_fold_train": folds,
        "interpretation": (
            "Feature architecture is reproduced, while parser-v4 semantics are "
            "authoritative; source regex-parser counts are not forced."
        ),
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
