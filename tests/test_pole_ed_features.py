import pandas as pd

from open_cancer.feature_family import transform_checked
from open_cancer.pole_ed_features import (
    POLE_ED_DRIVER_EXTENDED,
    POLE_ED_RANGE,
    POLE_HOTSPOT5,
    PoleEdFamily,
    compute_pole_ed_any_missense_flag,
    compute_pole_ed_driver_extended_flag,
    compute_pole_hotspot5_flag,
    compute_pole_non_ed_missense_flag,
    pole_ed_any_missense_family,
    pole_ed_driver_extended_family,
    pole_hotspot5_family,
)


def test_pole_hotspot5_has_five_entries():
    assert len(POLE_HOTSPOT5) == 5
    assert ("P", 286, "R") in POLE_HOTSPOT5
    assert ("V", 411, "L") in POLE_HOTSPOT5


def test_pole_hotspot5_is_subset_of_extended():
    assert POLE_HOTSPOT5.issubset(POLE_ED_DRIVER_EXTENDED)
    assert len(POLE_ED_DRIVER_EXTENDED) == 21


def test_pole_ed_range_is_268_to_471():
    assert POLE_ED_RANGE == (268, 471)


def test_compute_pole_hotspot5_flag_matches_exact_substitution_only():
    frame = pd.DataFrame({"POLE": ["WT", "P286R", "P286L", "P286S", ""]})
    flags = compute_pole_hotspot5_flag(frame)
    # WT -> 0; exact hotspot5 member -> 1; different alt (P286L) not in
    # hotspot5 (it IS in the extended set but not hotspot5) -> 0; unrelated
    # substitution -> 0; blank -> 0
    assert flags.tolist() == [0.0, 1.0, 0.0, 0.0, 0.0]


def test_compute_pole_ed_driver_extended_flag_includes_nonsense_entry():
    frame = pd.DataFrame({"POLE": ["Y458*", "P286L", "R100H"]})
    flags = compute_pole_ed_driver_extended_flag(frame)
    assert flags.tolist() == [1.0, 1.0, 0.0]


def test_compute_pole_ed_any_missense_flag_requires_missense_inside_ed():
    frame = pd.DataFrame(
        {
            "POLE": [
                "R268H",  # missense, ED lower bound -> 1
                "R471H",  # missense, ED upper bound -> 1
                "R267H",  # missense, just outside ED -> 0
                "R300R",  # synonymous inside ED -> 0
                "R300fs",  # frameshift inside ED, not missense -> 0
            ]
        }
    )
    flags = compute_pole_ed_any_missense_flag(frame)
    assert flags.tolist() == [1.0, 1.0, 0.0, 0.0, 0.0]


def test_compute_pole_non_ed_missense_flag_is_outside_ed_only():
    frame = pd.DataFrame({"POLE": ["R100H", "R300H", "WT"]})
    flags = compute_pole_non_ed_missense_flag(frame)
    assert flags.tolist() == [1.0, 0.0, 0.0]


def test_pole_hotspot5_family_matches_direct_compute_function():
    frame = pd.DataFrame({"POLE": ["P286R", "WT", "V411L"]})
    direct = compute_pole_hotspot5_flag(frame)
    fitted = pole_hotspot5_family().fit(frame)
    via_family = transform_checked(fitted, frame).toarray().ravel()
    assert via_family.tolist() == direct.tolist()


def test_pole_ed_driver_extended_family_matches_direct_compute_function():
    frame = pd.DataFrame({"POLE": ["Y458*", "WT", "S461L"]})
    direct = compute_pole_ed_driver_extended_flag(frame)
    fitted = pole_ed_driver_extended_family().fit(frame)
    via_family = transform_checked(fitted, frame).toarray().ravel()
    assert via_family.tolist() == direct.tolist()


def test_pole_ed_any_missense_family_matches_direct_compute_function():
    frame = pd.DataFrame({"POLE": ["R300H", "WT", "R100H"]})
    direct = compute_pole_ed_any_missense_flag(frame)
    fitted = pole_ed_any_missense_family().fit(frame)
    via_family = transform_checked(fitted, frame).toarray().ravel()
    assert via_family.tolist() == direct.tolist()


def test_pole_family_descriptor_has_no_file_backed_provenance():
    fitted = pole_hotspot5_family().fit(pd.DataFrame({"POLE": ["WT"]}))
    descriptor = fitted.descriptor
    assert descriptor.name == "pole_hotspot5"
    assert descriptor.fit_scope == "stateless"
    assert descriptor.feature_names == ("pole__hotspot5",)
    assert descriptor.external_knowledge == ()


def test_pole_family_rejects_unsupported_kind():
    family = PoleEdFamily(kind="bogus")
    try:
        family.fit(pd.DataFrame({"POLE": ["WT"]}))
    except ValueError as error:
        assert "bogus" in str(error)
    else:
        raise AssertionError("expected ValueError for unsupported kind")


def test_pole_family_rejects_missing_gene():
    family = pole_hotspot5_family()
    try:
        family.fit(pd.DataFrame({"OTHER": ["WT"]}))
    except ValueError as error:
        assert "POLE" in str(error)
    else:
        raise AssertionError("expected ValueError for missing gene")
