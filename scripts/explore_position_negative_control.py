#!/usr/bin/env python
"""Run fold-train-only residue-position permutation negative controls."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb
import yaml
from scipy import sparse
from sklearn.metrics import accuracy_score, f1_score, log_loss
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.hashing import sha256_file
from open_cancer.mutation_features import LOG_BURDEN_FEATURES, build_mutation_features
from open_cancer.paths import relative_posix
from open_cancer.position_negative_control import permute_position_values


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "explore_position_negative_control.yaml"
TRAIN_PATH = ROOT / "data" / "raw" / "train.csv"
TEST_PATH = ROOT / "data" / "raw" / "test.csv"


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def ensure_feature_artifacts(feature_dir: Path) -> None:
    required = (
        feature_dir / "train_features.npz",
        feature_dir / "feature_names.json",
        feature_dir / "train_ids.csv",
    )
    if all(path.is_file() for path in required):
        return
    build_mutation_features(
        TRAIN_PATH,
        TEST_PATH,
        feature_dir,
        include_robust_aggregates=False,
        selected_robust_aggregates=LOG_BURDEN_FEATURES,
        selected_position_features=("max_residue_position",),
        position_missing_policy="zero",
        position_token_scope="include_complex",
        position_transform="raw",
    )


def interpretation(signal_delta: float) -> str:
    if signal_delta >= 0.002:
        return "SUPPORTED_NUMERIC_POSITION_SIGNAL"
    if abs(signal_delta) <= 0.001:
        return "NO_CLEAR_NUMERIC_POSITION_SIGNAL"
    return "INCONCLUSIVE"


def render_report(result: dict[str, Any]) -> str:
    fold_deltas = [
        fold["delta_vs_reference"]
        for run in result["runs"]
        for fold in run["folds"]
    ]
    changed_values = [
        fold["changed_values"]
        for run in result["runs"]
        for fold in run["permutation"]
    ]
    support_mismatches = sum(
        fold["support_mismatches"]
        for run in result["runs"]
        for fold in run["permutation"]
    )
    lines = [
        "# Residue-position permutation negative control",
        "",
        "> 공식 실험이나 리더보드 제출이 아닌 `RUN_MODE=explore` 분석입니다.",
        "",
        "## 질문",
        "",
        "EXP-069의 개선이 `max_residue_position` 숫자값 자체에서 나온 것인지,",
        "아니면 mutation-presence와 sparse 구조에서 나온 것인지 확인합니다.",
        "",
        "## 누수 방지 설계",
        "",
        "- 각 outer fold의 학습 행 안에서만 위치값을 섞었습니다.",
        "- validation 위치값은 원본 그대로 두고 test 데이터는 사용하지 않았습니다.",
        "- 유전자, 위치 관측 mask와 mutation-presence를 유지했습니다.",
        "- 같은 유전자 안에서도 missense·synonymous·nonsense·frameshift·complex",
        "  조합이 같은 행끼리만 위치값을 섞었습니다.",
        "- 모델 seed는 EXP-069와 동일하게 고정하고 permutation seed만 변경했습니다.",
        "",
        "## 결과",
        "",
        f"- EXP-069 원본 OOF Macro F1: `{result['reference']['oof_macro_f1']:.10f}`",
        f"- permutation 평균 OOF Macro F1: `{result['summary']['mean_oof_macro_f1']:.10f}`",
        f"- 원본 - permutation 평균: `{result['summary']['signal_delta']:+.10f}`",
        f"- 판단: `{result['summary']['interpretation']}`",
        f"- 원본보다 낮아진 fold: `{sum(delta < 0 for delta in fold_deltas)}/15`",
        f"- fold당 실제로 이동한 위치값: `{min(changed_values):,}~{max(changed_values):,}`개",
        f"- sparse support 변경: `{support_mismatches}`건",
        "",
        "| permutation seed | OOF Macro F1 | 원본 대비 | fold 표준편차 | Log Loss |",
        "|---:|---:|---:|---:|---:|",
    ]
    for run in result["runs"]:
        lines.append(
            f"| {run['permutation_seed']} | {run['oof_macro_f1']:.10f} | "
            f"{run['delta_vs_reference']:+.10f} | {run['fold_std']:.10f} | "
            f"{run['log_loss']:.10f} |"
        )
    lines.extend(
        [
            "",
            "## 해석 기준",
            "",
            "- 원본이 permutation 평균보다 `0.002` 이상 높으면 숫자 위치 신호가",
            "  있다는 근거로 봅니다.",
            "- 절대 차이가 `0.001` 이하면 숫자 위치 신호가 명확하지 않은 것으로 봅니다.",
            "- 그 사이는 결론을 보류합니다.",
            "",
            "## 다음 결정",
            "",
            result["summary"]["next_action"],
            "",
            "상세 seed·fold 결과와 입력 해시는",
            "[`position_negative_control.json`](position_negative_control.json)에 있습니다.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    started = datetime.now(timezone.utc)
    start_time = time.perf_counter()
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    if context.issue_number != config["issue_number"]:
        raise ValueError(
            f"Issue #{config['issue_number']} 브랜치에서 실행해야 합니다: "
            f"현재 {context.branch}"
        )
    if context.experiment_id is not None:
        raise ValueError("negative control explore에는 EXP-ID가 없어야 합니다.")

    feature_dir = ROOT / config["feature_dir"]
    split_path = ROOT / config["split"]["path"]
    reference_metrics_path = ROOT / config["reference_metrics"]
    ensure_feature_artifacts(feature_dir)

    train = pd.read_csv(TRAIN_PATH, usecols=["ID", "SUBCLASS"], dtype=str)
    folds = pd.read_csv(split_path, dtype={"ID": str, "fold": int})
    train = train.merge(folds, on="ID", how="left", validate="one_to_one", sort=False)
    feature_ids = pd.read_csv(feature_dir / "train_ids.csv", dtype=str)["ID"]
    if not feature_ids.equals(train["ID"]):
        raise ValueError("Feature Factory와 train ID 순서가 다릅니다.")

    matrix = sparse.load_npz(feature_dir / "train_features.npz").tocsr()
    feature_names = json.loads(
        (feature_dir / "feature_names.json").read_text(encoding="utf-8")
    )
    encoder = LabelEncoder().fit(list(CLASS_LABELS))
    if list(encoder.classes_) != list(CLASS_LABELS):
        raise ValueError("고정 클래스 순서와 LabelEncoder 순서가 다릅니다.")
    labels = encoder.transform(train["SUBCLASS"]).astype(np.int32)

    reference_metrics = json.loads(reference_metrics_path.read_text(encoding="utf-8"))
    reference_score = float(reference_metrics["oof"]["macro_f1"])
    reference_fold_scores = {
        int(item["fold"]): float(item["macro_f1"])
        for item in reference_metrics["folds"]
    }
    model_params = {**config["model"], "num_class": len(CLASS_LABELS)}
    runs: list[dict[str, Any]] = []
    oof_dir = ROOT / "oof" / "explore_position_negative_control"
    oof_dir.mkdir(parents=True, exist_ok=True)

    for permutation_seed in config["position"]["permutation_seeds"]:
        oof = np.full((len(train), len(CLASS_LABELS)), np.nan, dtype=np.float32)
        fold_results: list[dict[str, Any]] = []
        permutation_reports: list[dict[str, Any]] = []
        for fold in range(config["split"]["n_splits"]):
            valid_mask = train["fold"].eq(fold).to_numpy()
            train_indices = np.flatnonzero(~valid_mask)
            valid_indices = np.flatnonzero(valid_mask)
            x_train, permutation_report = permute_position_values(
                matrix[train_indices],
                feature_names,
                position_feature=config["position"]["feature"],
                seed=int(permutation_seed) + fold * 10_000,
                strata_suffixes=config["position"]["strata_suffixes"],
            )
            x_valid = matrix[valid_indices]
            y_train = labels[train_indices]
            y_valid = labels[valid_indices]
            weights = (
                compute_sample_weight(class_weight="balanced", y=y_train)
                if config["training"]["balanced_sample_weight"]
                else None
            )
            model = xgb.XGBClassifier(
                **model_params,
                random_state=42 + fold,
            )
            model.fit(
                x_train,
                y_train,
                sample_weight=weights,
                eval_set=[(x_valid, y_valid)],
                verbose=False,
            )
            probabilities = model.predict_proba(x_valid).astype(np.float32)
            oof[valid_indices] = probabilities
            score = float(
                f1_score(y_valid, probabilities.argmax(axis=1), average="macro")
            )
            fold_result = {
                "fold": fold,
                "macro_f1": score,
                "reference_macro_f1": reference_fold_scores[fold],
                "delta_vs_reference": score - reference_fold_scores[fold],
                "best_iteration": int(model.best_iteration),
            }
            fold_results.append(fold_result)
            permutation_reports.append({"fold": fold, **permutation_report})
            print(json.dumps({"seed": permutation_seed, **fold_result}, ensure_ascii=False))

        predictions = oof.argmax(axis=1)
        score = float(f1_score(labels, predictions, average="macro"))
        fold_scores = np.asarray([item["macro_f1"] for item in fold_results])
        oof_frame = pd.DataFrame(
            {
                "ID": train["ID"],
                "SUBCLASS_TRUE": train["SUBCLASS"],
                "SUBCLASS_PRED": encoder.inverse_transform(predictions),
                "FOLD": train["fold"].astype(int),
            }
        )
        oof_frame.loc[:, list(PROBABILITY_COLUMNS)] = oof
        oof_path = oof_dir / f"seed_{permutation_seed}.csv"
        oof_frame.to_csv(oof_path, index=False, lineterminator="\n")
        runs.append(
            {
                "permutation_seed": int(permutation_seed),
                "oof_macro_f1": score,
                "delta_vs_reference": score - reference_score,
                "fold_mean": float(fold_scores.mean()),
                "fold_std": float(fold_scores.std()),
                "accuracy": float(accuracy_score(labels, predictions)),
                "log_loss": float(
                    log_loss(labels, oof, labels=np.arange(len(CLASS_LABELS)))
                ),
                "folds": fold_results,
                "permutation": permutation_reports,
                "oof_path": relative_posix(oof_path, ROOT),
                "oof_sha256": sha256_file(oof_path),
            }
        )

    scores = np.asarray([run["oof_macro_f1"] for run in runs])
    mean_score = float(scores.mean())
    signal_delta = reference_score - mean_score
    decision = interpretation(signal_delta)
    next_actions = {
        "SUPPORTED_NUMERIC_POSITION_SIGNAL": (
            "EXP-069의 `max+zero`를 Position Feature Spec v1에 포함하고 단계 F 조합 실험으로 진행합니다."
        ),
        "NO_CLEAR_NUMERIC_POSITION_SIGNAL": (
            "위치 피처는 Feature Spec v1 조합에서 제외하고 독립 앙상블 후보로만 유지합니다."
        ),
        "INCONCLUSIVE": (
            "위치 피처를 동결하되 Feature Spec v1 포함 여부를 보류하고 추가 위치 옵션 탐색은 하지 않습니다."
        ),
    }
    result = {
        "analysis": "residue_position_permutation_negative_control",
        "run_mode": "explore",
        "issue_number": context.issue_number,
        "branch": context.branch,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "runtime_seconds": float(time.perf_counter() - start_time),
        "target_used_for_permutation": False,
        "test_data_used": False,
        "validation_positions_permuted": False,
        "reference": {
            "experiment_id": config["reference_experiment"],
            "metrics_path": config["reference_metrics"],
            "metrics_sha256": sha256_file(reference_metrics_path),
            "oof_macro_f1": reference_score,
        },
        "inputs": {
            "train_sha256": sha256_file(TRAIN_PATH),
            "split_sha256": sha256_file(split_path),
            "feature_names_sha256": sha256_file(feature_dir / "feature_names.json"),
            "train_features_sha256": sha256_file(feature_dir / "train_features.npz"),
        },
        "runs": runs,
        "summary": {
            "mean_oof_macro_f1": mean_score,
            "std_across_permutation_seeds": float(scores.std()),
            "signal_delta": signal_delta,
            "interpretation": decision,
            "next_action": next_actions[decision],
        },
    }
    metrics_path = ROOT / config["output"]["metrics"]
    report_path = ROOT / config["output"]["report"]
    write_json(metrics_path, result)
    report_path.write_text(render_report(result), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
