from open_cancer.parser_support_gate import decide_support_gate, support_family_key


def test_supported_family_is_experiment_eligible() -> None:
    result = decide_support_gate(
        route="frameshift",
        train_sample_count=100,
        fold_sample_counts=[20, 19, 21, 20, 20],
    )
    assert result.decision == "EXPERIMENT_ELIGIBLE"


def test_zero_or_sparse_family_is_analysis_only() -> None:
    assert decide_support_gate(
        route="insertion", train_sample_count=0, fold_sample_counts=[0] * 5
    ).decision == "ANALYSIS_ONLY"
    assert decide_support_gate(
        route="deletion",
        train_sample_count=20,
        fold_sample_counts=[4, 4, 4, 4, 4],
    ).decision == "ANALYSIS_ONLY"


def test_unresolved_never_becomes_experiment_feature() -> None:
    result = decide_support_gate(
        route="unresolved",
        train_sample_count=1000,
        fold_sample_counts=[200] * 5,
    )
    assert result.decision == "UNRESOLVED_ONLY"


def test_stop_containing_range_is_not_collapsed_into_ordinary_range() -> None:
    assert support_family_key(
        route="range_replacement",
        event_type="range_replacement",
        payload={"contains_stop": True},
    ) == ("range_replacement", "stop_containing")
    assert support_family_key(
        route="range_replacement",
        event_type="range_replacement",
        payload={"contains_stop": False},
    ) == ("range_replacement", "range_replacement")
