from pathlib import Path

import pandas as pd

from open_cancer.feature_family import transform_checked
from open_cancer.pathway_aggregation_features import (
    CELL_CYCLE_GENES,
    CellCyclePathwayFamily,
    cell_cycle_any_nonsilent_family,
    compute_any_nonsilent_flag,
    load_cell_cycle_knowledge,
)


def knowledge_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "knowledge/tcga_pancanatlas_table_s3_cell_cycle_v1.json"
    )


def test_cell_cycle_gene_list_has_fifteen_genes():
    assert len(CELL_CYCLE_GENES) == 15
    assert len(set(CELL_CYCLE_GENES)) == 15
    assert "TP53" not in CELL_CYCLE_GENES


def test_cell_cycle_gene_list_matches_committed_knowledge_file():
    genes_with_roles = load_cell_cycle_knowledge(knowledge_path())
    assert tuple(genes_with_roles.keys()) == CELL_CYCLE_GENES
    assert set(genes_with_roles.values()) == {"OG", "TSG"}


def test_compute_any_nonsilent_flag_detects_nonsilent_tokens():
    frame = pd.DataFrame(
        {
            "RB1": ["WT", "R251*", "WT", ""],
            "CCND1": ["WT", "WT", "P287T", "WT"],
            "OTHER_GENE": ["V600E", "WT", "WT", "WT"],
        }
    )
    flags = compute_any_nonsilent_flag(frame, genes=("RB1", "CCND1"))
    assert flags.tolist() == [0.0, 1.0, 1.0, 0.0]


def test_compute_any_nonsilent_flag_ignores_synonymous_only_rows():
    frame = pd.DataFrame({"RB1": ["A251A"], "CCND1": ["WT"]})
    flags = compute_any_nonsilent_flag(frame, genes=("RB1", "CCND1"))
    assert flags.tolist() == [0.0]


def test_compute_any_nonsilent_flag_rejects_unknown_gene():
    frame = pd.DataFrame({"RB1": ["WT"]})
    try:
        compute_any_nonsilent_flag(frame, genes=("RB1", "GHOSTGENE"))
    except ValueError as error:
        assert "GHOSTGENE" in str(error)
    else:
        raise AssertionError("expected ValueError for missing gene")


def _fixture_frame() -> pd.DataFrame:
    row = {gene: "WT" for gene in CELL_CYCLE_GENES}
    row["RB1"] = "R251*"
    return pd.DataFrame([row, {gene: "WT" for gene in CELL_CYCLE_GENES}])


def test_cell_cycle_family_matches_direct_compute_function():
    """The registered family must be bit-identical to the raw compute function
    already used by EXP-170's recorded OOF/metrics -- this is what lets the
    Feature Factory registration be added without retraining."""
    frame = _fixture_frame()
    direct = compute_any_nonsilent_flag(frame, CELL_CYCLE_GENES)
    fitted = cell_cycle_any_nonsilent_family(knowledge_path()).fit(frame)
    via_family = transform_checked(fitted, frame).toarray().ravel()
    assert via_family.tolist() == direct.tolist()


def test_cell_cycle_family_descriptor_and_provenance():
    fitted = cell_cycle_any_nonsilent_family(knowledge_path()).fit(_fixture_frame())
    descriptor = fitted.descriptor
    assert descriptor.name == "cellcycle_any_nonsilent"
    assert descriptor.fit_scope == "stateless"
    assert descriptor.feature_names == ("pathway__cellcycle_any_nonsilent",)
    assert len(descriptor.external_knowledge) == 1
    provenance = descriptor.external_knowledge[0]
    assert provenance.license.startswith("CC BY-NC-ND")
    assert provenance.uri == "https://doi.org/10.1016/j.cell.2018.03.035"
    assert len(provenance.sha256) == 64


def test_cell_cycle_family_rejects_unsupported_kind():
    family = CellCyclePathwayFamily(knowledge_path=knowledge_path(), kind="bogus")
    try:
        family.fit(_fixture_frame())
    except ValueError as error:
        assert "bogus" in str(error)
    else:
        raise AssertionError("expected ValueError for unsupported kind")
