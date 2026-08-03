#!/usr/bin/env python
"""Adversarial validation: how separable are train and test rows?

This script is a diagnostic tool, not an official model experiment. It never
reads `SUBCLASS` and never updates `EXPERIMENT_HISTORY.md`. It trains a binary
classifier to distinguish train rows (domain label 0) from test rows (domain
label 1) using the same materialized frozen Feature Spec v1 matrix production
models consume. A high out-of-fold AUC quantifies how strong the train/test
distribution shift is; per-feature gain importance localizes which engineered
features carry it. Per PROJECT_CONTEXT.md, this diagnostic alone does not
change the official Feature Spec, thresholds, or submission candidates -- a
follow-up Experiment Issue is required before any reweighted retrain result
can be adopted.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[1]


def load_ids(path: Path) -> list[str]:
    return pd.read_csv(path, usecols=["ID"], dtype=str)["ID"].tolist()


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

    oof_pred = np.zeros(x.shape[0], dtype=np.float64)
    fold_auc: list[float] = []
    gain_totals = np.zeros(len(feature_names), dtype=np.float64)

    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    for fold, (train_idx, valid_idx) in enumerate(splitter.split(x, y)):
        model = XGBClassifier(
            objective="binary:logistic",
            eval_metric="auc",
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            tree_method="hist",
            device="cpu",
            n_jobs=8,
            random_state=seed + fold,
            early_stopping_rounds=early_stopping_rounds,
            verbosity=0,
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
        booster = model.get_booster()
        for feature_index_name, gain in booster.get_score(importance_type="gain").items():
            gain_totals[int(feature_index_name[1:])] += gain

    overall_auc = float(roc_auc_score(y, oof_pred))
    mean_gain = gain_totals / n_splits
    ranking = np.argsort(-mean_gain)
    top_features = [
        {"feature": feature_names[i], "mean_gain": float(mean_gain[i])}
        for i in ranking[: min(50, len(feature_names))]
        if mean_gain[i] > 0
    ]

    n_train = train_matrix.shape[0]
    train_oof = oof_pred[:n_train]
    raw_weight = train_oof / np.clip(1.0 - train_oof, 1e-6, None)
    weight_cap = float(np.quantile(raw_weight, 0.99))
    importance_weight = np.clip(raw_weight, 0.0, weight_cap)

    return {
        "n_train": int(n_train),
        "n_test": int(test_matrix.shape[0]),
        "n_features": len(feature_names),
        "n_splits": n_splits,
        "seed": seed,
        "fold_auc": fold_auc,
        "overall_auc": overall_auc,
        "top_features": top_features,
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

- `metrics.json`: fold별/전체 OOF AUC, feature 수, 상위 shift feature
- `top_shift_features.csv`: gain 기준 train/test를 가장 잘 구분하는 feature
- `train_domain_propensity.csv`: 각 train 행이 "test처럼 보이는" OOF 확률과
  `p/(1-p)` 기반 제안 importance weight(99th percentile로 clip)

여기서 사용한 5-fold는 도메인 분류(train vs test)를 위한 별도 stratified
split이며, 공식 `data/splits/stratified_5fold_seed42.csv`(SUBCLASS 계층화)와
다르다. 두 split을 섞어 쓰지 않는다.

## 해석 순서와 제약

1. 이 결과는 진단(QC)이며 그 자체로 Feature Spec, threshold, 제출 후보를
   바꾸는 근거가 아니다. `PROJECT_CONTEXT.md`의 OOD QC 제약을 따른다.
2. AUC가 뚜렷하게 0.5보다 크면(예: 0.7 이상) 상위 shift feature가 실제로
   `reports/analysis/eda_violin`, `reports/analysis/tokenization_ood`에서 이미
   확인한 burden/complex 계열과 겹치는지 대조한다.
3. 겹친다면 `train_domain_propensity.csv`의 weight로 outer-fold train만
   재가중한 재학습을 새 Experiment Issue에서 OOF로 검증한 뒤에만 Public 제출
   여부를 판단한다. 이 진단 실행만으로 제출하지 않는다.
4. `SUBCLASS`와 Public 점수는 이 스크립트의 어떤 단계에서도 사용하지 않았다.
"""


def write_outputs(output_dir: Path, result: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = {
        key: value
        for key, value in result.items()
        if key not in {"train_ids", "train_domain_propensity", "train_importance_weight"}
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    pd.DataFrame(result["top_features"]).to_csv(output_dir / "top_shift_features.csv", index=False)
    pd.DataFrame(
        {
            "ID": result["train_ids"],
            "oof_test_domain_probability": result["train_domain_propensity"],
            "suggested_importance_weight": result["train_importance_weight"],
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
    )
    write_outputs(args.output, result)
    print(
        json.dumps(
            {
                "overall_auc": result["overall_auc"],
                "fold_auc": result["fold_auc"],
                "n_features": result["n_features"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
