from __future__ import annotations

import numpy as np
import pandas as pd

from open_cancer.canonical_mutation_events import (
    CANONICAL_PARSER_CONTRACT_KEY,
    canonical_event_cache_info,
    clear_canonical_event_caches,
    parse_canonical_gene_cell,
)
from open_cancer.sparse_gene_cells import (
    extract_non_wt_gene_cells,
    is_non_wt_cell,
)


def test_extract_non_wt_cells_preserves_gene_major_order_and_exact_values() -> None:
    frame = pd.DataFrame(
        {
            "G1": ["WT", " R1H ", None, "wt"],
            "G2": ["R2*", "", np.nan, " WT "],
            "G3": ["WT", "R3R R4H", "WT", "R5H"],
        }
    )
    result = extract_non_wt_gene_cells(frame, ("G1", "G2", "G3"), block_size=2)
    assert result.row_indices.tolist() == [1, 0, 1, 3]
    assert result.gene_indices.tolist() == [0, 1, 2, 2]
    assert result.values == (" R1H ", "R2*", "R3R R4H", "R5H")


def test_non_wt_predicate_handles_case_whitespace_and_missing() -> None:
    assert not is_non_wt_cell("WT")
    assert not is_non_wt_cell(" wt ")
    assert not is_non_wt_cell("")
    assert not is_non_wt_cell(None)
    assert is_non_wt_cell("R132H")


def test_empty_and_missing_column_contract() -> None:
    result = extract_non_wt_gene_cells(pd.DataFrame({"G": ["WT"]}), ("G",))
    assert len(result) == 0
    assert result.row_indices.dtype == np.int32
    try:
        extract_non_wt_gene_cells(pd.DataFrame({"G": ["WT"]}), ("MISSING",))
    except ValueError as error:
        assert "MISSING" in str(error)
    else:
        raise AssertionError("missing gene column must fail")


def test_cache_key_includes_feature_version_and_column_order() -> None:
    frame = pd.DataFrame({"G1": ["R1H"], "G2": ["WT"]})
    first = extract_non_wt_gene_cells(
        frame, ("G1", "G2"), feature_version="feature-a"
    )
    reordered = extract_non_wt_gene_cells(
        frame, ("G2", "G1"), feature_version="feature-a"
    )
    changed = extract_non_wt_gene_cells(
        frame, ("G1", "G2"), feature_version="feature-b"
    )
    assert first.cache_key != reordered.cache_key
    assert first.cache_key != changed.cache_key
    assert first.feature_version == "feature-a"
    assert first.parser_contract_key


def test_compiled_event_cache_records_contract_and_hits() -> None:
    clear_canonical_event_caches()
    first = parse_canonical_gene_cell("R582X E28del")
    second = parse_canonical_gene_cell("R582X E28del")
    info = canonical_event_cache_info()
    assert first == second
    assert info["parser_contract_key"] == CANONICAL_PARSER_CONTRACT_KEY
    assert info["cell"]["hits"] == 1
    assert info["cell"]["misses"] == 1
