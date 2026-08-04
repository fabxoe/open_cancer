import pandas as pd

from open_cancer.ctnnb1_hotspot_features import (
    CTNNB1_D32_S33,
    Ctnnb1Family,
    compute_ctnnb1_d32_flag,
    compute_ctnnb1_s33_flag,
    ctnnb1_d32_family,
    ctnnb1_s33_family,
)
from open_cancer.feature_family import transform_checked


def test_ctnnb1_d32_s33_has_two_entries():
    assert CTNNB1_D32_S33 == ((32, "D"), (33, "S"))


def test_compute_ctnnb1_d32_flag_matches_position_and_reference_only():
    frame = pd.DataFrame({"CTNNB1": ["WT", "D32Y", "D32N", "S33C", "D31H", ""]})
    flags = compute_ctnnb1_d32_flag(frame)
    # WT -> 0; D32Y/D32N both match (position+reference only, alt ignored) -> 1;
    # S33C is the other position -> 0; D31H is a different position -> 0; blank -> 0
    assert flags.tolist() == [0.0, 1.0, 1.0, 0.0, 0.0, 0.0]


def test_compute_ctnnb1_s33_flag_matches_position_and_reference_only():
    frame = pd.DataFrame({"CTNNB1": ["S33C", "S33F", "D32Y", "S37F", "WT"]})
    flags = compute_ctnnb1_s33_flag(frame)
    assert flags.tolist() == [1.0, 1.0, 0.0, 0.0, 0.0]


def test_ctnnb1_d32_and_s33_flags_are_mutually_exclusive_columns():
    frame = pd.DataFrame({"CTNNB1": ["D32Y", "S33C", "S37F", "WT"]})
    d32 = compute_ctnnb1_d32_flag(frame)
    s33 = compute_ctnnb1_s33_flag(frame)
    assert (d32 * s33).sum() == 0.0


def test_ctnnb1_d32_family_matches_direct_compute_function():
    frame = pd.DataFrame({"CTNNB1": ["D32Y", "WT", "S33C"]})
    direct = compute_ctnnb1_d32_flag(frame)
    fitted = ctnnb1_d32_family().fit(frame)
    via_family = transform_checked(fitted, frame).toarray().ravel()
    assert via_family.tolist() == direct.tolist()


def test_ctnnb1_s33_family_matches_direct_compute_function():
    frame = pd.DataFrame({"CTNNB1": ["S33C", "WT", "D32Y"]})
    direct = compute_ctnnb1_s33_flag(frame)
    fitted = ctnnb1_s33_family().fit(frame)
    via_family = transform_checked(fitted, frame).toarray().ravel()
    assert via_family.tolist() == direct.tolist()


def test_ctnnb1_family_descriptor_has_no_file_backed_provenance():
    fitted = ctnnb1_d32_family().fit(pd.DataFrame({"CTNNB1": ["WT"]}))
    descriptor = fitted.descriptor
    assert descriptor.name == "ctnnb1_d32"
    assert descriptor.fit_scope == "stateless"
    assert descriptor.feature_names == ("hotspot__CTNNB1_32",)
    assert descriptor.external_knowledge == ()

    fitted_s33 = ctnnb1_s33_family().fit(pd.DataFrame({"CTNNB1": ["WT"]}))
    assert fitted_s33.descriptor.feature_names == ("hotspot__CTNNB1_33",)


def test_ctnnb1_family_rejects_unsupported_kind():
    family = Ctnnb1Family(kind="bogus")
    try:
        family.fit(pd.DataFrame({"CTNNB1": ["WT"]}))
    except ValueError as error:
        assert "bogus" in str(error)
    else:
        raise AssertionError("expected ValueError for unsupported kind")


def test_ctnnb1_family_rejects_missing_gene():
    family = ctnnb1_d32_family()
    try:
        family.fit(pd.DataFrame({"OTHER": ["WT"]}))
    except ValueError as error:
        assert "CTNNB1" in str(error)
    else:
        raise AssertionError("expected ValueError for missing gene")
