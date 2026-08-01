from __future__ import annotations

from pathlib import Path

import pandas as pd

from open_cancer.abc_c_features import (
    fixed_pathway_burden_family,
    functional_role_burden_family,
    load_fixed_groups,
)
from open_cancer.feature_family import fit_transform_family_set, transform_checked


def knowledge_path() -> Path:
    return Path(__file__).resolve().parents[1] / "knowledge/abc_c_compact_groups_v1.json"


def fixture_frame() -> pd.DataFrame:
    pathways, _ = load_fixed_groups(knowledge_path(), kind="pathways")
    genes = sorted({gene for members in pathways.values() for gene in members})
    row = {gene: "WT" for gene in genes}
    row.update({"TP53": "R1*", "KRAS": "R2H", "PTEN": "R3fs"})
    return pd.DataFrame([{"ID": "T1", **row}])


def test_pathway_burden_counts_mutated_and_lof_genes() -> None:
    frame = fixture_frame()
    fitted = fixed_pathway_burden_family(
        tuple(frame.columns[1:]), knowledge_path()
    ).fit(frame)
    values = transform_checked(fitted, frame).toarray()[0]
    names = fitted.descriptor.feature_names

    assert values[names.index("sample__pathway_tp53__mutated_gene_count")] == 1
    assert values[names.index("sample__pathway_tp53__lof_gene_count")] == 1
    assert values[names.index("sample__pathway_rtk_ras__mutated_gene_count")] == 1
    assert values[names.index("sample__pathway_rtk_ras__lof_gene_count")] == 0
    assert values[names.index("sample__pathway_pi3k__lof_gene_count")] == 1
    assert fitted.descriptor.output_dimension == 20


def test_functional_roles_are_independently_switchable() -> None:
    frame = fixture_frame()
    family = functional_role_burden_family(tuple(frame.columns[1:]), knowledge_path())
    bundle = fit_transform_family_set(
        [family], fold_train=frame, validation=frame, test=frame
    )
    names = bundle.feature_names
    values = bundle.train.toarray()[0]

    assert values[names.index("sample__role_oncogene__mutated_gene_count")] == 1
    assert values[names.index("sample__role_oncogene__lof_gene_count")] == 0
    assert values[names.index("sample__role_tumor_suppressor__mutated_gene_count")] == 2
    assert values[names.index("sample__role_tumor_suppressor__lof_gene_count")] == 2
    assert set(bundle.registry) == {"functional_role_burden"}
    assert bundle.fitted_families[0].descriptor.external_knowledge[0].uri.startswith("https://")
