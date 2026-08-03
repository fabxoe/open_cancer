from __future__ import annotations

from pathlib import Path

import pandas as pd

from open_cancer.abc_c_features import (
    fixed_pathway_burden_family,
    functional_role_burden_family,
    load_fixed_groups,
    pathway_mutation_type_family,
    pathway_mutation_type_fraction_family,
)
from open_cancer.feature_family import fit_transform_family_set, transform_checked


def knowledge_path() -> Path:
    return Path(__file__).resolve().parents[1] / "knowledge/abc_c_compact_groups_v1.json"


def canonical_pathway_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "knowledge/canonical_pathways_sanchez_vega_v1.json"
    )


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


def test_canonical_pathways_use_fixed_source_and_twenty_outputs() -> None:
    pathways, document = load_fixed_groups(canonical_pathway_path(), kind="pathways")
    assert tuple(pathways) == (
        "cell_cycle",
        "hippo",
        "myc",
        "notch",
        "nrf2",
        "pi3k",
        "rtk_ras",
        "tgf_beta",
        "tp53",
        "wnt",
    )
    assert document["source_sha256"] == (
        "a625675d03fa314eb27f3ab731524de13621a35aecd8edb7c67878f2d89ae07a"
    )
    frame = fixture_frame()
    fitted = fixed_pathway_burden_family(
        tuple(frame.columns[1:]), canonical_pathway_path()
    ).fit(frame)
    assert fitted.descriptor.output_dimension == 20
    assert fitted.descriptor.external_knowledge[0].license == "AGPL-3.0"


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


def test_pathway_mutation_types_count_affected_genes_once_per_type() -> None:
    frame = fixture_frame()
    frame.loc[0, "TP53"] = "R1* R2* R3H"
    fitted = pathway_mutation_type_family(
        tuple(frame.columns[1:]), knowledge_path()
    ).fit(frame)
    values = transform_checked(fitted, frame).toarray()[0]
    names = fitted.descriptor.feature_names

    assert values[names.index("sample__pathway_tp53__nonsense_gene_count")] == 1
    assert values[names.index("sample__pathway_tp53__missense_gene_count")] == 1
    assert values[names.index("sample__pathway_tp53__frameshift_gene_count")] == 0
    assert fitted.descriptor.output_dimension == 50
    assert fitted.descriptor.fit_scope == "stateless"


def test_pathway_mutation_types_keep_all_five_parser_categories() -> None:
    frame = fixture_frame()
    frame.loc[0, "TP53"] = "R1H R2R R3* R4fs 4_5AA>G*"
    fitted = pathway_mutation_type_family(
        tuple(frame.columns[1:]), canonical_pathway_path()
    ).fit(frame)
    values = transform_checked(fitted, frame).toarray()[0]
    names = fitted.descriptor.feature_names

    for mutation_type in ("missense", "synonymous", "nonsense", "frameshift", "complex"):
        assert values[
            names.index(f"sample__pathway_tp53__{mutation_type}_gene_count")
        ] == 1


def test_pathway_mutation_type_fractions_use_mutated_pathway_genes_as_denominator() -> None:
    frame = fixture_frame()
    frame.loc[0, "TP53"] = "R1H R2*"
    fitted = pathway_mutation_type_fraction_family(
        tuple(frame.columns[1:]), knowledge_path()
    ).fit(frame)
    values = transform_checked(fitted, frame).toarray()[0]
    names = fitted.descriptor.feature_names

    assert values[names.index("sample__pathway_tp53__missense_gene_fraction")] == 1
    assert values[names.index("sample__pathway_tp53__nonsense_gene_fraction")] == 1
    assert fitted.descriptor.name == "pathway_mutation_type_fraction"
    assert fitted.descriptor.output_dimension == 50


def test_pathway_mutation_type_fractions_return_zero_for_unmutated_pathway() -> None:
    frame = fixture_frame()
    frame.loc[0, "TP53"] = "WT"
    fitted = pathway_mutation_type_fraction_family(
        tuple(frame.columns[1:]), knowledge_path()
    ).fit(frame)
    values = transform_checked(fitted, frame).toarray()[0]
    names = fitted.descriptor.feature_names
    tp53_columns = [
        index for index, name in enumerate(names) if name.startswith("sample__pathway_tp53__")
    ]
    assert values[tp53_columns].sum() == 0
