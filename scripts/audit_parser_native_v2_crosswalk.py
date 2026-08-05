#!/usr/bin/env python
"""Audit compatibility/native-v2 equivalence before another experiment."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse

from open_cancer.hashing import sha256_file
from open_cancer.parser_baseline_features import ParserSupportedRangeFamily
from open_cancer.parser_compatibility_features import (
    ParserCompatibilityFamily,
    compatibility_family,
)
from open_cancer.parser_native_v2_features import (
    ParserNativeV2SemanticFamily,
    native_v2_model_consequence,
    native_v2_primary_family,
)
from open_cancer.canonical_mutation_events import parse_canonical_gene_cell


ROOT = Path(__file__).resolve().parents[1]
TRAIN = ROOT / "data/raw/train.csv"
TEST = ROOT / "data/raw/test.csv"
SUPPORT = ROOT / "reports/analysis/parser_native_v2_support/audit.json"
OUT = ROOT / "reports/analysis/parser_native_v2_crosswalk"

FAMILY_MAP = {
    "missense": "missense",
    "synonymous": "no_change",
    "nonsense": "nonsense",
    "frameshift": "frameshift",
}


def _difference(left: sparse.spmatrix, right: sparse.spmatrix) -> dict[str, object]:
    delta = sparse.csr_matrix(left - right)
    if delta.nnz:
        maximum = float(np.max(np.abs(delta.data)))
        rows = int(np.unique(delta.nonzero()[0]).size)
    else:
        maximum = 0.0
        rows = 0
    return {
        "equal": delta.nnz == 0,
        "different_cells": int(delta.nnz),
        "different_rows": rows,
        "max_abs_difference": maximum,
    }


def _token_crosswalk(frame: pd.DataFrame, genes: tuple[str, ...]) -> dict[str, object]:
    counter: Counter[tuple[str, str, str]] = Counter()
    source_tokens = 0
    active_tokens = 0
    for gene in genes:
        for cell in frame[gene].to_numpy(dtype=object, copy=False):
            parsed = parse_canonical_gene_cell(cell)
            for event in parsed.events:
                source_tokens += 1
                compatibility = compatibility_family(event)
                primary = native_v2_primary_family(event, gene_symbol=gene)
                model = native_v2_model_consequence(event) or "QC_ONLY"
                if model != "QC_ONLY":
                    active_tokens += 1
                counter[(compatibility, primary, model)] += 1
    return {
        "source_tokens": source_tokens,
        "model_active_tokens": active_tokens,
        "qc_only_tokens": source_tokens - active_tokens,
        "rows": [
            {
                "compatibility": compatibility,
                "native_primary": primary,
                "native_model": model,
                "count": count,
            }
            for (compatibility, primary, model), count in sorted(counter.items())
        ],
    }


def _feature_audit(frame: pd.DataFrame, genes: tuple[str, ...]) -> dict[str, object]:
    compatibility = ParserCompatibilityFamily(genes).fit(frame)
    native = ParserNativeV2SemanticFamily(genes).fit(frame)
    supported_range = ParserSupportedRangeFamily(genes).fit(frame)
    compatibility_matrix = compatibility.transform(frame)
    native_matrix = native.transform(frame)
    range_matrix = supported_range.transform(frame)
    c_index = {name: index for index, name in enumerate(compatibility.descriptor.feature_names)}
    n_index = {name: index for index, name in enumerate(native.descriptor.feature_names)}

    sample = {}
    gene = {}
    for compatibility_name, native_name in FAMILY_MAP.items():
        sample[compatibility_name] = _difference(
            compatibility_matrix[:, [c_index[f"sample__{compatibility_name}_count"]]],
            native_matrix[:, [n_index[f"sample__native_v2_{native_name}_gene_count"]]],
        )
        compatibility_columns = [
            c_index[f"{symbol}__{compatibility_name}"] for symbol in genes
        ]
        native_columns = [
            n_index[f"gene__{symbol}__native_v2_{native_name}_any"] for symbol in genes
        ]
        gene[compatibility_name] = _difference(
            compatibility_matrix[:, compatibility_columns],
            native_matrix[:, native_columns],
        )

    native_range_columns = [
        n_index["sample__native_v2_range_replacement_gene_count"],
        *(
            n_index[f"gene__{symbol}__native_v2_range_replacement_any"]
            for symbol in genes
        ),
    ]
    return {
        "rows": len(frame),
        "compatibility_shape": list(compatibility_matrix.shape),
        "native_v2_shape": list(native_matrix.shape),
        "mapped_sample_aggregation": sample,
        "mapped_gene_presence": gene,
        "native_range_equals_exp444_range_family": _difference(
            native_matrix[:, native_range_columns], range_matrix
        ),
    }


def main() -> None:
    train = pd.read_csv(TRAIN, dtype=str, keep_default_na=False)
    test = pd.read_csv(TEST, dtype=str, keep_default_na=False)
    genes = tuple(train.columns[2:])
    if genes != tuple(test.columns[1:]):
        raise ValueError("train/test gene schema mismatch")
    document = {
        "schema_version": "1.0.0",
        "issue": 462,
        "analysis_only": True,
        "inputs": {
            "train_sha256": sha256_file(TRAIN),
            "test_sha256": sha256_file(TEST),
            "support_audit_sha256": sha256_file(SUPPORT),
        },
        "constraints": {
            "subclass_used": False,
            "test_prevalence_used_for_selection": False,
            "public_lb_used": False,
        },
        "train": {
            "token_crosswalk": _token_crosswalk(train, genes),
            "features": _feature_audit(train, genes),
        },
        "test": {
            "token_crosswalk": _token_crosswalk(test, genes),
            "features": _feature_audit(test, genes),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "audit.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    train_feature = document["train"]["features"]
    lines = [
        "# Parser compatibility·native v2 비중복 family 전수 감사",
        "",
        "> Issue: [#462](https://github.com/fabxoe/open_cancer/issues/462)",
        ">",
        "> 모델 학습 없이 표현 차이만 측정했습니다.",
        "",
        "## 결론",
        "",
        "- missense·synonymous/no_change·nonsense·frameshift의 gene-level any는",
        "  compatibility와 native v2가 완전히 같습니다.",
        "- sample summary는 compatibility가 token count, native v2가 affected-gene",
        "  count이므로 동일하지 않습니다.",
        "- native v2의 strict range는 stop-containing range를 QC-only로 제외하므로",
        "  EXP-444의 broad supported-range와 같지 않습니다.",
        "- 다음 유효 ablation은 range 정의를 그대로 고정하고 native v2의 sample",
        "  집계만 token count로 통제하는 것입니다.",
        "",
        "## Train feature 비교",
        "",
        "| family | gene any 동일 | sample count 다른 행 | 최대 차이 |",
        "|---|---|---:|---:|",
    ]
    for family in FAMILY_MAP:
        gene_result = train_feature["mapped_gene_presence"][family]
        sample_result = train_feature["mapped_sample_aggregation"][family]
        lines.append(
            f"| `{family}` | `{gene_result['equal']}` | "
            f"{sample_result['different_rows']:,} | "
            f"{sample_result['max_abs_difference']:.0f} |"
        )
    lines.extend(
        [
            "",
            "## 다음 행동",
            "",
            "별도 Experiment Issue에서 EXP-456의 semantic routing과 gene-level any를",
            "그대로 유지하고 sample summary만 token count로 바꿉니다. 그다음에만",
            "strict range와 EXP-444 broad range의 차이를 별도 판단합니다. 두 변수를",
            "한 실험에서 동시에 바꾸지 않습니다.",
            "",
        ]
    )
    (OUT / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
