import numpy as np
import pandas as pd

from open_cancer.compact_effect_features import (
    build_compact_effect_matrix,
)


def test_build_compact_effect_matrix_uses_shared_parser_semantics() -> None:
    frame = pd.DataFrame(
        {
            "GENE_A": ["WT", "A10V", "Q30*", "unusual"],
            "GENE_B": ["G20G", "A40fs", "A10V A11V", "WT"],
        }
    )

    matrix, names, metadata = build_compact_effect_matrix(
        frame,
        gene_columns=["GENE_A", "GENE_B"],
    )

    assert matrix.shape == (4, 8)
    assert matrix.format == "csr"
    expected_gene_a_names = [
        "GENE_A__compressed_effect_severity_max",
        "GENE_A__compressed_variant_count_1_or_2plus",
        "GENE_A__compressed_effect_diversity",
        "GENE_A__compressed_complex_or_unparsed",
    ]
    assert set(expected_gene_a_names).issubset(names)
    assert metadata["gene_count"] == 2

    dense = matrix.toarray()
    column_index = {name: index for index, name in enumerate(names)}
    severity_index = column_index[expected_gene_a_names[0]]
    count_index = column_index[expected_gene_a_names[1]]
    complex_index = column_index[expected_gene_a_names[3]]

    # WT has no compact feature.
    assert dense[0, severity_index] == 0
    assert dense[0, count_index] == 0
    assert dense[0, complex_index] == 0
    # A10V is missense: severity is present and count bucket is one.
    assert dense[1, severity_index] > 0
    assert dense[1, count_index] == 1
    # An unparsed/complex token is represented explicitly, not assigned an
    # unsupported biological severity.
    assert dense[3, complex_index] == 1
