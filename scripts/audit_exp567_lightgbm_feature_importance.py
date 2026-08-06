#!/usr/bin/env python
"""Audit EXP-567 LightGBM gain/split and validation family permutation importance."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics import f1_score
from sklearn.preprocessing import LabelEncoder

from exp527_lightgbm_ablation_builders import build_parser_plus_cosine_features
from open_cancer.constants import CLASS_LABELS
from open_cancer.feature_family import drop_named_base_features
from open_cancer.hashing import sha256_file, sha256_lines
from open_cancer.tree_shap_audit import feature_family


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "reports" / "analysis" / "exp567_lightgbm_cosine_importance"
SLUG = "exp567_lightgbm_parser_cosine"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=ROOT,
        help="Repository root containing EXP-567 ignored checkpoints and feature cache.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--permutation-repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def audit_family(name: str) -> str:
    """Map one final EXP-567 feature to an auditable family."""

    if "__parser_v4_class_profile_cosine__" in name:
        return "class_cosine"
    return feature_family(name)


def _scatter_block(
    block: sparse.spmatrix,
    global_columns: np.ndarray,
    shape: tuple[int, int],
) -> sparse.csr_matrix:
    coo = sparse.coo_matrix(block)
    return sparse.csr_matrix(
        (coo.data, (coo.row, global_columns[coo.col])), shape=shape
    )


def permute_sparse_family(
    matrix: sparse.spmatrix,
    columns: np.ndarray,
    permutation: np.ndarray,
) -> sparse.csr_matrix:
    """Jointly permute selected sparse columns without densifying the matrix."""

    csr = sparse.csr_matrix(matrix)
    selected = np.asarray(columns, dtype=np.int64)
    order = np.asarray(permutation, dtype=np.int64)
    if selected.ndim != 1 or selected.size == 0:
        raise ValueError("columns must be a non-empty one-dimensional array")
    if order.shape != (csr.shape[0],) or set(order.tolist()) != set(range(csr.shape[0])):
        raise ValueError("permutation must contain every row exactly once")
    original = _scatter_block(csr[:, selected], selected, csr.shape)
    shuffled = _scatter_block(csr[order][:, selected], selected, csr.shape)
    result = (csr - original + shuffled).tocsr()
    result.eliminate_zeros()
    return result


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_contract(artifact_root: Path):
    feature_dir = artifact_root / "data" / "processed" / f"{SLUG}_features"
    model_dir = artifact_root / "models" / SLUG
    required = [
        feature_dir / "train_features.npz",
        feature_dir / "test_features.npz",
        feature_dir / "feature_names.json",
        *(model_dir / f"fold_{fold:02d}.txt" for fold in range(5)),
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "EXP-567 ignored artifacts are missing; fetch or supply --artifact-root:\n"
            + "\n".join(missing)
        )
    base_train = sparse.load_npz(feature_dir / "train_features.npz").tocsr()
    base_test = sparse.load_npz(feature_dir / "test_features.npz").tocsr()
    base_names = tuple(json.loads((feature_dir / "feature_names.json").read_text()))
    if base_train.shape[1] != len(base_names) or base_test.shape[1] != len(base_names):
        raise ValueError("EXP-567 base feature matrix/name contract mismatch")
    return feature_dir, model_dir, base_train, base_test, base_names


def main() -> None:
    try:
        import lightgbm as lgb
    except ModuleNotFoundError as error:
        raise ModuleNotFoundError(
            "This audit requires the experiment dependencies. "
            "Run it with `uv run --group experiment python "
            "scripts/audit_exp567_lightgbm_feature_importance.py`."
        ) from error

    args = parse_args()
    if args.permutation_repeats < 1:
        raise ValueError("permutation-repeats must be positive")
    artifact_root = args.artifact_root.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    feature_dir, model_dir, base_train, base_test, base_names = _load_contract(
        artifact_root
    )
    train = pd.read_csv(ROOT / "data" / "raw" / "train.csv", usecols=["ID", "SUBCLASS"], dtype=str)
    split = pd.read_csv(
        ROOT / "data" / "splits" / "stratified_5fold_seed42.csv",
        dtype={"ID": str, "fold": int},
    )
    merged = train.merge(split, on="ID", how="left", validate="one_to_one", sort=False)
    if not merged["ID"].equals(train["ID"]) or merged["fold"].isna().any():
        raise ValueError("canonical split ID contract mismatch")
    encoder = LabelEncoder().fit(list(CLASS_LABELS))
    target = encoder.transform(merged["SUBCLASS"]).astype(np.int32)
    folds = merged["fold"].to_numpy(dtype=np.int32)

    builder = build_parser_plus_cosine_features()
    feature_gain: dict[str, float] = defaultdict(float)
    feature_split: dict[str, int] = defaultdict(int)
    family_permutation: dict[str, list[float]] = defaultdict(list)
    fold_records: list[dict[str, Any]] = []
    final_name_hashes: set[str] = set()

    for fold in range(5):
        valid_indices = np.flatnonzero(folds == fold)
        train_indices = np.flatnonzero(folds != fold)
        extra = builder(
            fold=fold,
            train_indices=train_indices,
            valid_indices=valid_indices,
            base_train=base_train[train_indices],
            base_validation=base_train[valid_indices],
            base_test=base_test,
            base_feature_names=base_names,
            target=target[train_indices],
        )
        _, valid_base, _, kept_names = drop_named_base_features(
            base_train[train_indices],
            base_train[valid_indices],
            base_test,
            base_names,
            extra.base_feature_names_to_drop,
            allow_empty=bool(extra.feature_names),
        )
        matrix = sparse.hstack(
            [valid_base, extra.validation], format="csr", dtype=np.float32
        )
        names = (*kept_names, *tuple(extra.feature_names))
        checkpoint = model_dir / f"fold_{fold:02d}.txt"
        booster = lgb.Booster(model_file=str(checkpoint))
        if booster.num_feature() != matrix.shape[1] or matrix.shape[1] != len(names):
            raise ValueError(
                f"fold {fold} feature contract mismatch: "
                f"model={booster.num_feature()}, matrix={matrix.shape[1]}, names={len(names)}"
            )
        final_name_hashes.add(sha256_lines(names))
        probabilities = np.asarray(booster.predict(matrix), dtype=np.float64)
        baseline = float(
            f1_score(target[valid_indices], probabilities.argmax(axis=1), average="macro")
        )

        gains = booster.feature_importance(importance_type="gain")
        splits = booster.feature_importance(importance_type="split")
        for name, gain, count in zip(names, gains, splits, strict=True):
            feature_gain[name] += float(gain)
            feature_split[name] += int(count)

        groups: dict[str, list[int]] = defaultdict(list)
        for index, name in enumerate(names):
            groups[audit_family(name)].append(index)
        fold_family: dict[str, list[float]] = {}
        for family_index, family in enumerate(sorted(groups)):
            columns = np.asarray(groups[family], dtype=np.int64)
            deltas: list[float] = []
            for repeat in range(args.permutation_repeats):
                rng = np.random.default_rng(
                    args.seed + fold * 10_000 + family_index * 100 + repeat
                )
                permuted = permute_sparse_family(
                    matrix, columns, rng.permutation(matrix.shape[0])
                )
                score = float(
                    f1_score(
                        target[valid_indices],
                        np.asarray(booster.predict(permuted)).argmax(axis=1),
                        average="macro",
                    )
                )
                deltas.append(baseline - score)
                family_permutation[family].append(baseline - score)
            fold_family[family] = deltas
        fold_records.append(
            {
                "fold": fold,
                "validation_rows": int(len(valid_indices)),
                "baseline_macro_f1": baseline,
                "feature_count": len(names),
                "feature_names_sha256": sha256_lines(names),
                "checkpoint": checkpoint.relative_to(artifact_root).as_posix(),
                "checkpoint_sha256": sha256_file(checkpoint),
                "family_permutation_delta": fold_family,
            }
        )
        print(json.dumps({"fold": fold, "baseline_macro_f1": baseline}, ensure_ascii=False))

    feature_rows = []
    total_gain = sum(feature_gain.values())
    total_split = sum(feature_split.values())
    for name in sorted(feature_gain, key=lambda value: (-feature_gain[value], value)):
        feature_rows.append(
            {
                "feature": name,
                "family": audit_family(name),
                "gain": feature_gain[name],
                "gain_share": feature_gain[name] / total_gain if total_gain else 0.0,
                "split_count": feature_split[name],
                "split_share": feature_split[name] / total_split if total_split else 0.0,
            }
        )
    family_rows = []
    for family in sorted(set(row["family"] for row in feature_rows)):
        members = [row for row in feature_rows if row["family"] == family]
        deltas = np.asarray(family_permutation[family], dtype=np.float64)
        family_rows.append(
            {
                "family": family,
                "feature_count": len(members),
                "gain": float(sum(row["gain"] for row in members)),
                "gain_share": float(sum(row["gain_share"] for row in members)),
                "split_count": int(sum(row["split_count"] for row in members)),
                "split_share": float(sum(row["split_share"] for row in members)),
                "permutation_macro_f1_delta_mean": float(deltas.mean()),
                "permutation_macro_f1_delta_std": float(deltas.std()),
                "permutation_macro_f1_delta_min": float(deltas.min()),
                "permutation_macro_f1_delta_max": float(deltas.max()),
                "permutation_evaluations": int(deltas.size),
            }
        )
    family_rows.sort(
        key=lambda row: (-row["permutation_macro_f1_delta_mean"], row["family"])
    )
    pd.DataFrame(feature_rows).to_csv(output_dir / "feature_importance.csv", index=False)
    pd.DataFrame(family_rows).to_csv(output_dir / "family_importance.csv", index=False)
    _write_json(
        output_dir / "summary.json",
        {
            "analysis_role": "validation_only_feature_importance",
            "issue_number": 576,
            "experiment": "EXP-567",
            "training_or_selection_use": False,
            "test_or_public_lb_use": False,
            "importance": {
                "supported": ["gain", "split"],
                "unsupported": ["cover"],
                "cover_note": "LightGBM Booster does not expose XGBoost-style cover importance.",
            },
            "permutation": {
                "method": "joint row permutation of every column in one feature family",
                "repeats_per_fold": args.permutation_repeats,
                "seed": args.seed,
                "positive_delta_means_family_is_useful": True,
            },
            "data": {
                "train_sha256": sha256_file(ROOT / "data" / "raw" / "train.csv"),
                "split_sha256": sha256_file(
                    ROOT / "data" / "splits" / "stratified_5fold_seed42.csv"
                ),
                "base_feature_names_sha256": sha256_lines(base_names),
                "final_feature_names_sha256": sorted(final_name_hashes),
                "artifact_root": "runtime argument; absolute local path not persisted",
                "feature_cache": feature_dir.relative_to(artifact_root).as_posix(),
            },
            "folds": fold_records,
            "family_importance": family_rows,
            "top_features": feature_rows[:100],
        },
    )


if __name__ == "__main__":
    main()
