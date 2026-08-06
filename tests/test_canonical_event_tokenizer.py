from __future__ import annotations

from open_cancer.canonical_event_tokenizer import (
    build_event_vocabulary,
    canonical_event_tokens,
    summarize_event_tokens,
    tokenize_patient_event_row,
)
from open_cancer.mutation_parser_contract import route_protein_mutation


def _tokens(gene: str, raw: str) -> tuple[str, ...]:
    return canonical_event_tokens(gene, route_protein_mutation(raw))


def test_stop_notation_aliases_have_identical_semantic_tokens() -> None:
    assert _tokens("TP53", "R582X") == _tokens("TP53", "R582Ter")
    assert _tokens("TP53", "R582Ter") == _tokens("TP53", "R582*")
    assert "gene=TP53|family=substitution:nonsense" in _tokens("TP53", "R582X")
    assert "gene=TP53|aa_transition=R>STOP" in _tokens("TP53", "R582X")


def test_substitution_retains_transition_and_no_change_meaning() -> None:
    missense = _tokens("IDH1", "R132H")
    no_change = _tokens("IDH1", "R132R")
    assert "gene=IDH1|family=substitution:missense" in missense
    assert "gene=IDH1|aa_transition=R>H" in missense
    assert "gene=IDH1|family=substitution:no_change" in no_change
    assert "gene=IDH1|aa_transition=R>R" in no_change
    assert missense != _tokens("IDH2", "R132H")


def test_frameshift_only_exposes_single_confirmed_first_new_residue() -> None:
    compact = _tokens("NPM1", "WQ288fs")
    ambiguous = _tokens("ELF3", "SDEL133fs")
    assert "gene=NPM1|frameshift_first_new_aa=Q" in compact
    assert not any("frameshift_first_new_aa" in token for token in ambiguous)
    assert not any("DEL" in token for token in ambiguous)
    assert "gene=ELF3|parse_status=partial" in ambiguous


def test_deletion_insertion_and_delins_use_bounded_length_and_composition() -> None:
    deletion = _tokens("GENE", "G235_G238del")
    insertion = _tokens("MADCAM1", "S261_P262insQEPPDTTS")
    delins = _tokens("GENE", "E1117delinsGGRRIIK")

    assert "gene=GENE|deleted_length=3-5" in deletion
    assert "gene=MADCAM1|inserted_length=6-10" in insertion
    assert insertion.count("gene=MADCAM1|inserted_aa=P") == 2
    assert "gene=GENE|replaced_length=1" in delins
    assert "gene=GENE|replacement_length=6-10" in delins
    assert "gene=GENE|net_length_change=positive" in delins
    assert not any("GGRRIIK" in token for token in delins)
    assert not any("QEPPDTTS" in token for token in insertion)


def test_range_stop_and_range_no_change_are_distinct() -> None:
    no_change = _tokens("GENE", "236_237LL>LL")
    stop = _tokens("GENE", "300_301LE>F*")
    assert "gene=GENE|family=range_no_change" in no_change
    assert "gene=GENE|family=range_stop" in stop
    assert "gene=GENE|subfamily=later_stop" in stop
    assert "gene=GENE|position_span=2" in stop


def test_unresolved_token_retains_provenance_without_raw_vocabulary() -> None:
    tokens = _tokens("GENE", "-762fs")
    assert "gene=GENE|family=unresolved" in tokens
    assert "gene=GENE|parse_status=unresolved" in tokens
    assert "gene=GENE|unresolved_structure=other" in tokens
    assert not any("762" in token for token in tokens)


def test_patient_multiset_is_order_invariant_and_preserves_counts() -> None:
    row = {"TP53": "R582X R582Ter", "IDH1": "R132H"}
    forward = tokenize_patient_event_row(row, ("TP53", "IDH1"))
    reverse = tokenize_patient_event_row(row, ("IDH1", "TP53"))
    assert forward == reverse
    assert forward.source_event_count == 3
    assert forward.as_counter()["gene=TP53|aa_transition=R>STOP"] == 2
    assert forward.sha256 == reverse.sha256


def test_blank_and_wt_have_separate_provenance_contract() -> None:
    result = tokenize_patient_event_row(
        {"A": "WT", "B": "", "C": None}, ("A", "B", "C")
    )
    assert result.source_event_count == 0
    assert result.wt_gene_cell_count == 1
    assert result.blank_gene_cell_count == 2
    assert result.as_counter() == {
        "gene=B|provenance=blank": 1,
        "gene=C|provenance=blank": 1,
    }


def test_position_bins_are_one_based_and_configurable() -> None:
    default = _tokens("IDH1", "R132H")
    width_50 = canonical_event_tokens(
        "IDH1", route_protein_mutation("R132H"), position_bin_width=50
    )
    assert "gene=IDH1|position_bin=101-200" in default
    assert "gene=IDH1|position_bin=101-150" in width_50


def test_vocabulary_and_audit_are_deterministic() -> None:
    first = tokenize_patient_event_row(
        {"TP53": "R582X", "IDH1": "R132H"}, ("TP53", "IDH1")
    )
    second = tokenize_patient_event_row(
        {"TP53": "WT", "IDH1": "R132R"}, ("TP53", "IDH1")
    )
    forward = build_event_vocabulary((first, second))
    reverse = build_event_vocabulary((second, first))
    assert forward == reverse
    assert forward.sha256 == reverse.sha256
    assert tuple(column for column, _ in forward.encode(first)) == tuple(
        sorted(column for column, _ in forward.encode(first))
    )

    summary = summarize_event_tokens((first, second))
    assert summary.patient_count == 2
    assert summary.source_event_count == 3
    assert summary.unique_token_count == len(forward.tokens)
    assert summary.vocabulary_sha256 == forward.sha256
