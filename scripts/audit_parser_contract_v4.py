#!/usr/bin/env python
"""Create a compact, deterministic snapshot for parser contract v4."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from open_cancer.hashing import sha256_file
from open_cancer.mutation_parser_contract import (
    build_parser_contract,
    route_protein_mutation,
)
from open_cancer.robust_mutation_parser import parse_robust_mutation_token
from open_cancer.validation import validate_json_document


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "reports/analysis/parser_contract_v4/fixtures.json"
SCHEMA = ROOT / "schemas/mutation_parser_fixture.schema.json"
OUTPUT = ROOT / "reports/analysis/parser_contract_v4/audit.json"


def main() -> None:
    validate_json_document(CATALOG, SCHEMA)
    document = json.loads(CATALOG.read_text(encoding="utf-8"))
    routes: Counter[str] = Counter()
    modules: Counter[str] = Counter()
    differences: list[dict[str, object]] = []
    max_raw_length = 0
    for fixture in document["fixtures"]:
        raw = fixture["raw_token"]
        routed = route_protein_mutation(raw)
        robust = parse_robust_mutation_token(raw)
        routes[routed.route] += 1
        modules[f"{routed.semantic_module}@{routed.semantic_module_version}"] += 1
        max_raw_length = max(max_raw_length, len(raw))
        if robust.event_family != routed.event_type or robust.normalized != routed.normalized_token:
            differences.append(
                {
                    "fixture_id": fixture["id"],
                    "v3_event": robust.event_family,
                    "v3_normalized": robust.normalized,
                    "v4_route": routed.route,
                    "v4_event": routed.event_type,
                    "v4_normalized": routed.normalized_token,
                }
            )

    contract = build_parser_contract(CATALOG)
    result = {
        "analysis_only": True,
        "target_used": False,
        "test_distribution_used_for_rule": False,
        "fixture_count": len(document["fixtures"]),
        "fixture_catalog_sha256": contract.fixture_catalog_sha256,
        "fixture_schema_sha256": sha256_file(SCHEMA),
        "contract": contract.__dict__,
        "route_counts": dict(sorted(routes.items())),
        "semantic_module_counts": dict(sorted(modules.items())),
        "max_raw_token_length": max_raw_length,
        "v3_v4_difference_count": len(differences),
        "v3_v4_differences": differences,
    }
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
