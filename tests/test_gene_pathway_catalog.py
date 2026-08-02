from open_cancer.gene_pathway_catalog import (
    build_catalog_table,
    cross_validate_hotspots,
    parse_hotspot_positions,
    summarize_pathway_coverage,
    PathwayRow,
)


def test_parse_hotspot_positions_handles_table_s3_formats():
    assert parse_hotspot_positions("R80, H83") == (80, 83)
    assert parse_hotspot_positions("X159_splice, G72") == (159, 72)
    assert parse_hotspot_positions("M1") == (1,)
    assert parse_hotspot_positions("-") == ()
    assert parse_hotspot_positions(None) == ()
    assert parse_hotspot_positions("") == ()


def test_build_catalog_table_flags_panel_and_whitelist_membership():
    rows = [
        PathwayRow("TP53", "TP53", "TSG", (175, 248)),
        PathwayRow("GHOSTGENE", "TP53", "OG", ()),
    ]
    table = build_catalog_table(
        rows,
        panel_genes=frozenset({"TP53"}),
        cosmic_whitelist_genes=frozenset({"TP53"}),
    )
    assert table[0]["in_panel"] is True
    assert table[0]["in_cosmic_whitelist"] is True
    assert table[0]["hotspot_positions"] == "175;248"
    assert table[1]["in_panel"] is False
    assert table[1]["hotspot_positions"] == ""


def test_summarize_pathway_coverage_computes_per_pathway_stats():
    rows = [
        PathwayRow("TP53", "TP53", "TSG", (175,)),
        PathwayRow("MDM2", "TP53", "OG", ()),
        PathwayRow("GHOSTGENE", "TP53", "Unknown", ()),
    ]
    table = build_catalog_table(
        rows,
        panel_genes=frozenset({"TP53", "MDM2"}),
        cosmic_whitelist_genes=frozenset({"TP53"}),
    )
    summary = {row["pathway"]: row for row in summarize_pathway_coverage(table)}
    tp53 = summary["TP53"]
    assert tp53["gene_count"] == 3
    assert tp53["in_panel_count"] == 2
    assert tp53["panel_coverage_pct"] == round(100 * 2 / 3, 4)
    assert tp53["og_count"] == 1
    assert tp53["tsg_count"] == 1
    assert tp53["unknown_og_tsg_count"] == 1
    assert tp53["in_cosmic_whitelist_count"] == 1
    assert summary["WNT"]["gene_count"] == 0
    assert summary["WNT"]["panel_coverage_pct"] == 0.0


def test_cross_validate_hotspots_matches_gene_and_position():
    rows = [
        PathwayRow("TP53", "TP53", "TSG", (175, 248)),
        PathwayRow("BRAF", "RTK RAS", "OG", (601,)),
    ]
    table = build_catalog_table(
        rows, panel_genes=frozenset(), cosmic_whitelist_genes=frozenset()
    )
    known_hotspots = (
        ("TP53", 175, "R"),
        ("TP53", 248, "R"),
        ("BRAF", 600, "V"),
        ("IDH1", 132, "R"),
    )
    result = cross_validate_hotspots(table, known_hotspots)
    assert result["total_known_hotspots"] == 4
    assert result["matched_count"] == 2
    assert result["position_unmatched_count"] == 1
    assert result["gene_absent_count"] == 1
    assert result["position_unmatched"][0]["gene"] == "BRAF"
    assert result["position_unmatched"][0]["position"] == 600
    assert result["gene_absent"][0]["gene"] == "IDH1"
