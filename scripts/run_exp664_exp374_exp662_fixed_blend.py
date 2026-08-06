#!/usr/bin/env python
"""Run EXP-664 fixed blend and its pre-registered generalization gates."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import f1_score

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
import run_exp135_fixed_probability_blend as runner


runner.CONFIG_PATH = runner.ROOT / "configs/exp664_exp374_exp662_fixed_blend.yaml"
runner.ISSUE = 664
runner.EXP_ID = "EXP-664"
runner.SLUG = "exp664_exp374_exp662_fixed_blend"
runner.EXPECTED_COMPONENTS = ("EXP-374", "EXP-662")
runner.EXPECTED_WEIGHTS = (0.5, 0.5)
runner.PARENT_EXPERIMENT = "EXP-662"
runner.RUNNER_COMMAND = "uv run python scripts/run_exp664_exp374_exp662_fixed_blend.py"
runner.RUNNER_NOTES = (
    "Inference-only fixed 0.5/0.5 probability mean of Public-validated legacy "
    "EXP-374 and independently parsed calibrated hierarchical TF-IDF EXP-662. "
    "The weight was fixed before evaluation and is not adjusted after gates."
)


ROOT = runner.ROOT
SLUG = runner.SLUG


def _write_json(path: Path, document: dict) -> None:
    path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _predictions(frame: pd.DataFrame) -> np.ndarray:
    probability = frame.loc[:, list(PROBABILITY_COLUMNS)].to_numpy(dtype=float)
    return np.asarray(CLASS_LABELS)[probability.argmax(axis=1)]


def write_gate_report() -> None:
    config = yaml.safe_load(runner.CONFIG_PATH.read_text(encoding="utf-8"))
    acceptance = config["acceptance"]
    report_dir = ROOT / "reports" / SLUG
    blend_metrics = json.loads((report_dir / "metrics.json").read_text(encoding="utf-8"))
    parent_metrics = json.loads(
        (ROOT / "reports/exp662_hierarchical_tfidf_svc_sigmoid/metrics.json").read_text(encoding="utf-8")
    )
    exp374 = pd.read_csv(ROOT / config["ensemble"]["components"][0]["oof_probability_path"])
    exp662 = pd.read_csv(ROOT / config["ensemble"]["components"][1]["oof_probability_path"])
    blend = pd.read_csv(ROOT / "oof" / f"{SLUG}.csv")
    if not exp374["ID"].equals(exp662["ID"]) or not exp662["ID"].equals(blend["ID"]):
        raise ValueError("parent/blend OOF ID order mismatch")
    true = blend["SUBCLASS_TRUE"].to_numpy()
    pred374 = _predictions(exp374)
    pred662 = _predictions(exp662)
    pred_blend = _predictions(blend)

    propensity = pd.read_csv(ROOT / acceptance["test_like_propensity_path"])
    aligned = blend[["ID"]].merge(
        propensity[["ID", "oof_test_domain_probability"]], on="ID", how="left", validate="one_to_one"
    )
    if aligned["oof_test_domain_probability"].isna().any():
        raise ValueError("test-like propensity ID coverage mismatch")
    threshold = float(aligned["oof_test_domain_probability"].quantile(acceptance["test_like_quantile"]))
    test_like = aligned["oof_test_domain_probability"].ge(threshold).to_numpy()
    parent_test_like_f1 = float(
        f1_score(true[test_like], pred662[test_like], labels=CLASS_LABELS, average="macro", zero_division=0)
    )
    blend_test_like_f1 = float(
        f1_score(true[test_like], pred_blend[test_like], labels=CLASS_LABELS, average="macro", zero_division=0)
    )
    per_class_delta = {
        label: float(blend_metrics["oof"]["per_class_f1"][label] - parent_metrics["oof"]["per_class_f1"][label])
        for label in CLASS_LABELS
    }
    fold_std_delta = float(blend_metrics["oof"]["fold_std"] - parent_metrics["oof"]["fold_std"])
    macro_delta = float(blend_metrics["oof"]["macro_f1"] - parent_metrics["oof"]["macro_f1"])
    log_loss_delta = float(blend_metrics["oof"]["log_loss"] - parent_metrics["oof"]["log_loss"])
    test_like_delta = blend_test_like_f1 - parent_test_like_f1
    gates = {
        "macro_f1_non_degradation": macro_delta >= acceptance["minimum_macro_f1_delta"],
        "log_loss_non_degradation": log_loss_delta <= acceptance["maximum_log_loss_delta"],
        "test_like_macro_f1_non_degradation": test_like_delta
        >= acceptance["minimum_test_like_macro_f1_delta"],
        "fold_std_regression_limit": fold_std_delta <= acceptance["maximum_fold_std_delta"],
        "per_class_regression_limit": min(per_class_delta.values())
        >= -acceptance["maximum_per_class_regression"],
    }
    correct374 = pred374 == true
    correct662 = pred662 == true
    correctness_pearson = float(np.corrcoef(correct374.astype(float), correct662.astype(float))[0, 1])
    gate_report = {
        "experiment_id": "EXP-664",
        "comparison_experiment": "EXP-662",
        "weights": {"EXP-374": 0.5, "EXP-662": 0.5},
        "parent_diversity": {
            "label_disagreement": float(np.mean(pred374 != pred662)),
            "correctness_pearson": correctness_pearson,
            "exp374_only_correct": float(np.mean(correct374 & ~correct662)),
            "exp662_only_correct": float(np.mean(correct662 & ~correct374)),
        },
        "macro_f1_delta": macro_delta,
        "log_loss_delta": log_loss_delta,
        "fold_std_delta": fold_std_delta,
        "minimum_per_class_f1_delta": min(per_class_delta.values()),
        "per_class_f1_delta": per_class_delta,
        "test_like": {
            "propensity_quantile": acceptance["test_like_quantile"],
            "threshold": threshold,
            "rows": int(test_like.sum()),
            "parent_macro_f1": parent_test_like_f1,
            "blend_macro_f1": blend_test_like_f1,
            "delta": test_like_delta,
        },
        "gate_results": gates,
        "passed": all(gates.values()),
    }
    _write_json(report_dir / "gate_report.json", gate_report)
    decision = "ADOPT_WITHOUT_PUBLIC_SUBMISSION" if gate_report["passed"] else "ARCHIVE_GATE_FAILED"
    readme = [
        "# EXP-664 EXP-374 + EXP-662 fixed 0.5/0.5 blend",
        "",
        "Public-validated legacy parser EXP-374와 독립 hierarchical TF-IDF EXP-662의 확률을",
        "평가 전에 고정한 0.5/0.5 비율로 평균했다. 비율 탐색이나 사후 보정은 하지 않았다.",
        "",
        f"- OOF Macro F1: `{blend_metrics['oof']['macro_f1']:.10f}` (EXP-662 대비 `{macro_delta:+.10f}`)",
        f"- OOF Log Loss: `{blend_metrics['oof']['log_loss']:.10f}` (EXP-662 대비 `{log_loss_delta:+.10f}`)",
        f"- Fold std: `{blend_metrics['oof']['fold_std']:.10f}` (EXP-662 대비 `{fold_std_delta:+.10f}`)",
        f"- Test-like Macro F1: `{blend_test_like_f1:.10f}` (EXP-662 대비 `{test_like_delta:+.10f}`)",
        f"- Parent label disagreement: `{gate_report['parent_diversity']['label_disagreement']:.10f}`",
        f"- Parent correctness Pearson: `{correctness_pearson:.10f}`",
        f"- 최소 class F1 delta: `{min(per_class_delta.values()):+.10f}`",
        f"- 공동 게이트: `{'PASS' if gate_report['passed'] else 'FAIL'}`",
        f"- 판단: `{decision}`",
        "- Public LB: 미제출(Issue 범위 밖)",
        "- 재현 상태: `INFERENCE_VERIFIED`",
        "",
        "## 게이트",
        "",
        *[f"- {name}: `{value}`" for name, value in gates.items()],
    ]
    (report_dir / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")


if __name__ == "__main__":
    runner.main()
    write_gate_report()
