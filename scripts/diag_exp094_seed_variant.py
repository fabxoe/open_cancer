#!/usr/bin/env python
"""Diagnostic-only ad-hoc rerun of EXP-094 (pure v1 base spec, no added feature)
with an alternate model seed base -- to quantify the feature-independent noise
floor of DLBC OOF probabilities (Issue #251).

NOT an official experiment: no EXP-ID, no History entry, no writes under
official exp094 paths. All outputs go under
`reports/analysis/dlbc_noise_floor_data/` only.

Usage: uv run python scripts/diag_exp094_seed_variant.py <seed_base>
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy import sparse
from sklearn.metrics import f1_score

from open_cancer.constants import CLASS_LABELS
from open_cancer.frozen_feature_specs import materialize_frozen_feature_spec
from open_cancer.model_runner import create_model_adapter, run_canonical_cv

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "reports" / "analysis" / "dlbc_noise_floor_data"
TRAIN = ROOT / "data" / "raw" / "train.csv"
TEST = ROOT / "data" / "raw" / "test.csv"
SPLIT = ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"
CONFIG_PATH = ROOT / "configs" / "exp094_feature_spec_v1.yaml"

seed_base = int(sys.argv[1])

feature_dir = OUT_DIR / "_diag_exp094_v1_features"  # shared cache, read-only reuse across seeds
model_dir = OUT_DIR / f"_diag_exp094_seed{seed_base}_models"
model_dir.mkdir(parents=True, exist_ok=True)

clock = time.perf_counter()

feature_spec_manifest = materialize_frozen_feature_spec(
    root=ROOT, name="v1", output_dir=feature_dir, train_path=TRAIN, test_path=TEST
)
x_train = sparse.load_npz(feature_dir / "train_features.npz").tocsr()
x_test = sparse.load_npz(feature_dir / "test_features.npz").tocsr()
assert x_train.shape[1] == 35119, f"unexpected column count: {x_train.shape[1]} (expected pure v1 base)"

train_raw = pd.read_csv(TRAIN, dtype=str, keep_default_na=False)
test_raw = pd.read_csv(TEST, dtype=str, keep_default_na=False)
train = train_raw[["ID", "SUBCLASS"]]
split = train[["ID"]].merge(
    pd.read_csv(SPLIT, dtype={"ID": str, "fold": int}),
    on="ID", how="left", validate="one_to_one", sort=False,
)
folds = split["fold"].to_numpy(dtype=np.int32)
targets = train["SUBCLASS"].map({label: i for i, label in enumerate(CLASS_LABELS)}).to_numpy(dtype=np.int32)

config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
params = dict(config["model"])
assert params["colsample_bytree"] == 0.8 and params["n_jobs"] == 8, "config drifted from expected EXP-094 baseline"

print(f"seed_base={seed_base}, model params (unchanged from EXP-094): {params}")
print(
    "feature spec identity: "
    f"base_feature_spec_sha256={feature_spec_manifest['base_feature_spec_sha256']}, "
    f"source_config_sha256={feature_spec_manifest['source_config_sha256']}, "
    f"train_input_sha256={feature_spec_manifest['train_input_sha256']}, "
    f"test_input_sha256={feature_spec_manifest['test_input_sha256']}"
)

result = run_canonical_cv(
    train_features=x_train,
    test_features=x_test,
    targets=targets,
    folds=folds,
    adapter_factory=lambda fold: create_model_adapter("xgboost", params, seed_base + fold),
    model_dir=model_dir,
    balanced_sample_weight=True,
)

pred = result.oof_probabilities.argmax(axis=1)
f1 = f1_score(targets, pred, average="macro")
print(f"Diagnostic OOF macro F1 (seed_base={seed_base}): {f1:.10f}")

oof_df = pd.DataFrame(result.oof_probabilities, columns=CLASS_LABELS).assign(ID=train.ID.values)
oof_path = OUT_DIR / f"diag_exp094_seed{seed_base}_oof.csv"
oof_df.to_csv(oof_path, index=False)
print(f"Wrote {oof_path}")
print(f"Elapsed: {time.perf_counter() - clock:.1f}s")

with open(OUT_DIR / f"diag_exp094_seed{seed_base}_meta.json", "w", encoding="utf-8") as fh:
    json.dump(
        {
            "oof_macro_f1": float(f1),
            "seed_base": seed_base,
            "params": params,
            "feature_spec_identity": {
                "base_feature_spec_sha256": feature_spec_manifest["base_feature_spec_sha256"],
                "source_config_sha256": feature_spec_manifest["source_config_sha256"],
                "train_input_sha256": feature_spec_manifest["train_input_sha256"],
                "test_input_sha256": feature_spec_manifest["test_input_sha256"],
            },
        },
        fh,
        indent=2,
    )
