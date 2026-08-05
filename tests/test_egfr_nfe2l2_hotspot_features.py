import pandas as pd

from open_cancer.egfr_nfe2l2_hotspot_features import (
    CANDIDATES,
    EgfrNfe2l2Family,
    egfr_289_family,
    egfr_598_family,
    nfe2l2_79_family,
)
from open_cancer.feature_family import transform_checked


def test_candidates_has_three_entries():
    assert CANDIDATES == (
        ("EGFR", 289, "A"),
        ("EGFR", 598, "G"),
        ("NFE2L2", 79, "E"),
    )


def test_egfr_289_family_matches_position_and_reference_only():
    frame = pd.DataFrame({"EGFR": ["WT", "A289V", "A289T", "G598V", "A288H", ""]})
    fitted = egfr_289_family().fit(frame)
    flags = transform_checked(fitted, frame).toarray().ravel()
    # WT -> 0; A289V/A289T match (position+reference only, alt ignored) -> 1;
    # G598V is the other position -> 0; A288H is a different position -> 0; blank -> 0
    assert flags.tolist() == [0.0, 1.0, 1.0, 0.0, 0.0, 0.0]


def test_egfr_598_family_matches_position_and_reference_only():
    frame = pd.DataFrame({"EGFR": ["G598V", "G598R", "A289V", "WT"]})
    fitted = egfr_598_family().fit(frame)
    flags = transform_checked(fitted, frame).toarray().ravel()
    assert flags.tolist() == [1.0, 1.0, 0.0, 0.0]


def test_nfe2l2_79_family_matches_position_and_reference_only():
    frame = pd.DataFrame({"NFE2L2": ["E79Q", "E79K", "WT", "E80Q"]})
    fitted = nfe2l2_79_family().fit(frame)
    flags = transform_checked(fitted, frame).toarray().ravel()
    assert flags.tolist() == [1.0, 1.0, 0.0, 0.0]


def test_three_candidate_flags_are_mutually_exclusive_columns():
    egfr_frame = pd.DataFrame({"EGFR": ["A289V", "G598V", "WT"]})
    egfr_289 = transform_checked(egfr_289_family().fit(egfr_frame), egfr_frame).toarray().ravel()
    egfr_598 = transform_checked(egfr_598_family().fit(egfr_frame), egfr_frame).toarray().ravel()
    assert (egfr_289 * egfr_598).sum() == 0.0


def test_family_descriptor_has_no_file_backed_provenance():
    fitted = egfr_289_family().fit(pd.DataFrame({"EGFR": ["WT"]}))
    descriptor = fitted.descriptor
    assert descriptor.name == "egfr_nfe2l2_egfr_289"
    assert descriptor.fit_scope == "stateless"
    assert descriptor.feature_names == ("hotspot__EGFR_289",)
    assert descriptor.external_knowledge == ()

    fitted_nfe2l2 = nfe2l2_79_family().fit(pd.DataFrame({"NFE2L2": ["WT"]}))
    assert fitted_nfe2l2.descriptor.feature_names == ("hotspot__NFE2L2_79",)


def test_family_rejects_unsupported_kind():
    family = EgfrNfe2l2Family(kind="bogus")
    try:
        family.fit(pd.DataFrame({"EGFR": ["WT"]}))
    except ValueError as error:
        assert "bogus" in str(error)
    else:
        raise AssertionError("expected ValueError for unsupported kind")


def test_family_rejects_missing_gene():
    family = egfr_289_family()
    try:
        family.fit(pd.DataFrame({"OTHER": ["WT"]}))
    except ValueError as error:
        assert "EGFR" in str(error)
    else:
        raise AssertionError("expected ValueError for missing gene")
