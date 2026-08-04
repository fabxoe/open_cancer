from __future__ import annotations

import pandas as pd
import pytest

from open_cancer.protein_substitution_semantics import (
    PROTEIN_SUBSTITUTION_SEMANTICS_VERSION,
    PROTEIN_SUBSTITUTION_SEMANTICS_CONTRACT,
    ProteinSubstitutionSemanticFamily,
    audit_protein_substitution_semantics,
    parse_protein_substitution_token,
)


def test_contract_is_versioned_and_target_independent() -> None:
    assert PROTEIN_SUBSTITUTION_SEMANTICS_CONTRACT["definition_version"] == "4.0.0"
    assert PROTEIN_SUBSTITUTION_SEMANTICS_CONTRACT["raw_token_preserved"] is True
    assert PROTEIN_SUBSTITUTION_SEMANTICS_CONTRACT["target_used"] is False
    assert PROTEIN_SUBSTITUTION_SEMANTICS_CONTRACT["test_distribution_used_for_rule"] is False


@pytest.mark.parametrize(
    ("token", "event", "subtype", "normalized", "changed", "delta"),
    [
        ("R132H", "missense", "missense", "R132H", True, True),
        ("D623D", "no_change", "synonymous", "D623D", False, False),
        ("E237*", "nonsense", "nonsense", "E237*", True, False),
        ("S126X", "nonsense", "nonsense", "S126*", True, False),
        ("E237Ter", "nonsense", "nonsense", "E237*", True, False),
        ("m42t", "missense", "missense", "M42T", True, True),
    ],
)
def test_exact_substitution_semantics(
    token: str,
    event: str,
    subtype: str,
    normalized: str,
    changed: bool,
    delta: bool,
) -> None:
    parsed = parse_protein_substitution_token(token)
    assert parsed.event_type == event
    assert parsed.substitution_type == subtype
    assert parsed.normalized_token == normalized
    assert parsed.parse_status == "complete"
    assert parsed.protein_changed is changed
    assert parsed.physicochemical_delta_eligible is delta
    assert parsed.parser_definition_version == PROTEIN_SUBSTITUTION_SEMANTICS_VERSION


def test_stop_spellings_are_semantically_identical_except_raw_provenance() -> None:
    variants = [parse_protein_substitution_token(token) for token in ("E237*", "E237X", "E237Ter")]
    semantic = {
        (
            item.normalized_token,
            item.event_type,
            item.substitution_type,
            item.alternate_residue_canonical,
            item.contains_stop,
            item.immediate_stop,
        )
        for item in variants
    }
    assert semantic == {("E237*", "nonsense", "nonsense", "*", True, True)}
    assert {item.raw_token for item in variants} == {"E237*", "E237X", "E237Ter"}


@pytest.mark.parametrize("token", ["M1T", "M1X", "M1*"])
def test_met1_change_is_start_site_not_ordinary_substitution(token: str) -> None:
    parsed = parse_protein_substitution_token(token)
    assert parsed.event_type == "start_codon_affected"
    assert parsed.start_codon_affected is True
    assert parsed.substitution_type == "unknown"
    assert parsed.physicochemical_delta_eligible is False


def test_reference_side_x_and_star_remain_unresolved() -> None:
    unknown = parse_protein_substitution_token("X127C")
    assert unknown.event_type == "unknown_reference_substitution"
    assert unknown.unknown_reference_residue is True
    assert unknown.contains_stop is False
    assert unknown.parse_status == "unresolved"

    nonstandard = parse_protein_substitution_token("*261*")
    assert nonstandard.event_type == "nonstandard_stop_reference"
    assert nonstandard.nonstandard_reference_stop_notation is True
    assert nonstandard.parse_status == "unresolved"


@pytest.mark.parametrize(
    "token",
    [
        "1436_1437SI>RF",
        "59_60HY>QH",
        "236_237LL>LL",
        "P233del",
        "P11_K12insP",
        "SDEL133fs",
        "-762fs",
    ],
)
def test_other_grammars_are_not_consumed(token: str) -> None:
    parsed = parse_protein_substitution_token(token)
    assert parsed.parse_status == "not_applicable"
    assert parsed.event_type == "other"


@pytest.mark.parametrize(
    "token",
    ["R132H", "D623D", "E237*", "E237X", "E237Ter", "M1T", "X127C", "*261*"],
)
def test_normalization_is_idempotent(token: str) -> None:
    first = parse_protein_substitution_token(token)
    second = parse_protein_substitution_token(first.normalized_token)
    assert second.normalized_token == first.normalized_token
    assert second.event_type == first.event_type
    assert second.substitution_type == first.substitution_type


def test_feature_adapter_keeps_token_and_unique_gene_counts_separate() -> None:
    frame = pd.DataFrame(
        {
            "G1": ["R1H R2H", "M1T"],
            "G2": ["E3X D4D", "X7C"],
        }
    )
    fitted = ProteinSubstitutionSemanticFamily(
        gene_columns=("G1", "G2"),
        include_gene_features=True,
    ).fit(frame)
    matrix = fitted.transform(frame)
    names = fitted.descriptor.feature_names

    assert matrix[0, names.index("sample__substitution_missense_gene_count")] == 1
    assert matrix[0, names.index("sample__substitution_missense_token_count")] == 2
    assert matrix[0, names.index("G1__substitution_missense_any")] == 1
    assert matrix[0, names.index("G1__substitution_missense_count")] == 2
    assert matrix[0, names.index("sample__substitution_nonsense_gene_count")] == 1
    assert matrix[1, names.index("sample__substitution_start_codon_affected_token_count")] == 1
    assert matrix[1, names.index("sample__substitution_unknown_reference_token_count")] == 1


def test_audit_is_compact_and_patient_free() -> None:
    frame = pd.DataFrame({"G1": ["R1H E2X", "D3D"], "G2": ["WT", "M1T"]})
    result = audit_protein_substitution_semantics(frame, ("G1", "G2"))
    assert result["event_counts"]["missense"] == 1
    assert result["event_counts"]["nonsense"] == 1
    assert result["event_counts"]["no_change"] == 1
    assert result["event_counts"]["start_codon_affected"] == 1
    assert "ID" not in str(result)
