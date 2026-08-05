#!/usr/bin/env python
"""Audit parser-v4 semantic coverage before native model integration."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from open_cancer.hashing import sha256_file
from open_cancer.mutation_parser_contract import build_parser_contract
from open_cancer.parser_semantic_completeness import (
    PARSER_SEMANTIC_AUDIT_VERSION,
    SemanticAuditAccumulator,
)
from open_cancer.parser_support_gate import decide_support_gate
from open_cancer.validation import validate_json_document


ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "data/raw/train.csv"
TEST = ROOT / "data/raw/test.csv"
SPLIT = ROOT / "data/splits/stratified_5fold_seed42.csv"
FIXTURES = ROOT / "reports/analysis/parser_contract_v4/fixtures.json"
FIXTURE_SCHEMA = ROOT / "schemas/mutation_parser_fixture.schema.json"
OUTPUT_DIR = ROOT / "reports/analysis/parser_v4_semantic_completeness"
OUTPUT_JSON = OUTPUT_DIR / "audit.json"
OUTPUT_README = OUTPUT_DIR / "README.md"
OUTPUT_SCHEMA = ROOT / "schemas/parser_semantic_completeness.schema.json"


def _folds() -> dict[str, int]:
    with SPLIT.open("r", encoding="utf-8", newline="") as handle:
        return {row["ID"]: int(row["fold"]) for row in csv.DictReader(handle)}


def _audit_csv(
    path: Path, *, name: str, fold_by_id: dict[str, int] | None
) -> dict[str, Any]:
    accumulator = SemanticAuditAccumulator(name, fold_by_id=fold_by_id)
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        genes = tuple(
            value for value in (reader.fieldnames or ())
            if value not in {"ID", "SUBCLASS"}
        )
        for row in reader:
            accumulator.consume_sample(
                sample_id=row["ID"],
                gene_cells=((gene, row.get(gene) or "") for gene in genes),
            )
    document = accumulator.to_document()
    document["gene_count"] = len(genes)
    return document


def _family_lookup(document: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (row["route"], row["event_type"]): row
        for row in document["families"]
    }


def _combined_support(
    train: dict[str, Any], test: dict[str, Any]
) -> list[dict[str, Any]]:
    train_rows = _family_lookup(train)
    test_rows = _family_lookup(test)
    output = []
    for route, event in sorted(set(train_rows) | set(test_rows)):
        left = train_rows.get((route, event), {})
        right = test_rows.get((route, event), {})
        train_samples = int(left.get("samples", 0))
        fold_samples = list(left.get("fold_samples", [0] * 5))
        decision = decide_support_gate(
            route=route,
            train_sample_count=train_samples,
            fold_sample_counts=fold_samples,
        )
        output.append(
            {
                "route": route,
                "event_type": event,
                "train_occurrences": int(left.get("occurrences", 0)),
                "train_unique_tokens": int(left.get("unique_tokens", 0)),
                "train_samples": train_samples,
                "train_genes": int(left.get("genes", 0)),
                "train_gene_cells": int(left.get("gene_cells", 0)),
                "train_fold_samples": fold_samples,
                "test_occurrences": int(right.get("occurrences", 0)),
                "test_unique_tokens": int(right.get("unique_tokens", 0)),
                "test_samples": int(right.get("samples", 0)),
                "test_genes": int(right.get("genes", 0)),
                "test_gene_cells": int(right.get("gene_cells", 0)),
                "decision": decision.decision,
                "reason": decision.reason,
            }
        )
    return output


def _markdown(document: dict[str, Any]) -> str:
    train = document["datasets"]["train"]
    test = document["datasets"]["test"]
    support = document["support_decisions"]
    eligible = [row for row in support if row["decision"] == "EXPERIMENT_ELIGIBLE"]
    analysis = [row for row in support if row["decision"] != "EXPERIMENT_ELIGIBLE"]
    lines = [
        "# Parser v4 semantic completeness·support·collision 감사",
        "",
        "> Issue: [#424](https://github.com/fabxoe/open_cancer/issues/424)",
        ">",
        "> 모델 학습이나 점수 생성 없이 parser-native baseline의 입력 schema를",
        "> 고정하기 위한 의미·지원량 감사입니다.",
        "",
        "## 결론",
        "",
        f"- train token `{train['source_token_count']:,}`개와 test token "
        f"`{test['source_token_count']:,}`개를 하나도 버리지 않고 route했습니다.",
        f"- raw-token semantic collision: train "
        f"`{train['raw_token_semantic_collision_count']}` / test "
        f"`{test['raw_token_semantic_collision_count']}`",
        f"- normalized semantic collision: train "
        f"`{train['normalized_semantic_collision_count']}` / test "
        f"`{test['normalized_semantic_collision_count']}`",
        f"- canonical support gate 통과 family: `{len(eligible)}`개, "
        f"QC-only family: `{len(analysis)}`개",
        "- support가 부족한 올바른 사건은 parser에서 삭제하지 않고 native model의",
        "  세부 피처만 QC-only 또는 상위 family 집계로 제한합니다.",
        "",
        "## Family 지원량",
        "",
        "| Route | Event | Train token | Train sample | Fold sample | Test token | 판단 |",
        "|---|---|---:|---:|---|---:|---|",
    ]
    for row in support:
        lines.append(
            f"| `{row['route']}` | `{row['event_type']}` | "
            f"{row['train_occurrences']:,} | {row['train_samples']:,} | "
            f"`{row['train_fold_samples']}` | {row['test_occurrences']:,} | "
            f"`{row['decision']}` |"
        )
    lines.extend(
        [
            "",
            "## Parse 상태",
            "",
            f"- train: `{train['parse_statuses']}`",
            f"- test: `{test['parse_statuses']}`",
            "",
            "## 장문 sequence 길이",
            "",
            "원문 sequence를 고차원 vocabulary로 만들지 않고 길이·stop·구조 같은",
            "compact 의미만 native schema 후보로 사용합니다.",
            "",
            f"- train: `{train['sequence_length_distributions']}`",
            f"- test: `{test['sequence_length_distributions']}`",
            "",
            "## 기존 5-family와의 관계",
            "",
            "`missense/synonymous/nonsense/frameshift/complex`는 과거 호환용 lexical",
            "bucket입니다. `complex`에 섞였던 deletion·insertion·delins·range와",
            "unresolved 사건은 native schema에서 분리합니다. 전체 crosswalk 원본은",
            "[`audit.json`](audit.json)의 `legacy_crosswalk`에 있습니다.",
            "",
            "## 해석 제한",
            "",
            "- `SUBCLASS`와 Public LB는 사용하지 않았습니다.",
            "- test 집계는 coverage QC이며 feature 채택·threshold 선택에 사용하지 않았습니다.",
            "- partial/unresolved 표기를 특정 생물학적 사건으로 강제 승격하지 않았습니다.",
            "- 이 결과는 성능 결과가 아니며 실제 채택은 후속 canonical 5-fold에서 판단합니다.",
            "",
            "## 다음 단계",
            "",
            "이 감사 결과와 field coverage를 바탕으로 N2 unified parser-native feature",
            "schema·adapter를 구현합니다. isoform·driver·pathway·Optuna는 아직 연결하지",
            "않습니다.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    fold_by_id = _folds()
    train = _audit_csv(TRAIN, name="train", fold_by_id=fold_by_id)
    test = _audit_csv(TEST, name="test", fold_by_id=None)
    contract = build_parser_contract(FIXTURES)
    document = {
        "schema_version": "1.0.0",
        "audit_version": PARSER_SEMANTIC_AUDIT_VERSION,
        "issue": 424,
        "analysis_only": True,
        "parser_contract": contract.__dict__,
        "inputs": {
            "train": {"path": "data/raw/train.csv", "sha256": sha256_file(TRAIN)},
            "test": {"path": "data/raw/test.csv", "sha256": sha256_file(TEST)},
            "split": {"path": "data/splits/stratified_5fold_seed42.csv",
                      "sha256": sha256_file(SPLIT)},
            "fixtures": {"path": "reports/analysis/parser_contract_v4/fixtures.json",
                         "sha256": sha256_file(FIXTURES)},
            "fixture_schema_sha256": sha256_file(FIXTURE_SCHEMA),
        },
        "constraints": {
            "subclass_used": False,
            "public_lb_used": False,
            "test_prevalence_used_for_decision": False,
            "raw_tokens_preserved": True,
            "model_trained": False,
        },
        "datasets": {"train": train, "test": test},
        "support_decisions": _combined_support(train, test),
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    validate_json_document(OUTPUT_JSON, OUTPUT_SCHEMA)
    OUTPUT_README.write_text(_markdown(document), encoding="utf-8")
    collision_count = sum(
        dataset["raw_token_semantic_collision_count"]
        + dataset["normalized_semantic_collision_count"]
        for dataset in document["datasets"].values()
    )
    if not train["mutation_presence_preserved"] or not test["mutation_presence_preserved"]:
        raise RuntimeError("parser v4 dropped source mutation tokens")
    if collision_count:
        raise RuntimeError(f"semantic collisions detected: {collision_count}")
    print(json.dumps({
        "train_tokens": train["source_token_count"],
        "test_tokens": test["source_token_count"],
        "support_family_count": len(document["support_decisions"]),
        "collisions": collision_count,
        "output": str(OUTPUT_JSON.relative_to(ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
