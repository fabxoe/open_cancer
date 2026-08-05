from open_cancer.mutation_parser_contract import route_protein_mutation
from open_cancer.parser_semantic_completeness import (
    SemanticAuditAccumulator,
    semantic_field_presence,
    semantic_sequence_lengths,
    semantic_subfamily_key,
)


def test_semantic_subfamilies_preserve_native_meaning() -> None:
    assert semantic_subfamily_key(route_protein_mutation("R132H")) == "missense"
    assert semantic_subfamily_key(route_protein_mutation("WQ288fs")) == (
        "ref_alt_before_position"
    )
    assert semantic_subfamily_key(route_protein_mutation("G235_G238del")) == (
        "residue_range:residue_aware_range"
    )
    assert semantic_subfamily_key(
        route_protein_mutation("E1117delinsGGRRIIK")
    ) == "single_position:no_stop"
    assert semantic_subfamily_key(route_protein_mutation("197_198YQ>**")) == (
        "immediate_stop"
    )


def test_field_coverage_and_sequence_lengths_are_payload_derived() -> None:
    insertion = route_protein_mutation("S261_P262insQEPPDTTS")
    fields = semantic_field_presence(insertion)
    assert fields["positions"] is True
    assert fields["reference"] is True
    assert fields["alternate"] is True
    assert fields["range_endpoints"] is True
    assert fields["length"] is True
    assert semantic_sequence_lengths(insertion)["inserted"] == 8

    delins = route_protein_mutation("H1176_W1177delinsQ")
    lengths = semantic_sequence_lengths(delins)
    assert lengths["alternate_raw"] == 1
    assert lengths["alternate_translated"] == 1


def test_streaming_audit_preserves_presence_and_has_no_collisions() -> None:
    audit = SemanticAuditAccumulator(
        "fixture", fold_by_id={"S1": 0, "S2": 1}
    )
    audit.consume_sample(
        sample_id="S1",
        gene_cells=(
            ("TP53", "R213X R213*"),
            ("EGFR", "K745_E746insIPVAIK"),
        ),
    )
    audit.consume_sample(
        sample_id="S2",
        gene_cells=(
            ("TP53", "R213Ter"),
            ("OTHER", "WT"),
        ),
    )
    document = audit.to_document()
    assert document["source_token_count"] == 4
    assert document["routed_token_count"] == 4
    assert document["mutation_presence_preserved"] is True
    assert document["raw_token_semantic_collision_count"] == 0
    assert document["normalized_semantic_collision_count"] == 0
    assert document["canonical_equivalence_group_count"] == 1
    equivalent = document["canonical_equivalence_examples"][0]
    assert equivalent["normalized_token"] == "R213*"
    assert equivalent["raw_forms"] == ["R213*", "R213Ter", "R213X"]


def test_legacy_complex_crosswalk_is_split_by_native_router() -> None:
    audit = SemanticAuditAccumulator("fixture")
    audit.consume_sample(
        sample_id="S1",
        gene_cells=(
            ("A", "E28del"),
            ("B", "E1117delinsGGRRIIK"),
            ("C", "236_237LL>LL"),
        ),
    )
    rows = audit.to_document()["legacy_crosswalk"]
    observed = {
        (row["legacy_family"], row["route"], row["event_type"])
        for row in rows
    }
    assert ("complex", "deletion", "deletion") in observed
    assert ("complex", "delins", "delins") in observed
    assert ("complex", "range_replacement", "synonymous") in observed
