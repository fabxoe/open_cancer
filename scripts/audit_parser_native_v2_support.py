#!/usr/bin/env python
"""Derive the frozen native-v2 activation list from the parser support audit."""

from __future__ import annotations

import json
from pathlib import Path

from open_cancer.hashing import sha256_file
from open_cancer.parser_native_v2_features import MODEL_ACTIVE_V2_CONSEQUENCES


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports/analysis/parser_v4_semantic_completeness/audit.json"
SCHEMA = ROOT / "configs/parser_v4_native_feature_schema_v2.yaml"
OUTPUT_DIR = ROOT / "reports/analysis/parser_native_v2_support"
OUTPUT = OUTPUT_DIR / "audit.json"
README = OUTPUT_DIR / "README.md"

CONSEQUENCE_SOURCE = {
    "missense": ("substitution", "missense"),
    "no_change": ("substitution", "no_change"),
    "nonsense": ("substitution", "nonsense"),
    "frameshift": ("frameshift", "frameshift"),
    "range_replacement": ("range_replacement", "range_replacement"),
}


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    rows = {
        (row["route"], row["event_type"]): row
        for row in source["support_decisions"]
    }
    active = []
    for consequence in MODEL_ACTIVE_V2_CONSEQUENCES:
        key = CONSEQUENCE_SOURCE[consequence]
        row = rows[key]
        if row["decision"] != "EXPERIMENT_ELIGIBLE":
            raise RuntimeError(f"model-active consequence failed support gate: {key}")
        active.append(
            {
                "consequence": consequence,
                "route": key[0],
                "event_type": key[1],
                "train_samples": row["train_samples"],
                "train_fold_samples": row["train_fold_samples"],
                "decision": row["decision"],
            }
        )
    qc_only = [
        row for row in source["support_decisions"]
        if row["decision"] != "EXPERIMENT_ELIGIBLE"
    ]
    document = {
        "schema_version": "1.0.0",
        "issue": 453,
        "analysis_only": True,
        "source_audit": {
            "path": str(SOURCE.relative_to(ROOT)),
            "sha256": sha256_file(SOURCE),
            "issue": 424,
        },
        "feature_schema": {
            "path": str(SCHEMA.relative_to(ROOT)),
            "sha256": sha256_file(SCHEMA),
        },
        "constraints": {
            "target_used": False,
            "test_prevalence_used_for_activation": False,
            "public_lb_used": False,
            "mutation_presence_preserved": True,
        },
        "model_active": active,
        "qc_only": qc_only,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Parser v4 native semantic adapter v2 지원 감사",
        "",
        "> Issue: [#453](https://github.com/fabxoe/open_cancer/issues/453)",
        ">",
        "> 모델 학습 없이 train과 canonical fold 지원만으로 활성 열을 고정했습니다.",
        "",
        "## 모델 활성 consequence",
        "",
        "| consequence | route:event | train sample | fold sample |",
        "|---|---|---:|---|",
    ]
    for row in active:
        lines.append(
            f"| `{row['consequence']}` | `{row['route']}:{row['event_type']}` | "
            f"{row['train_samples']:,} | `{row['train_fold_samples']}` |"
        )
    lines.extend(
        [
            "",
            "## QC-only 원칙",
            "",
            "deletion·insertion·duplication candidate·delins·range stop/no-change·",
            "start-codon·unresolved 의미는 parser에서 삭제하거나 complex로 합치지 않습니다.",
            "다만 현재 train/fold 지원 gate를 통과하지 못해 첫 v2 모델 행렬에는 넣지 않고",
            "exclusive primary family와 raw token provenance로 보존합니다.",
            "",
            "기존 mutation-presence는 항상 모델에 별도로 유지됩니다. target·test prevalence·",
            "Public LB는 이 결정에 사용하지 않았습니다.",
            "",
        ]
    )
    README.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
