import pandas as pd

from open_cancer.parser_v4_shap_priority import (
    build_parser_v4_event_table,
    build_priority_tables,
    build_shap_gene_evidence,
    extract_gene_from_feature,
)


GENES = ("IDH1", "TP53", "BRAF")


def _shap_tables():
    global_tables = {
        "A": pd.DataFrame(
            {
                "feature": ["IDH1__mutated", "hotspot__BRAF_600"],
                "share": [0.2, 0.1],
                "rank": [3, 80],
            }
        ),
        "B": pd.DataFrame(
            {
                "feature": ["IDH1__max_residue_position", "sample__total_variant_count"],
                "share": [0.3, 0.4],
                "rank": [2, 1],
            }
        ),
    }
    class_tables = {
        "A": pd.DataFrame(
            {
                "class": ["LGG", "GBMLGG"],
                "feature": ["IDH1__mutated", "IDH1__mutated"],
                "mean_abs_true_class_shap": [0.5, 0.4],
                "rank": [1, 2],
            }
        ),
        "B": pd.DataFrame(
            {
                "class": ["LGG"],
                "feature": ["IDH1__max_residue_position"],
                "mean_abs_true_class_shap": [0.6],
                "rank": [1],
            }
        ),
    }
    return global_tables, class_tables


def test_feature_gene_resolution_excludes_sample_and_pathway() -> None:
    assert extract_gene_from_feature("IDH1__mutated", known_genes=GENES) == "IDH1"
    assert extract_gene_from_feature("hotspot__BRAF_600", known_genes=GENES) == "BRAF"
    assert extract_gene_from_feature("sample__total_variant_count", known_genes=GENES) is None
    assert extract_gene_from_feature(
        "sample__pathway_tp53__mutated_gene_count", known_genes=GENES
    ) is None


def test_parser_event_table_groups_stop_aliases_but_preserves_raw_tokens() -> None:
    train = pd.DataFrame(
        {
            "ID": ["S1", "S2", "S3"],
            "SUBCLASS": ["LGG", "LGG", "GBMLGG"],
            "IDH1": ["R132H R172X R172Ter R172*", "R132H", "WT"],
            "TP53": ["WT", "R248Q", "R248Q"],
            "BRAF": ["WT", "WT", "V600E"],
        }
    )
    events = build_parser_v4_event_table(train, gene_columns=GENES)
    stop = events[events["raw_token"].isin(["R172X", "R172Ter", "R172*"])]
    assert stop["canonical_event_sha256"].nunique() == 1
    assert set(stop["raw_token"]) == {"R172X", "R172Ter", "R172*"}
    assert set(stop["event_type"]) == {"nonsense"}


def test_priority_votes_are_deterministic_and_patient_counts_do_not_inflate() -> None:
    train = pd.DataFrame(
        {
            "ID": ["S1", "S2", "S3"],
            "SUBCLASS": ["LGG", "LGG", "GBMLGG"],
            "IDH1": ["R132H R172X R172Ter R172*", "R132H", "WT"],
            "TP53": ["WT", "R248Q", "R248Q"],
            "BRAF": ["WT", "WT", "V600E"],
        }
    )
    global_tables, class_tables = _shap_tables()
    shap = build_shap_gene_evidence(
        global_tables, class_tables, known_genes=GENES
    )
    events = build_parser_v4_event_table(train, gene_columns=GENES)
    tables = build_priority_tables(
        events,
        shap_gene_evidence=shap,
        class_sample_counts={"LGG": 2, "GBMLGG": 1},
        total_samples=3,
    )
    idh1 = tables["gene_priority"].query("gene == 'IDH1'").iloc[0]
    assert idh1["token_count"] == 5
    assert idh1["patient_count"] == 2
    assert idh1["shap_priority_votes"] == 3
    repeated = build_priority_tables(
        events.sample(frac=1, random_state=7),
        shap_gene_evidence=shap,
        class_sample_counts={"LGG": 2, "GBMLGG": 1},
        total_samples=3,
    )
    assert tables["gene_priority"].to_dict("records") == repeated[
        "gene_priority"
    ].to_dict("records")
