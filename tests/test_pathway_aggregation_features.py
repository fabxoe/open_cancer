import pandas as pd

from open_cancer.pathway_aggregation_features import (
    CELL_CYCLE_GENES,
    compute_any_nonsilent_flag,
)


def test_cell_cycle_gene_list_has_fifteen_genes():
    assert len(CELL_CYCLE_GENES) == 15
    assert len(set(CELL_CYCLE_GENES)) == 15
    assert "TP53" not in CELL_CYCLE_GENES


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
