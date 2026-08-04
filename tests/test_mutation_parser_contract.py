from __future__ import annotations

import json
from pathlib import Path

import pytest

from open_cancer.mutation_parser_contract import (
    build_parser_contract,
    route_protein_mutation,
    validate_resolved_parser_contract,
)
from open_cancer.validation import validate_json_document


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "reports/analysis/parser_contract_v4/fixtures.json"
SCHEMA = ROOT / "schemas/mutation_parser_fixture.schema.json"


def test_fixture_catalog_schema_and_routes() -> None:
    validate_json_document(CATALOG, SCHEMA)
    document = json.loads(CATALOG.read_text(encoding="utf-8"))
    for fixture in document["fixtures"]:
        routed = route_protein_mutation(fixture["raw_token"])
        assert routed.raw_token == fixture["raw_token"]
        assert routed.route == fixture["expected_route"], fixture["id"]
        assert routed.event_type == fixture["expected_event_type"], fixture["id"]
        assert list(routed.positions) == fixture["expected_positions"], fixture["id"]


def test_router_precedence_prevents_substring_double_counting() -> None:
    assert route_protein_mutation("SDEL133fs").route == "frameshift"
    assert route_protein_mutation("E1117delinsG").route == "delins"
    assert route_protein_mutation("G108del").route == "deletion"
    assert route_protein_mutation("K745_E746insIPVAIK").route == "insertion"


def test_contract_is_content_addressed_and_complete() -> None:
    contract = build_parser_contract(CATALOG)
    resolved = validate_resolved_parser_contract(
        contract.__dict__, fixture_catalog_path=CATALOG
    )
    assert resolved == contract


def test_missing_or_stale_contract_fails() -> None:
    contract = build_parser_contract(CATALOG).__dict__
    missing = dict(contract)
    missing.pop("feature_adapter_version")
    with pytest.raises(ValueError, match="missing required fields"):
        validate_resolved_parser_contract(missing, fixture_catalog_path=CATALOG)

    stale = dict(contract)
    stale["fixture_catalog_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="does not match"):
        validate_resolved_parser_contract(stale, fixture_catalog_path=CATALOG)
