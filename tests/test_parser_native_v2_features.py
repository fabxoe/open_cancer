import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from open_cancer.mutation_parser_contract import route_protein_mutation
from open_cancer.hashing import sha256_file
from open_cancer.parser_compatibility_features import ParserCompatibilityFamily
from open_cancer.parser_native_v2_features import (
    MODEL_ACTIVE_V2_CONSEQUENCES,
    ParserNativeV2SemanticFamily,
    ParserNativeV2TokenCountFamily,
    native_v2_model_consequence,
    native_v2_primary_family,
    native_v2_semantic_contract_record,
    parse_native_v2_gene_cell,
)


def test_primary_semantics_are_exclusive_and_preserve_examples() -> None:
    cases = {
        "R132H": "substitution:missense",
        "D623D": "substitution:no_change",
        "R213X": "substitution:nonsense",
        "WQ288fs": "frameshift",
        "SDEL133fs": "frameshift",
        "G235_G238del": "deletion",
        "S261_P262insQEPPDTTS": "insertion",
        "E1117delinsGGRRIIK": "delins",
        "1436_1437SI>RF": "range_replacement",
        "236_237LL>LL": "range_no_change",
        "197_198YQ>**": "range_stop",
        "-762fs": "unresolved",
    }
    for token, expected in cases.items():
        routed = route_protein_mutation(token)
        assert native_v2_primary_family(routed, gene_symbol="GENE") == expected


def test_support_gate_projection_does_not_force_qc_only_events() -> None:
    assert native_v2_model_consequence(route_protein_mutation("R132H")) == "missense"
    assert native_v2_model_consequence(route_protein_mutation("R213Ter")) == "nonsense"
    assert native_v2_model_consequence(route_protein_mutation("WQ288fs")) == "frameshift"
    assert native_v2_model_consequence(route_protein_mutation("1436_1437SI>RF")) == "range_replacement"
    for token in (
        "G235_G238del",
        "S261_P262insQEPPDTTS",
        "E1117delinsGGRRIIK",
        "236_237LL>LL",
        "197_198YQ>**",
        "-762fs",
    ):
        assert native_v2_model_consequence(route_protein_mutation(token)) is None


def test_every_non_wt_token_has_primary_qc_provenance() -> None:
    cell = "R132H G235_G238del E1117delinsGGRRIIK -762fs"
    parsed = parse_native_v2_gene_cell("GENE", cell)
    assert parsed.mutated is True
    assert parsed.token_count == 4
    assert sum(count for _, count in parsed.primary_family_counts) == 4
    assert parsed.model_consequences == frozenset({"missense"})
    assert parsed.model_consequence_counts == (("missense", 1),)
    assert parse_native_v2_gene_cell("GENE", "WT").mutated is False


def test_v2_adapter_is_fixed_width_deterministic_and_alias_invariant() -> None:
    frame = pd.DataFrame(
        {
            "A": ["R213X", "R213Ter", "R213*"],
            "B": ["1436_1437SI>RF", "WT", "G235_G238del"],
        }
    )
    fitted = ParserNativeV2SemanticFamily(("A", "B")).fit(frame)
    matrix = fitted.transform(frame).toarray()
    names = fitted.descriptor.feature_names
    index = {name: position for position, name in enumerate(names)}
    assert matrix.shape == (3, 5 + 2 * 5)
    nonsense = index["sample__native_v2_nonsense_gene_count"]
    assert matrix[0, nonsense] == matrix[1, nonsense] == matrix[2, nonsense] == 1
    assert matrix[0, index["sample__native_v2_range_replacement_gene_count"]] == 1
    assert matrix[2, index["gene__B__native_v2_range_replacement_any"]] == 0

    second = ParserNativeV2SemanticFamily(("A", "B")).fit(frame)
    assert second.descriptor.feature_names_sha256 == fitted.descriptor.feature_names_sha256
    assert np.array_equal(second.transform(frame).toarray(), matrix)


def test_token_count_adapter_changes_only_sample_aggregation() -> None:
    frame = pd.DataFrame(
        {
            "TP53": ["R1H R2H R3X", "R4H", "WT"],
            "EGFR": ["E5H E6E", "E7X E8Ter", "1436_1437SI>RF"],
        }
    )
    gene_fitted = ParserNativeV2SemanticFamily(("TP53", "EGFR")).fit(frame)
    token_fitted = ParserNativeV2TokenCountFamily(("TP53", "EGFR")).fit(frame)
    gene_matrix = gene_fitted.transform(frame).toarray()
    token_matrix = token_fitted.transform(frame).toarray()

    # Gene-level semantic presence is exactly unchanged.
    assert np.array_equal(gene_matrix[:, 5:], token_matrix[:, 5:])
    token_index = {
        name: position for position, name in enumerate(token_fitted.descriptor.feature_names)
    }
    assert token_matrix[0, token_index["sample__native_v2_missense_token_count"]] == 3
    assert token_matrix[0, token_index["sample__native_v2_no_change_token_count"]] == 1
    assert token_matrix[0, token_index["sample__native_v2_nonsense_token_count"]] == 1
    assert token_matrix[1, token_index["sample__native_v2_nonsense_token_count"]] == 2
    assert token_matrix[2, token_index["sample__native_v2_range_replacement_token_count"]] == 1
    assert gene_fitted.descriptor.feature_names_sha256 != token_fitted.descriptor.feature_names_sha256


def test_token_count_contract_records_single_controlled_difference() -> None:
    frame = pd.DataFrame({"TP53": ["R1H R2H"]})
    fitted = ParserNativeV2TokenCountFamily(("TP53",)).fit(frame)
    record = native_v2_semantic_contract_record(fitted)
    assert record["family"] == "parser_v4_native_semantic_v2_token_count"
    assert record["sample_aggregation"] == "token_count"
    assert record["gene_aggregation"] == "consequence_presence"
    assert len(record["schema_sha256"]) == 64


def test_token_count_matches_compatibility_for_four_shared_families() -> None:
    frame = pd.DataFrame(
        {
            "TP53": ["R1H R2H R3X", "WQ288fs R4R", "WT"],
            "EGFR": ["E5H E6E", "E7X E8Ter", "1436_1437SI>RF"],
        }
    )
    compatibility = ParserCompatibilityFamily(("TP53", "EGFR")).fit(frame)
    token = ParserNativeV2TokenCountFamily(("TP53", "EGFR")).fit(frame)
    compatibility_matrix = compatibility.transform(frame).toarray()
    token_matrix = token.transform(frame).toarray()
    compatibility_index = {
        name: position for position, name in enumerate(compatibility.descriptor.feature_names)
    }
    token_index = {
        name: position for position, name in enumerate(token.descriptor.feature_names)
    }
    mapping = {
        "missense": "missense",
        "synonymous": "no_change",
        "nonsense": "nonsense",
        "frameshift": "frameshift",
    }
    for legacy_name, native_name in mapping.items():
        assert np.array_equal(
            compatibility_matrix[:, compatibility_index[f"sample__{legacy_name}_count"]],
            token_matrix[:, token_index[f"sample__native_v2_{native_name}_token_count"]],
        )


def test_v2_contract_and_schema_are_aligned() -> None:
    frame = pd.DataFrame({"TP53": ["R213X"]})
    fitted = ParserNativeV2SemanticFamily(("TP53",)).fit(frame)
    record = native_v2_semantic_contract_record(fitted)
    schema = yaml.safe_load(
        Path("configs/parser_v4_native_feature_schema_v2.yaml").read_text()
    )
    assert tuple(schema["model_active_consequences"]) == MODEL_ACTIVE_V2_CONSEQUENCES
    assert record["model_active_consequences"] == list(MODEL_ACTIVE_V2_CONSEQUENCES)
    assert len(record["schema_sha256"]) == 64
    assert len(record["feature_names_sha256"]) == 64
    assert schema["support_policy"]["target_used"] is False
    assert schema["support_policy"]["public_lb_used"] is False


def test_committed_support_audit_matches_source_and_active_schema() -> None:
    audit = json.loads(
        Path("reports/analysis/parser_native_v2_support/audit.json").read_text()
    )
    source = Path(audit["source_audit"]["path"])
    schema = Path(audit["feature_schema"]["path"])
    assert audit["source_audit"]["sha256"] == sha256_file(source)
    assert audit["feature_schema"]["sha256"] == sha256_file(schema)
    assert tuple(
        row["consequence"] for row in audit["model_active"]
    ) == MODEL_ACTIVE_V2_CONSEQUENCES
    assert all(
        row["decision"] == "EXPERIMENT_ELIGIBLE"
        for row in audit["model_active"]
    )
    assert audit["constraints"]["target_used"] is False
    assert audit["constraints"]["public_lb_used"] is False
