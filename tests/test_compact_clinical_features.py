from __future__ import annotations

import pandas as pd

from open_cancer.compact_clinical_features import CompactClinicalMutationFamily


def test_compact_features_use_parser_v4_and_patient_support() -> None:
    train = pd.DataFrame({
        "G1": ["R1H R1H", "R1H", "R1H", "R1H", "R1H", "WT"],
        "G2": ["E2X", "E2Ter", "E2*", "K3fs", "D4D", "P5del"],
    })
    fitted = CompactClinicalMutationFamily(
        gene_columns=("G1", "G2"), hotspot_min_patient_count=5
    ).fit(train)
    assert fitted.recurrent_missense_keys == ("G1:R1H",)
    assert dict(fitted.recurrent_missense_support) == {"G1:R1H": 5}
    assert fitted.mutated_genes == ("G1", "G2")
    assert fitted.truncating_genes == ("G2",)

    matrix = fitted.transform(train).toarray()
    names = fitted.descriptor.feature_names
    assert matrix[0, names.index("recurrent_missense__G1")] == 1
    assert matrix[0, names.index("summary__total_event_count")] == 3
    assert matrix[0, names.index("summary__nonsense_event_count")] == 1
    assert matrix[3, names.index("summary__frameshift_event_count")] == 1


def test_validation_only_event_does_not_change_fitted_vocabulary() -> None:
    train = pd.DataFrame({"G1": ["R1H", "WT"], "G2": ["WT", "WT"]})
    validation = pd.DataFrame({"G1": ["Q9K"], "G2": ["A7V"]})
    fitted = CompactClinicalMutationFamily(
        gene_columns=("G1", "G2"), hotspot_min_patient_count=1
    ).fit(train)
    before = fitted.metadata()
    transformed = fitted.transform(validation)
    assert transformed.shape[1] == len(fitted.descriptor.feature_names)
    assert "mutated__G2" not in fitted.descriptor.feature_names
    assert fitted.metadata() == before


def test_feature_order_and_hash_are_deterministic() -> None:
    frame = pd.DataFrame({"B": ["R2H"], "A": ["E1*"]})
    family = CompactClinicalMutationFamily(
        gene_columns=("B", "A"), hotspot_min_patient_count=1
    )
    first = family.fit(frame)
    second = family.fit(frame.copy())
    assert first.descriptor.feature_names == second.descriptor.feature_names
    assert first.metadata()["feature_names_sha256"] == second.metadata()["feature_names_sha256"]
    assert first.descriptor.feature_names[:2] == ("mutated__A", "mutated__B")


def test_stop_aliases_are_all_truncating() -> None:
    frame = pd.DataFrame({"G": ["E2X", "E2Ter", "E2*"]})
    fitted = CompactClinicalMutationFamily(gene_columns=("G",)).fit(frame)
    matrix = fitted.transform(frame).toarray()
    names = fitted.descriptor.feature_names
    column = names.index("truncating__G")
    assert matrix[:, column].tolist() == [1.0, 1.0, 1.0]
    nonsense = names.index("summary__nonsense_event_count")
    assert matrix[:, nonsense].tolist() == [1.0, 1.0, 1.0]
