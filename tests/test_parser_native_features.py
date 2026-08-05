from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from open_cancer.parser_native_features import (
    NATIVE_CONSEQUENCES,
    ParserNativeSemanticFamily,
    native_consequence,
    native_semantic_contract_record,
    parse_native_gene_cell,
)
from open_cancer.mutation_parser_contract import route_protein_mutation


def test_native_consequence_uses_semantics_not_legacy_complex_bucket() -> None:
    assert native_consequence(route_protein_mutation("R132H")) == "missense"
    assert native_consequence(route_protein_mutation("D623D")) == "no_change"
    assert native_consequence(route_protein_mutation("R213X")) == "nonsense"
    assert native_consequence(route_protein_mutation("R213Ter")) == "nonsense"
    assert native_consequence(route_protein_mutation("WQ288fs")) == "frameshift"
    assert native_consequence(route_protein_mutation("1436_1437SI>RF")) == (
        "range_replacement"
    )
    assert native_consequence(route_protein_mutation("236_237LL>LL")) == "no_change"
    assert native_consequence(route_protein_mutation("197_198YQ>**")) == "nonsense"
    assert native_consequence(route_protein_mutation("E28del")) == (
        "non_simple_or_unresolved"
    )


def test_every_non_wt_cell_preserves_mutation_presence() -> None:
    examples = (
        "R132H",
        "R213X R213Ter R213*",
        "WQ288fs SDEL133fs",
        "G235_G238del",
        "S261_P262insQEPPDTTS",
        "E1117delinsGGRRIIK",
        "-762fs *261*",
    )
    for cell in examples:
        parsed = parse_native_gene_cell(cell)
        assert parsed.mutated is True
        assert parsed.token_count == len(cell.split())
        assert parsed.consequences
    assert parse_native_gene_cell("WT").mutated is False
    assert parse_native_gene_cell("").mutated is False


def test_adapter_has_stable_schema_and_affected_gene_counts() -> None:
    frame = pd.DataFrame(
        {
            "A": ["R132H R133H", "WT"],
            "B": ["R213X R213Ter", "WQ288fs"],
            "C": ["E28del", "236_237LL>LL"],
        }
    )
    fitted = ParserNativeSemanticFamily(("A", "B", "C")).fit(frame)
    matrix = fitted.transform(frame).toarray()
    names = fitted.descriptor.feature_names
    index = {name: position for position, name in enumerate(names)}

    assert matrix.shape == (2, 12 + 3 * len(NATIVE_CONSEQUENCES))
    assert matrix[0, index["sample__native_missense_gene_count"]] == 1
    assert matrix[0, index["sample__native_nonsense_gene_count"]] == 1
    assert matrix[0, index["sample__native_non_simple_or_unresolved_gene_count"]] == 1
    assert matrix[0, index["gene__A__native_missense_any"]] == 1
    assert matrix[0, index["gene__B__native_nonsense_any"]] == 1
    assert matrix[1, index["sample__native_frameshift_gene_count"]] == 1
    assert matrix[1, index["sample__native_no_change_gene_count"]] == 1
    assert matrix[1, index[
        "sample__native_frameshift_ref_alt_before_position_gene_count"
    ]] == 1

    second = ParserNativeSemanticFamily(("A", "B", "C")).fit(frame)
    assert second.descriptor.feature_names == names
    assert second.descriptor.feature_names_sha256 == (
        fitted.descriptor.feature_names_sha256
    )
    assert np.array_equal(second.transform(frame).toarray(), matrix)


def test_contract_records_schema_and_feature_hashes() -> None:
    frame = pd.DataFrame({"TP53": ["R213X"]})
    fitted = ParserNativeSemanticFamily(("TP53",)).fit(frame)
    record = native_semantic_contract_record(fitted)
    assert record["schema_sha256"] == fitted.schema_sha256
    assert len(record["schema_sha256"]) == 64
    assert len(record["feature_names_sha256"]) == 64
    assert record["mutation_presence_policy"] == "preserve_existing_base_feature"
    schema = yaml.safe_load(
        Path("configs/parser_v4_native_feature_schema_v1.yaml").read_text()
    )
    assert tuple(schema["model_active_consequences"]) == NATIVE_CONSEQUENCES
    assert schema["support_policy"]["target_used"] is False
    assert schema["support_policy"]["public_lb_used"] is False
