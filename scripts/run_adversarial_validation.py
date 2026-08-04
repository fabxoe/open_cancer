#!/usr/bin/env python
"""Adversarial validation: how separable are train and test rows?

This script is a diagnostic tool, not an official model experiment. It never
reads `SUBCLASS` and never updates `EXPERIMENT_HISTORY.md`. It trains binary
classifiers to distinguish train rows (domain label 0) from test rows (domain
label 1) using the same materialized frozen Feature Spec v1 matrix production
models consume. A high out-of-fold AUC quantifies how strong the train/test
distribution shift is.

Beyond the single combined-feature baseline, this also answers the
family-level questions requested on PR #293: standalone AUC per engineering
family, leave-one-family-out AUC, a residue-position ablation, and a
train/test distribution table for the top shift features. All of this is QC
only -- it never removes an official feature, picks a threshold, or is used
as a training sample weight. Issue #294 tried reusing the domain-propensity
output as a training sample weight and was rejected by team review (PR #303)
for injecting test feature distribution into training preprocessing; nothing
in this script feeds back into any official experiment config.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from xgboost import XGBClassifier

from open_cancer.hashing import sha256_file, sha256_lines

ROOT = Path(__file__).resolve().parents[1]

# Coarse families requested on PR #293. "missing" (per-gene empty-cell
# indicators) is intentionally not one of these five -- it stays inside every
# "rest of the spec" pool below but is not itself evaluated standalone.
FAMILY_RULES: dict[str, Callable[[str], bool]] = {
    "raw_mutation_presence": lambda name: name.endswith("__mutated"),
    "gene_mutation_type_indicators": lambda name: name.rsplit("__", 1)[-1]
    in {"missense", "synonymous", "nonsense", "frameshift", "complex"},
    "sample_aggregate_burden": lambda name: name.startswith("sample__"),
    "residue_position": lambda name: name.endswith("__max_residue_position"),
    "fixed_hotspot": lambda name: name.startswith("hotspot__"),
}

MODEL_PARAMS = {
    "objective": "binary:logistic",
    "eval_metric": "auc",
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
    "tree_method": "hist",
    "device": "cpu",
    "n_jobs": 8,
    "verbosity": 0,
}


def load_ids(path: Path) -> list[str]:
    return pd.read_csv(path, usecols=["ID"], dtype=str)["ID"].tolist()


def classify_feature_family(name: str) -> str:
    """Group a Feature Spec v1 column name into its fine-grained family.

    Per-gene columns share a "__" suffix (e.g. "TP53__missense"); the suffix
    alone is the family, since gene identity is not the shift signal we want
    to aggregate over. "sample__*" and "hotspot__*" are already family-level
    aggregates, so the prefix is the family.
    """
    if name.startswith("sample__"):
        return "sample_burden_aggregate"
    if name.startswith("hotspot__"):
        return "hotspot"
    if "__" in name:
        return name.split("__", 1)[1]
    return "other"


def classify_distribution_kind(name: str) -> str:
    """"presence" columns are mostly-zero indicator/count columns best summarized
    by nonzero prevalence; "continuous" columns get a full quantile table."""
    if name.startswith("sample__") or name.endswith("__max_residue_position"):
        return "continuous"
    return "presence"


def fit_domain_auc(
    x_full: sparse.csr_matrix,
    y: np.ndarray,
    column_indices: np.ndarray | None,
    fold_splits: list[tuple[np.ndarray, np.ndarray]],
    seed: int,
    n_estimators: int,
    max_depth: int,
    learning_rate: float,
    early_stopping_rounds: int,
    compute_gain: bool,
) -> tuple[dict, np.ndarray]:
    x = x_full if column_indices is None else x_full[:, column_indices]
    n_features = x.shape[1]
    oof_pred = np.zeros(x.shape[0], dtype=np.float64)
    fold_auc: list[float] = []
    gain_totals = np.zeros(n_features, dtype=np.float64) if compute_gain else None
    for fold, (train_idx, valid_idx) in enumerate(fold_splits):
        model = XGBClassifier(
            **MODEL_PARAMS,
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            random_state=seed + fold,
            early_stopping_rounds=early_stopping_rounds,
        )
        model.fit(
            x[train_idx],
            y[train_idx],
            eval_set=[(x[valid_idx], y[valid_idx])],
            verbose=False,
        )
        fold_pred = model.predict_proba(x[valid_idx])[:, 1]
        oof_pred[valid_idx] = fold_pred
        fold_auc.append(float(roc_auc_score(y[valid_idx], fold_pred)))
        if compute_gain:
            booster = model.get_booster()
            for feature_index_name, gain in booster.get_score(importance_type="gain").items():
                gain_totals[int(feature_index_name[1:])] += gain
    overall_auc = float(roc_auc_score(y, oof_pred))
    result: dict = {"n_features": int(n_features), "fold_auc": fold_auc, "overall_auc": overall_auc}
    if compute_gain:
        result["mean_gain"] = (gain_totals / len(fold_splits)).tolist()
    return result, oof_pred


def top_features_from_gain(mean_gain: list[float], names: list[str], top_n: int = 50) -> list[dict]:
    gain_array = np.asarray(mean_gain, dtype=np.float64)
    ranking = np.argsort(-gain_array)
    return [
        {"feature": names[i], "mean_gain": float(gain_array[i])}
        for i in ranking[: min(top_n, len(names))]
        if gain_array[i] > 0
    ]


def compute_feature_distribution(
    name: str,
    train_col: np.ndarray,
    test_col: np.ndarray,
) -> dict:
    kind = classify_distribution_kind(name)
    n_train = len(train_col)
    n_test = len(test_col)
    train_nonzero = int(np.count_nonzero(train_col))
    test_nonzero = int(np.count_nonzero(test_col))
    train_prevalence = train_nonzero / n_train
    test_prevalence = test_nonzero / n_test
    row = {
        "feature": name,
        "family": classify_feature_family(name),
        "kind": kind,
        "train_nonzero": train_nonzero,
        "test_nonzero": test_nonzero,
        "train_prevalence": train_prevalence,
        "test_prevalence": test_prevalence,
        "prevalence_abs_diff": test_prevalence - train_prevalence,
        "prevalence_relative_ratio": (
            test_prevalence / train_prevalence if train_prevalence > 0 else float("nan")
        ),
        "train_zero_ratio": 1.0 - train_prevalence,
        "test_zero_ratio": 1.0 - test_prevalence,
    }
    if kind == "continuous":
        quantiles = (0, 25, 50, 75, 90, 95, 99, 100)
        labels = ("min", "p25", "median", "p75", "p90", "p95", "p99", "max")
        for label, q in zip(labels, quantiles):
            row[f"train_{label}"] = float(np.percentile(train_col, q))
            row[f"test_{label}"] = float(np.percentile(test_col, q))
    return row


def run_adversarial_validation(
    feature_dir: Path,
    train_path: Path,
    test_path: Path,
    n_splits: int,
    seed: int,
    n_estimators: int,
    max_depth: int,
    learning_rate: float,
    early_stopping_rounds: int,
    top_n: int,
) -> dict:
    train_matrix = sparse.load_npz(feature_dir / "train_features.npz").tocsr()
    test_matrix = sparse.load_npz(feature_dir / "test_features.npz").tocsr()
    feature_names = json.loads((feature_dir / "feature_names.json").read_text(encoding="utf-8"))
    if train_matrix.shape[1] != len(feature_names) or test_matrix.shape[1] != len(feature_names):
        raise ValueError("feature_names 길이가 materialize된 행렬 열 수와 다릅니다.")

    train_ids = load_ids(train_path)
    test_ids = load_ids(test_path)
    if len(train_ids) != train_matrix.shape[0] or len(test_ids) != test_matrix.shape[0]:
        raise ValueError("ID 개수가 materialize된 행렬 행 수와 다릅니다.")

    x = sparse.vstack([train_matrix, test_matrix], format="csr")
    y = np.concatenate(
        [np.zeros(train_matrix.shape[0]), np.ones(test_matrix.shape[0])]
    ).astype(np.int32)

    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    fold_splits = list(splitter.split(x, y))

    fit_kwargs = dict(
        x_full=x,
        y=y,
        fold_splits=fold_splits,
        seed=seed,
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        early_stopping_rounds=early_stopping_rounds,
    )

    print(json.dumps({"stage": "baseline_full_spec", "n_features": len(feature_names)}))
    baseline_result, baseline_oof = fit_domain_auc(
        column_indices=None, compute_gain=True, **fit_kwargs
    )
    top_features = top_features_from_gain(baseline_result["mean_gain"], feature_names, top_n)

    families = [classify_feature_family(name) for name in feature_names]
    family_gain: dict[str, float] = {}
    family_count: dict[str, int] = {}
    for family, gain in zip(families, baseline_result["mean_gain"]):
        family_gain[family] = family_gain.get(family, 0.0) + float(gain)
        family_count[family] = family_count.get(family, 0) + 1
    total_gain = float(sum(baseline_result["mean_gain"]))
    family_shift = sorted(
        (
            {
                "family": family,
                "n_features": family_count[family],
                "total_gain": family_gain[family],
                "mean_gain_per_feature": family_gain[family] / family_count[family],
                "share_of_total_gain": (
                    family_gain[family] / total_gain if total_gain > 0 else 0.0
                ),
            }
            for family in family_gain
        ),
        key=lambda row: -row["total_gain"],
    )

    all_indices = np.arange(len(feature_names))
    family_indices_map = {
        family: all_indices[[bool(rule(name)) for name in feature_names]]
        for family, rule in FAMILY_RULES.items()
    }
    family_column_mapping = {
        family: [feature_names[i] for i in idx.tolist()] for family, idx in family_indices_map.items()
    }

    family_auc: dict[str, dict] = {}
    residue_lofo_result: dict | None = None
    residue_rest_names: list[str] | None = None
    for family, idx in family_indices_map.items():
        print(json.dumps({"stage": "family_standalone", "family": family, "n_features": int(len(idx))}))
        standalone_result, _ = fit_domain_auc(column_indices=idx, compute_gain=False, **fit_kwargs)
        rest_idx = np.setdiff1d(all_indices, idx, assume_unique=True)
        is_residue = family == "residue_position"
        print(
            json.dumps(
                {"stage": "family_leave_one_out", "family": family, "n_features": int(len(rest_idx))}
            )
        )
        lofo_result, _ = fit_domain_auc(column_indices=rest_idx, compute_gain=is_residue, **fit_kwargs)
        family_auc[family] = {
            "n_features": int(len(idx)),
            "feature_name_sha256": sha256_lines(sorted(feature_names[i] for i in idx.tolist())),
            "standalone": {
                "fold_auc": standalone_result["fold_auc"],
                "overall_auc": standalone_result["overall_auc"],
            },
            "leave_one_out": {
                "fold_auc": lofo_result["fold_auc"],
                "overall_auc": lofo_result["overall_auc"],
                "delta_from_full_auc": baseline_result["overall_auc"] - lofo_result["overall_auc"],
            },
        }
        if is_residue:
            residue_lofo_result = lofo_result
            residue_rest_names = [feature_names[i] for i in rest_idx.tolist()]

    assert residue_lofo_result is not None and residue_rest_names is not None
    residue_ablation = {
        "full_spec": {
            "n_features": len(feature_names),
            "overall_auc": baseline_result["overall_auc"],
            "fold_auc": baseline_result["fold_auc"],
        },
        "without_residue_position": {
            "n_features": residue_lofo_result["n_features"],
            "overall_auc": residue_lofo_result["overall_auc"],
            "fold_auc": residue_lofo_result["fold_auc"],
        },
        "auc_delta": baseline_result["overall_auc"] - residue_lofo_result["overall_auc"],
        "fold_auc_delta": [
            full - lofo
            for full, lofo in zip(baseline_result["fold_auc"], residue_lofo_result["fold_auc"])
        ],
        "top_shift_features_full_spec": top_features,
        "top_shift_features_without_residue_position": top_features_from_gain(
            residue_lofo_result["mean_gain"], residue_rest_names, top_n
        ),
        "note": (
            "OOD 원인 진단 전용. residue-position 제외로 AUC가 떨어져도 "
            "공식 모델에서 이 family를 바로 제거하는 근거로 쓰지 않는다."
        ),
    }

    n_train = train_matrix.shape[0]
    top_distributions = []
    for entry in top_features:
        name = entry["feature"]
        col_index = feature_names.index(name)
        train_col = np.asarray(train_matrix[:, col_index].todense()).ravel()
        test_col = np.asarray(test_matrix[:, col_index].todense()).ravel()
        top_distributions.append(compute_feature_distribution(name, train_col, test_col))

    train_oof = baseline_oof[:n_train]
    raw_weight = train_oof / np.clip(1.0 - train_oof, 1e-6, None)
    weight_cap = float(np.quantile(raw_weight, 0.99))
    importance_weight = np.clip(raw_weight, 0.0, weight_cap)

    return {
        "input_artifacts": {
            "train_features_sha256": sha256_file(feature_dir / "train_features.npz"),
            "test_features_sha256": sha256_file(feature_dir / "test_features.npz"),
            "feature_names_sha256": sha256_file(feature_dir / "feature_names.json"),
            "ordered_feature_names_sha256": sha256_lines(feature_names),
            "train_csv_sha256": sha256_file(train_path),
            "test_csv_sha256": sha256_file(test_path),
        },
        "model_configuration": {
            **MODEL_PARAMS,
            "n_estimators": n_estimators,
            "max_depth": max_depth,
            "learning_rate": learning_rate,
            "early_stopping_rounds": early_stopping_rounds,
        },
        "domain_split": {
            "method": "StratifiedKFold",
            "target": "train=0,test=1",
            "shuffle": True,
            "n_splits": n_splits,
            "seed": seed,
            "subclass_used": False,
            "public_score_used": False,
        },
        "n_train": int(n_train),
        "n_test": int(test_matrix.shape[0]),
        "n_features": len(feature_names),
        "n_splits": n_splits,
        "seed": seed,
        "fold_auc": baseline_result["fold_auc"],
        "overall_auc": baseline_result["overall_auc"],
        "total_gain": total_gain,
        "top_features": top_features,
        "family_shift": family_shift,
        "family_auc": family_auc,
        "family_column_mapping": family_column_mapping,
        "residue_ablation": residue_ablation,
        "top_shift_distributions": top_distributions,
        "train_ids": train_ids,
        "train_domain_propensity": train_oof.tolist(),
        "train_importance_weight": importance_weight.tolist(),
    }


README_TEXT = """# Adversarial validation: train/test 분리 가능성

이 진단은 `SUBCLASS`를 전혀 사용하지 않고, 동결 Feature Spec v1 행렬만으로
train 행(도메인 라벨 0)과 test 행(도메인 라벨 1)을 구분하는 이진 분류기를
학습한다. OOF AUC가 0.5에 가까우면 이 feature 표현에서 두 도메인이 구분
불가능하다는 뜻이고, 1.0에 가까우면 강한 분포 차이(batch effect 후보)가
있다는 뜻이다.

**`analysis_only: true`** — 이 디렉토리의 모든 산출물은 QC·원인 분석
전용이며, 공식 Feature Spec·threshold·제출 후보를 정하는 근거로 쓰지 않는다.

## 산출물

- `metrics.json`: fold별/전체 OOF AUC(전체 Feature Spec v1 기준), feature 수
- `top_shift_features.csv`: gain 기준 train/test를 가장 잘 구분하는 개별 feature
- `family_shift.csv`: 전체 Feature Spec v1 하나의 모델 안에서, family별로
  gain을 합산한 결과(빠른 스크리닝용)
- `family_auc.json`: family별 **standalone AUC**(그 family만 입력으로 사용)와
  **leave-one-family-out AUC**(전체에서 그 family만 제외) — 동일 domain
  split·seed·모델 조건. standalone은 family 자체의 분리력을,
  leave-one-out은 다른 family를 조건으로 한 추가 기여를 보여준다.
- `family_column_mapping.json`: family → 실제 포함된 feature 이름 목록과
  `feature_name_sha256`(감사용)
- `residue_ablation.json`: 전체 Feature Spec v1 AUC vs residue-position 전체
  제외 AUC, fold별 차이, 제외 전후 상위 shift feature 구성 변화
- `top_shift_distributions.csv`: 상위 feature(기본 50개)의 train/test 분포 —
  presence류(mutation-presence/type/hotspot)는 nonzero 수·prevalence·차이,
  continuous류(sample 집계·residue-position)는 min/p25/median/p75/p90/p95/p99/max
- `train_domain_propensity.csv`: 각 train 행의 "test처럼 보이는" OOF 확률과
  `p/(1-p)` 기반 제안 importance weight(99th percentile로 clip) — 참고용으로만
  보존하며 학습 가중치로 재사용하지 않는다.

여기서 사용한 5-fold는 도메인 분류(train vs test)를 위한 별도 stratified
split이며, 공식 `data/splits/stratified_5fold_seed42.csv`(SUBCLASS 계층화)와
다르다. 두 split을 섞어 쓰지 않는다. `gene_mutation_type_indicators` family는
missense/synonymous/nonsense/frameshift/complex 5종만 포함하며, 같은 코드
경로에서 만들어지는 `missing`(결측 지시자) 열은 이 5개 family 밖에 남아
모든 leave-one-out의 "나머지"에는 포함되지만 별도 family로 단독 평가하지
않는다.

## 해석 순서와 제약

1. 이 결과는 진단(QC)이며 그 자체로 Feature Spec, threshold, 제출 후보를
   바꾸는 근거가 아니다. `PROJECT_CONTEXT.md`의 OOD QC 제약을 따른다.
2. `family_auc.json`의 standalone/leave-one-out과 `family_shift.csv`를 함께
   보고, 어느 family가 shift를 지배하는지 확인한 뒤 `reports/analysis/eda_violin`,
   `reports/analysis/tokenization_ood`에서 이미 확인한 burden/complex 계열과
   겹치는지 대조한다.
3. **`train_domain_propensity.csv`(test feature 분포에서 유도한 weight)를
   학습 sample weight로 재사용하지 않는다.** Issue #294에서 이 방식을
   시도했으나 test feature 분포 정보가 학습 전처리에 직접 들어가
   `PROJECT_CONTEXT.md`의 "test/validation 분포 정보를 학습 전처리에 사용하지
   않는다" 계약과 충돌한다는 팀장 검토로 기각됐다(PR #303 참고).
4. `residue_ablation.json`은 residue-position family가 shift에 얼마나
   기여하는지 보여주는 원인 진단이며, 이 결과만으로 공식 모델에서 해당
   family를 제거하지 않는다.
5. 어느 family를 실제로 검증하려면, **test 데이터를 전혀 참조하지 않는**
   train-only ablation(그 family를 Feature Spec에서 제외하고 기존 canonical
   5-fold로 재학습해 OOF·fold-std 변화만 확인)을 새 Experiment Issue에서
   수행한다.
6. `SUBCLASS`와 Public 점수는 이 스크립트의 어떤 단계에서도 사용하지 않았다.
"""


def write_outputs(output_dir: Path, result: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    excluded = {
        "train_ids",
        "train_domain_propensity",
        "train_importance_weight",
        "family_column_mapping",
        "top_shift_distributions",
        "residue_ablation",
        "family_auc",
    }
    metrics = {key: value for key, value in result.items() if key not in excluded}
    metrics["analysis_only"] = True
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    pd.DataFrame(result["top_features"]).to_csv(output_dir / "top_shift_features.csv", index=False)
    pd.DataFrame(result["family_shift"]).to_csv(output_dir / "family_shift.csv", index=False)
    (output_dir / "family_auc.json").write_text(
        json.dumps(
            {"analysis_only": True, "families": result["family_auc"]},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "family_column_mapping.json").write_text(
        json.dumps(
            {
                "analysis_only": True,
                "families": {
                    family: {
                        "n_features": info["n_features"],
                        "feature_name_sha256": info["feature_name_sha256"],
                        "features": result["family_column_mapping"][family],
                    }
                    for family, info in result["family_auc"].items()
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "residue_ablation.json").write_text(
        json.dumps(
            {"analysis_only": True, **result["residue_ablation"]},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    pd.DataFrame(result["top_shift_distributions"]).to_csv(
        output_dir / "top_shift_distributions.csv", index=False
    )
    pd.DataFrame(
        {
            "ID": result["train_ids"],
            "oof_test_domain_probability": result["train_domain_propensity"],
            "suggested_importance_weight": result["train_importance_weight"],
            "analysis_only": True,
        }
    ).to_csv(output_dir / "train_domain_propensity.csv", index=False)
    (output_dir / "README.md").write_text(README_TEXT, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-dir", type=Path, required=True)
    parser.add_argument("--train-path", type=Path, default=ROOT / "data" / "raw" / "train.csv")
    parser.add_argument("--test-path", type=Path, default=ROOT / "data" / "raw" / "test.csv")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports" / "analysis" / "adversarial_validation",
    )
    parser.add_argument("--n-splits", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n-estimators", type=int, default=300)
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--early-stopping-rounds", type=int, default=30)
    parser.add_argument("--top-n", type=int, default=50)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_adversarial_validation(
        feature_dir=args.feature_dir,
        train_path=args.train_path,
        test_path=args.test_path,
        n_splits=args.n_splits,
        seed=args.seed,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
        learning_rate=args.learning_rate,
        early_stopping_rounds=args.early_stopping_rounds,
        top_n=args.top_n,
    )
    write_outputs(args.output, result)
    print(
        json.dumps(
            {
                "overall_auc": result["overall_auc"],
                "fold_auc": result["fold_auc"],
                "n_features": result["n_features"],
                "family_auc_overall": {
                    family: {
                        "standalone": info["standalone"]["overall_auc"],
                        "leave_one_out": info["leave_one_out"]["overall_auc"],
                    }
                    for family, info in result["family_auc"].items()
                },
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
