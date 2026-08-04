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
        ("WQ288fs", "frameshift", "WQ288FS", True),
        ("P233del", "inframe_deletion", "P233DEL", False),
        ("P11_K12insP", "inframe_insertion", "P11_K12INSP", False),
        ("R376_A377delinsP", "delins", "R376_A377DELINSP", False),
        ("447_448MD>IN", "range_replacement", "447_448MD>IN", False),
        ("A20dup", "duplication", "A20DUP", False),
        ("X127C", "other_unmappable", "X127C", False),
        ("UNKNOWN", "other_unmappable", "UNKNOWN", False),
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
    cell = canonicalize_mutation_cell("R213X R213* r213x")
    assert cell.source_token_count == 3
    assert cell.exact_duplicate_count == 2
    assert len(cell.tokens) == 1
    assert cell.tokens[0].normalized == "R213*"
    assert cell.tokens[0].event_family == "stop_gain"


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
