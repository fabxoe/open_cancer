#!/usr/bin/env python
"""EXPLORE ONLY (Issue #557, RUN_MODE=explore, no EXP-ID): quick unofficial OOF
signal check for adding a Pfam in-domain residue indicator on top of EXP-374's
canonical feature set.

NOT an official experiment. Writes no EXPERIMENT_HISTORY.md entry, no
model/oof/submission artifacts under an exp-slug path, and does not require a
clean worktree. The domain manifest
(knowledge/ensembl_protein_domain_annotation_v1.json) is still
PENDING_TEAM_LEAD_APPROVAL -- this number is a "worth pursuing?" signal only,
not an adoptable result. If it looks promising, this needs a real Experiment
Issue + EXP-ID, run through the official `run_hotspot_xgb.main()` path with a
proper resolved config, once approval lands.

Reuses EXP-374's cached base+hotspot feature matrix
(data/processed/exp374_stop_notation_isoform_mask_features/), EXP-374's exact
model hyperparameters and checkpoint-selection policy
(configs/exp374_stop_isoform_residue_mask.yaml), and the same fold-safe
pathway-family builder (build_fold_features() from
run_exp374_stop_isoform_residue_mask.py) EXP-374 itself uses. Only the new
Pfam in-domain indicator column set is added; nothing else changes.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
import yaml
from scipy import sparse
from sklearn.metrics import f1_score
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.checkpoint_selection import (
    audit_xgboost_validation_iterations,
    predict_xgboost_at_iteration,
)
from open_cancer.constants import CLASS_LABELS
from open_cancer.domain_occupancy_position import (
    DomainOccupancyTransformer,
    load_domain_intervals,
)
from open_cancer.feature_family import drop_named_base_features
from open_cancer.isoform_semantics import load_annotation_index
from open_cancer.mutation_features import build_mutation_features

from run_exp374_stop_isoform_residue_mask import build_fold_features

ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data/raw/train.csv"
TEST_PATH = ROOT / "data/raw/test.csv"
SPLIT_PATH = ROOT / "data/splits/stratified_5fold_seed42.csv"
CONFIG_PATH = ROOT / "configs/exp374_stop_isoform_residue_mask.yaml"
BASE_FEATURE_DIR = ROOT / "data/processed/exp374_stop_notation_isoform_mask_features"
BASE_SUBDIR = BASE_FEATURE_DIR / "base_mutation_type_features"
ANNOTATION_CACHE = (
    ROOT / "data/external/ensembl_release_116/competition_gene_isoform_index.json"
)
DOMAIN_COMBINED_PATH = (
    ROOT / "data/external/ensembl_release_116/domain_features/pfam_domains_by_protein.json"
)
SCRATCH_DOMAIN_DIR = ROOT / "data/processed/explore_pfam_domain_indicator_scratch"

EXP374_BASELINE_OOF_MACRO_F1 = 0.4267909268459148


def build_domain_columns():
    annotation_index = load_annotation_index(ANNOTATION_CACHE)
    domain_intervals = load_domain_intervals(DOMAIN_COMBINED_PATH)
    transformer = DomainOccupancyTransformer(annotation_index, domain_intervals)

    build_mutation_features(
        TRAIN_PATH,
        TEST_PATH,
        SCRATCH_DOMAIN_DIR,
        selected_position_features=("max_residue_position",),
        position_missing_policy="zero",
        position_token_scope="include_complex",
        position_transform="raw",
        position_token_transformer=transformer,
        position_semantic_contract={
            "status": "EXPLORE_ONLY_PENDING_TEAM_LEAD_APPROVAL",
            "issue": 557,
            "manifest_path": "knowledge/ensembl_protein_domain_annotation_v1.json",
            "target_used": False,
            "test_distribution_used_for_rule": False,
            "public_leaderboard_used": False,
        },
    )
    names = json.loads((SCRATCH_DOMAIN_DIR / "feature_names.json").read_text(encoding="utf-8"))
    domain_indices = [
        index for index, name in enumerate(names) if name.endswith("__max_residue_position")
    ]
    domain_names = [
        names[index].removesuffix("__max_residue_position") + "__in_pfam_domain"
        for index in domain_indices
    ]

    train_matrix = sparse.load_npz(SCRATCH_DOMAIN_DIR / "train_features.npz")
    test_matrix = sparse.load_npz(SCRATCH_DOMAIN_DIR / "test_features.npz")
    train_ids = pd.read_csv(SCRATCH_DOMAIN_DIR / "train_ids.csv", dtype=str)["ID"]
    test_ids = pd.read_csv(SCRATCH_DOMAIN_DIR / "test_ids.csv", dtype=str)["ID"]

    return (
        train_matrix[:, domain_indices].tocsr(),
        test_matrix[:, domain_indices].tocsr(),
        domain_names,
        train_ids,
        test_ids,
    )


def main() -> None:
    if not DOMAIN_COMBINED_PATH.is_file():
        raise SystemExit(
            "먼저 uv run python scripts/fetch_ensembl_pfam_domain_catalog.py 를 실행하세요."
        )

    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))

    train_meta = pd.read_csv(TRAIN_PATH, usecols=["ID", "SUBCLASS"], dtype=str)
    test_meta = pd.read_csv(TEST_PATH, usecols=["ID"], dtype=str)
    folds = pd.read_csv(SPLIT_PATH, dtype={"ID": str, "fold": int})
    train = train_meta.merge(folds, on="ID", how="left", validate="one_to_one", sort=False)
    if not train["ID"].equals(train_meta["ID"]) or train["fold"].isna().any():
        raise RuntimeError("fold 병합 정합성 오류")

    x_all = sparse.load_npz(BASE_FEATURE_DIR / "train_features.npz")
    x_test = sparse.load_npz(BASE_FEATURE_DIR / "test_features.npz")
    all_feature_names = json.loads(
        (BASE_FEATURE_DIR / "feature_names.json").read_text(encoding="utf-8")
    )

    cached_train_ids = pd.read_csv(BASE_SUBDIR / "train_ids.csv", dtype=str)["ID"]
    cached_test_ids = pd.read_csv(BASE_SUBDIR / "test_ids.csv", dtype=str)["ID"]
    if not cached_train_ids.equals(train["ID"]) or not cached_test_ids.equals(test_meta["ID"]):
        raise RuntimeError("캐시 피처 ID 순서가 원본과 다릅니다.")

    print("Pfam 도메인 indicator 컬럼 생성 중...")
    domain_train, domain_test, domain_names, domain_train_ids, domain_test_ids = (
        build_domain_columns()
    )
    if not domain_train_ids.equals(train["ID"]) or not domain_test_ids.equals(test_meta["ID"]):
        raise RuntimeError("도메인 피처 ID 순서가 원본과 다릅니다.")

    baseline_dim = x_all.shape[1]
    x_all = sparse.hstack([x_all, domain_train], format="csr", dtype=np.float32)
    x_test = sparse.hstack([x_test, domain_test], format="csr", dtype=np.float32)
    all_feature_names = [*all_feature_names, *domain_names]
    print(f"기존 {baseline_dim}열 + 신규 domain indicator {len(domain_names)}열")

    label_encoder = LabelEncoder().fit(list(CLASS_LABELS))
    if list(label_encoder.classes_) != list(CLASS_LABELS):
        raise RuntimeError("고정 클래스 순서와 LabelEncoder 순서가 다릅니다.")
    y = label_encoder.transform(train["SUBCLASS"]).astype(np.int32)

    model_params = {**config["model"], "num_class": len(CLASS_LABELS)}
    checkpoint_selection = config["training"]["checkpoint_selection"]
    n_splits = config["split"]["n_splits"]
    seed = config["seed"]

    fold_feature_builder = build_fold_features()
    oof_proba = np.full((len(train), len(CLASS_LABELS)), np.nan, dtype=np.float32)

    for fold in range(n_splits):
        valid_mask = train["fold"].eq(fold).to_numpy()
        train_indices = np.flatnonzero(~valid_mask)
        valid_indices = np.flatnonzero(valid_mask)
        y_train = y[train_indices]
        y_valid = y[valid_indices]
        x_train_fold = x_all[train_indices]
        x_valid_fold = x_all[valid_indices]

        extra = fold_feature_builder(
            fold=fold,
            train_indices=train_indices,
            valid_indices=valid_indices,
            base_train=x_train_fold,
            base_validation=x_valid_fold,
            base_test=x_test,
            base_feature_names=all_feature_names,
            target=y_train,
        )
        x_train_fold, x_valid_fold, _unused_test, _kept_names = drop_named_base_features(
            x_train_fold,
            x_valid_fold,
            x_test,
            all_feature_names,
            extra.base_feature_names_to_drop,
        )
        x_train_fold = sparse.hstack([x_train_fold, extra.train], format="csr", dtype=np.float32)
        x_valid_fold = sparse.hstack(
            [x_valid_fold, extra.validation], format="csr", dtype=np.float32
        )

        sample_weight = (
            compute_sample_weight(class_weight="balanced", y=y_train)
            if config["training"]["balanced_sample_weight"]
            else None
        )
        model = xgb.XGBClassifier(**model_params, random_state=seed + fold)
        model.fit(
            x_train_fold,
            y_train,
            sample_weight=sample_weight,
            eval_set=[(x_valid_fold, y_valid)],
            verbose=False,
        )
        checkpoint_audit = audit_xgboost_validation_iterations(
            model,
            x_valid_fold,
            y_valid,
            selection_policy=checkpoint_selection,
            rolling_window_size=config["training"].get("checkpoint_rolling_window"),
            minimum_iteration=config["training"].get("checkpoint_min_iteration"),
        )
        selected_iteration = int(checkpoint_audit["selected_checkpoint"]["iteration"])
        valid_proba = predict_xgboost_at_iteration(
            model, x_valid_fold, selected_iteration
        ).astype(np.float32)
        oof_proba[valid_indices] = valid_proba

        fold_macro_f1 = f1_score(y_valid, valid_proba.argmax(axis=1), average="macro")
        print(f"fold {fold}: macro_f1={fold_macro_f1:.10f} (iteration={selected_iteration})")

    oof_pred = oof_proba.argmax(axis=1)
    oof_macro_f1 = f1_score(y, oof_pred, average="macro")
    delta = oof_macro_f1 - EXP374_BASELINE_OOF_MACRO_F1
    print()
    print("=== EXPLORE ONLY (RUN_MODE=explore, 팀장 승인 대기, 비공식 수치) ===")
    print(f"OOF Macro F1 (EXP-374 + Pfam in-domain indicator): {oof_macro_f1:.10f}")
    print(f"EXP-374 baseline:                                  {EXP374_BASELINE_OOF_MACRO_F1:.10f}")
    print(f"delta:                                             {delta:+.10f}")


if __name__ == "__main__":
    main()
