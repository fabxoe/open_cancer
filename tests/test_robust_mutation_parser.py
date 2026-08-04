from __future__ import annotations

import pandas as pd
import pytest
from scipy import sparse

from open_cancer.hashing import sha256_lines
from open_cancer.robust_mutation_parser import (
    EVENT_FAMILIES,
    ROBUST_PARSER_VERSION,
    ORDERED_NON_SIMPLE_EVENT_FAMILIES,
    RobustMutationEventFamily,
    RobustNonSimpleGeneCountFamily,
    RobustNonSimpleGeneIndicatorFamily,
    audit_robust_mutation_parser,
    canonicalize_mutation_cell,
    parse_robust_mutation_token,
    robust_event_feature_names,
)


@pytest.mark.parametrize(
    ("token", "family", "normalized", "eligible"),
    [
        ("R132H", "missense", "R132H", True),
        ("R132R", "synonymous", "R132R", True),
        ("R213*", "stop_gain", "R213*", True),
        ("R213X", "stop_gain", "R213*", True),
        ("R213Ter", "stop_gain", "R213*", True),
        ("WQ288fs", "frameshift", "WQ288FS", True),
        ("P233del", "inframe_deletion", "P233DEL", False),
        ("P11_K12insP", "inframe_insertion", "P11_K12INSP", False),
        ("R376_A377delinsP", "delins", "R376_A377DELINSP", False),
        ("447_448MD>IN", "range_replacement", "447_448MD>IN", False),
        ("A20dup", "duplication", "A20DUP", False),
        ("X127C", "other_unmappable", "X127C", False),
        ("UNKNOWN", "other_unmappable", "UNKNOWN", False),
        ("-287fs", "other_unmappable", "-287FS", False),
        ("*261*", "other_unmappable", "*261*", False),
    ],
)
def test_parse_robust_event_families(
    token: str,
    family: str,
    normalized: str,
    eligible: bool,
) -> None:
    parsed = parse_robust_mutation_token(token)
    assert parsed.event_family == family
    assert parsed.normalized == normalized
    assert parsed.position_eligible is eligible


def test_stop_x_and_star_share_one_semantic_token() -> None:
    cell = canonicalize_mutation_cell("R213X R213* r213x R213Ter")
    assert cell.source_token_count == 4
    assert cell.exact_duplicate_count == 3
    assert len(cell.tokens) == 1
    assert cell.tokens[0].normalized == "R213*"
    assert cell.tokens[0].event_family == "stop_gain"


@pytest.mark.parametrize(
    (
        "token",
        "family",
        "reference",
        "alternate",
        "translated",
        "stop_offset",
        "stop_position",
        "post_stop",
        "no_change",
    ),
    [
        ("1436_1437SI>RF", "range_replacement", "SI", "RF", "RF", None, None, None, False),
        ("59_60HY>QH", "range_replacement", "HY", "QH", "QH", None, None, None, False),
        ("300_301LE>F*", "range_replacement", "LE", "F*", "F", 1, 301, "", False),
        ("2126_2127WE>*K", "stop_gain", "WE", "*K", "", 0, 2126, "K", False),
        ("236_237LL>LL", "synonymous", "LL", "LL", "LL", None, None, None, True),
        ("197_198YQ>**", "stop_gain", "YQ", "**", "", 0, 197, "*", False),
    ],
)
def test_team_lead_range_examples_have_explicit_protein_semantics(
    token: str,
    family: str,
    reference: str,
    alternate: str,
    translated: str,
    stop_offset: int | None,
    stop_position: int | None,
    post_stop: str | None,
    no_change: bool,
) -> None:
    parsed = parse_robust_mutation_token(token)
    assert parsed.source_structure == "range_replacement"
    assert parsed.event_family == family
    assert parsed.reference_sequence == reference
    assert parsed.alternate_sequence == alternate
    assert parsed.translated_alternate_sequence == translated
    assert parsed.first_stop_offset == stop_offset
    assert parsed.first_stop_position == stop_position
    assert parsed.post_stop_sequence == post_stop
    assert parsed.contains_stop is (stop_offset is not None)
    assert parsed.protein_truncating is (stop_offset is not None)
    assert parsed.protein_no_change is no_change
    assert parsed.range_reference_span_valid is True


def test_multiletter_frameshift_does_not_treat_residue_del_as_keyword() -> None:
    parsed = parse_robust_mutation_token("SDEL133fs")
    assert parsed.event_family == "frameshift"
    assert parsed.source_structure == "frameshift"
    assert parsed.residue_positions == (133,)
    assert parsed.reference_sequence == "SDEL"
    assert parsed.reference_amino_acid is None
    assert parsed.frameshift_prefix_semantics == "unresolved_multiletter_prefix"
    assert parsed.position_eligible is True
    assert parsed.protein_truncating is True

    ambiguous_stop_prefix = parse_robust_mutation_token("IW*44fs")
    assert ambiguous_stop_prefix.event_family == "frameshift"
    assert ambiguous_stop_prefix.reference_sequence == "IW*"
    assert (
        ambiguous_stop_prefix.frameshift_prefix_semantics
        == "unresolved_multiletter_prefix"
    )


def test_range_alternate_fs_is_phenylalanine_serine_not_frameshift() -> None:
    parsed = parse_robust_mutation_token("721_722LA>FS")
    assert parsed.event_family == "range_replacement"
    assert parsed.source_structure == "range_replacement"
    assert parsed.alternate_sequence == "FS"
    assert parsed.contains_stop is False
    assert parsed.protein_truncating is False


def test_range_stop_spellings_share_one_canonical_semantic_token() -> None:
    cell = canonicalize_mutation_cell(
        "300_301LE>F* 300_301LE>FX 300_301LE>FTer"
    )
    assert cell.source_token_count == 3
    assert cell.exact_duplicate_count == 2
    assert len(cell.tokens) == 1
    assert cell.tokens[0].normalized == "300_301LE>F*"


def test_range_reference_length_must_match_coordinate_span() -> None:
    parsed = parse_robust_mutation_token("10_11ACD>RF")
    assert parsed.source_structure == "range_replacement"
    assert parsed.range_reference_span_valid is False
    assert parsed.confidence == "low"


def test_ambiguous_non_protein_positions_are_never_exposed_as_residues() -> None:
    for token in ("-287fs", "*261*"):
        parsed = parse_robust_mutation_token(token)
        assert parsed.event_family == "other_unmappable"
        assert parsed.residue_positions == ()
        assert parsed.position_eligible is False


@pytest.mark.parametrize(
    "token",
    [
        "R132H",
        "D623D",
        "R213X",
        "R213Ter",
        "K16fs",
        "91_92NH>KY",
        "249del",
        "R649del",
        "-287fs",
        "*261*",
    ],
)
def test_token_normalization_is_idempotent(token: str) -> None:
    first = parse_robust_mutation_token(token)
    second = parse_robust_mutation_token(first.normalized)
    assert second.normalized == first.normalized
    assert second.event_family == first.event_family
    assert second.residue_positions == first.residue_positions
    assert second.position_eligible == first.position_eligible


def test_similar_positions_do_not_collapse_different_event_meanings() -> None:
    stop = parse_robust_mutation_token("R213X")
    missense = parse_robust_mutation_token("R213H")
    deletion = parse_robust_mutation_token("R213del")
    assert {stop.event_family, missense.event_family, deletion.event_family} == {
        "stop_gain",
        "missense",
        "inframe_deletion",
    }
    assert len({stop.normalized, missense.normalized, deletion.normalized}) == 3


def test_cell_representation_is_invariant_to_order_whitespace_and_duplicates() -> None:
    left = canonicalize_mutation_cell("  P233del   R132H P233del  ")
    right = canonicalize_mutation_cell("R132H P233DEL")
    left_semantics = tuple(
        (token.normalized, token.event_family, token.residue_positions)
        for token in left.tokens
    )
    right_semantics = tuple(
        (token.normalized, token.event_family, token.residue_positions)
        for token in right.tokens
    )
    assert left_semantics == right_semantics
    assert left.exact_duplicate_count == 1
    assert right.exact_duplicate_count == 0


def test_blank_and_wt_cells_have_no_events() -> None:
    assert canonicalize_mutation_cell("").tokens == ()
    assert canonicalize_mutation_cell("WT WT").tokens == ()
    assert canonicalize_mutation_cell(None).tokens == ()


def test_robust_family_counts_unique_genes_not_raw_tokens() -> None:
    frame = pd.DataFrame(
        {
            "G1": ["R213X R213*", "WT"],
            "G2": ["Q10* P11del P12del", "R2H"],
        }
    )
    family = RobustMutationEventFamily(
        gene_columns=("G1", "G2"),
        include_gene_indicators=True,
    ).fit(frame)
    matrix = sparse.csr_matrix(family.transform(frame))
    names = family.descriptor.feature_names

    assert matrix[0, names.index("sample__robust_stop_gain_gene_count")] == 2
    assert matrix[0, names.index("sample__robust_inframe_deletion_gene_count")] == 1
    assert matrix[0, names.index("G1__robust_stop_gain_any")] == 1
    assert matrix[0, names.index("G2__robust_stop_gain_any")] == 1
    assert matrix[0, names.index("G2__robust_inframe_deletion_any")] == 1
    assert matrix[1, names.index("sample__robust_missense_gene_count")] == 1


def test_r1_replacement_excludes_x_stop_and_counts_non_simple_genes_once() -> None:
    frame = pd.DataFrame(
        {
            "G1": ["R213X R213* P233del P234del", "WT"],
            "G2": ["R376_A377delinsP", "Q10X"],
        }
    )
    fitted = RobustNonSimpleGeneCountFamily(("G1", "G2")).fit(frame)
    matrix = fitted.transform(frame)

    assert fitted.base_feature_names_to_drop == ("sample__complex_count",)
    assert fitted.descriptor.feature_names == (
        "sample__robust_non_simple_event_gene_count",
    )
    assert matrix[0, 0] == 2  # multiple events in G1 still count as one affected gene
    assert matrix[1, 0] == 0  # X alternate is normalized stop-gain, not non-simple


def test_r2_replaces_only_generic_gene_complex_with_semantic_indicators() -> None:
    frame = pd.DataFrame(
        {
            "G1": ["R213X P233del P234del", "A20dup"],
            "G2": ["R376_A377delinsP", "R2H"],
        }
    )
    fitted = RobustNonSimpleGeneIndicatorFamily(("G1", "G2")).fit(frame)
    matrix = fitted.transform(frame)
    names = fitted.descriptor.feature_names

    assert fitted.base_feature_names_to_drop == ("G1__complex", "G2__complex")
    assert matrix.shape == (2, 2 * len(ORDERED_NON_SIMPLE_EVENT_FAMILIES))
    assert matrix[0, names.index("G1__robust_inframe_deletion_any")] == 1
    assert matrix[0, names.index("G1__robust_other_unmappable_any")] == 0
    assert matrix[0, names.index("G2__robust_delins_any")] == 1
    assert matrix[1, names.index("G1__robust_duplication_any")] == 1
    assert matrix[1].nnz == 1
    assert "sample__complex_count" not in fitted.base_feature_names_to_drop


def test_r2_feature_order_is_gene_then_fixed_non_simple_family_order() -> None:
    fitted = RobustNonSimpleGeneIndicatorFamily(("B", "A")).fit(
        pd.DataFrame({"B": ["WT"], "A": ["WT"]})
    )
    expected = tuple(
        f"{gene}__robust_{family}_any"
        for gene in ("B", "A")
        for family in ORDERED_NON_SIMPLE_EVENT_FAMILIES
    )
    assert fitted.descriptor.feature_names == expected
    assert fitted.transform(pd.DataFrame({"B": ["WT"], "A": ["WT"]})).nnz == 0


def test_feature_order_and_hash_are_deterministic() -> None:
    names = robust_event_feature_names(("B", "A"), include_gene_indicators=True)
    assert names[: len(EVENT_FAMILIES)] == tuple(
        f"sample__robust_{family}_gene_count" for family in EVENT_FAMILIES
    )
    assert names[len(EVENT_FAMILIES)] == "B__robust_missense_any"
    first = RobustMutationEventFamily(("B", "A"), True).fit(
        pd.DataFrame({"B": ["WT"], "A": ["WT"]})
    )
    second = RobustMutationEventFamily(("B", "A"), True).fit(
        pd.DataFrame({"B": ["WT"], "A": ["WT"]})
    )
    assert first.descriptor.feature_names_sha256 == second.descriptor.feature_names_sha256
    assert first.descriptor.feature_names_sha256 == sha256_lines(names)


def test_parser_audit_is_compact_and_counts_normalization() -> None:
    frame = pd.DataFrame(
        {
            "G1": ["R213X R213*", "UNKNOWN"],
            "G2": ["P233del", "WT"],
        }
    )
    audit = audit_robust_mutation_parser(frame, ("G1", "G2"))
    assert audit["parser_version"] == ROBUST_PARSER_VERSION
    assert audit["source_tokens"] == 4
    assert audit["canonical_tokens"] == 3
    assert audit["exact_duplicates_removed"] == 1
    assert audit["event_family_counts"]["stop_gain"] == 1
    assert audit["event_family_counts"]["inframe_deletion"] == 1
    assert audit["event_family_counts"]["other_unmappable"] == 1
    assert len(audit["contract_sha256"]) == 64


def test_robust_family_rejects_missing_gene_columns() -> None:
    frame = pd.DataFrame({"G1": ["R2H"]})
    fitted = RobustMutationEventFamily(("G1", "G2")).fit(frame)
    with pytest.raises(ValueError, match="유전자 열"):
        fitted.transform(frame)
