from open_cancer.isoform_annotation_multiplicity import group_gene_cell_annotations


def test_iars1_frameshift_positions_form_likely_not_confirmed_group() -> None:
    result = group_gene_cell_annotations(
        "Y1204Cfs Y1201Cfs Y1227Cfs Y1207Cfs Y1232Cfs Y1252Cfs"
    )
    assert result.raw_annotation_count == 6
    assert result.strict_event_count == 6
    assert result.likely_event_count == 1
    assert result.likely_collapse_count == 5
    assert result.likely_groups[0].confidence == "likely"
    assert result.likely_groups[0].signature == ("frameshift", "Y", "C")


def test_egfr_same_insertion_sequence_groups_across_isoform_positions() -> None:
    result = group_gene_cell_annotations(
        "K692_E693insIPVAIK K745_E746insIPVAIK "
        "K478_E479insIPVAIK K700_E701insIPVAIK"
    )
    assert result.strict_event_count == 4
    assert result.likely_event_count == 1
    assert result.likely_groups[0].signature == ("insertion", "IPVAIK")


def test_different_inserted_sequences_and_unrelated_substitutions_stay_separate() -> None:
    result = group_gene_cell_annotations(
        "K10_E11insAAA K20_E21insBBB D1071N Y780* V963V"
    )
    assert result.raw_annotation_count == 5
    assert result.strict_event_count == 5
    assert result.likely_event_count == 5
    assert result.likely_groups == ()


def test_raw_and_exact_duplicate_counts_are_preserved() -> None:
    result = group_gene_cell_annotations("R132H R132H WT")
    assert result.raw_tokens == ("R132H", "R132H")
    assert result.raw_annotation_count == 2
    assert result.strict_event_count == 1
    assert result.exact_duplicate_count == 1
    assert result.likely_event_count == 1


def test_empty_cell() -> None:
    result = group_gene_cell_annotations("WT")
    assert result.raw_annotation_count == result.likely_event_count == 0
