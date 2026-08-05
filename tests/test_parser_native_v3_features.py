from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from open_cancer.mutation_parser_contract import route_protein_mutation
from open_cancer.parser_native_v2_features import ParserNativeV2TokenCountFamily
from open_cancer.parser_native_v3_features import (
    MODEL_ACTIVE_V3_CONSEQUENCES,
    ParserNativeV3SemanticRangeFamily,
    native_v3_model_consequence,
    native_v3_semantic_contract_record,
    parse_native_v3_gene_cell,
)


def test_range_semantics_are_mutually_exclusive() -> None:
    cases = {
        "1436_1437SI>RF": "range_replacement",
        "59_60HY>QH": "range_replacement",
        "300_301LE>F*": "range_stop",
        "2126_2127WE>*K": "range_stop",
        "197_198YQ>**": "range_stop",
        "236_237LL>LL": "range_no_change",
    }
    for token, expected in cases.items():
        consequence = native_v3_model_consequence(route_protein_mutation(token))
        assert consequence == expected


def test_cell_counts_range_tokens_without_collapsing_meanings() -> None:
    parsed = parse_native_v3_gene_cell(
        "GENE", "1436_1437SI>RF 300_301LE>F* 197_198YQ>** 236_237LL>LL"
    )
    assert parsed.model_consequences == frozenset(
        {"range_replacement", "range_stop", "range_no_change"}
    )
    assert dict(parsed.model_consequence_counts) == {
        "range_no_change": 1,
        "range_replacement": 1,
        "range_stop": 2,
    }
    assert sum(count for _, count in parsed.primary_family_counts) == 4
    assert parsed.token_count == 4


def test_v3_adds_two_range_meanings_and_preserves_v2_columns() -> None:
    frame = pd.DataFrame(
        {
            "TP53": ["R1H R2X", "300_301LE>F*"],
            "EGFR": ["1436_1437SI>RF", "236_237LL>LL"],
        }
    )
    v2 = ParserNativeV2TokenCountFamily(("TP53", "EGFR")).fit(frame)
    v3 = ParserNativeV3SemanticRangeFamily(("TP53", "EGFR")).fit(frame)
    v2_matrix = v2.transform(frame).toarray()
    v3_matrix = v3.transform(frame).toarray()
    v2_names = v2.descriptor.feature_names
    v3_names = v3.descriptor.feature_names

    consequence_names = (
        "missense", "no_change", "nonsense", "frameshift", "range_replacement"
    )
    for consequence in consequence_names:
        v2_sample = v2_names.index(f"sample__native_v2_{consequence}_token_count")
        v3_sample = v3_names.index(f"sample__native_v3_{consequence}_token_count")
        assert np.array_equal(v2_matrix[:, v2_sample], v3_matrix[:, v3_sample])
        for gene in ("TP53", "EGFR"):
            v2_gene = v2_names.index(f"gene__{gene}__native_v2_{consequence}_any")
            v3_gene = v3_names.index(f"gene__{gene}__native_v3_{consequence}_any")
            assert np.array_equal(v2_matrix[:, v2_gene], v3_matrix[:, v3_gene])

    assert v3_matrix[1, v3_names.index("sample__native_v3_range_stop_token_count")] == 1
    assert v3_matrix[1, v3_names.index("sample__native_v3_range_no_change_token_count")] == 1
    assert v3_matrix[1, v3_names.index("gene__TP53__native_v3_range_stop_any")] == 1
    assert v3_matrix[1, v3_names.index("gene__EGFR__native_v3_range_no_change_any")] == 1


def test_v3_schema_and_contract_are_fixed() -> None:
    frame = pd.DataFrame({"TP53": ["197_198YQ>**"]})
    fitted = ParserNativeV3SemanticRangeFamily(("TP53",)).fit(frame)
    record = native_v3_semantic_contract_record(fitted)
    schema = yaml.safe_load(
        Path("configs/parser_v4_native_feature_schema_v3_semantic_range.yaml").read_text()
    )
    assert tuple(schema["model_active_consequences"]) == MODEL_ACTIVE_V3_CONSEQUENCES
    assert record["model_active_consequences"] == list(MODEL_ACTIVE_V3_CONSEQUENCES)
    assert record["range_semantics"]["mutually_exclusive"] is True
    assert record["sample_aggregation"] == "token_count"
    assert len(record["schema_sha256"]) == 64
    assert len(record["feature_names_sha256"]) == 64
