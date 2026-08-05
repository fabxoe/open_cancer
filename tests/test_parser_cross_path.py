import pandas as pd

from open_cancer.canonical_mutation_events import (
    canonical_event_sha256,
    parse_canonical_gene_cell,
    route_canonical_token,
)
from open_cancer.mutation_features import MUTATION_TYPES
from open_cancer.parser_compatibility_features import (
    ParserCompatibilityFamily,
    compatibility_family,
)
from open_cancer.parser_native_features import native_consequence, parse_native_gene_cell


def test_stop_aliases_share_one_canonical_identity() -> None:
    hashes = {
        canonical_event_sha256(route_canonical_token(token))
        for token in ("R213*", "R213X", "R213Ter")
    }
    assert len(hashes) == 1


def test_native_and_compatibility_paths_share_canonical_events() -> None:
    examples = (
        "R132H",
        "D623D",
        "R213X",
        "WQ288fs",
        "G235_G238del",
        "S261_P262insQEPPDTTS",
        "E1117delinsGGRRIIK",
        "1436_1437SI>RF",
        "-762fs",
    )
    for token in examples:
        cell = parse_canonical_gene_cell(token)
        assert len(cell.events) == 1
        event = cell.events[0]
        assert native_consequence(event)
        assert compatibility_family(event) in MUTATION_TYPES
        assert parse_native_gene_cell(token).token_count == 1


def test_compatibility_adapter_matches_historical_names_and_dimensions() -> None:
    frame = pd.DataFrame(
        {
            "A": ["R132H R213X", "WT"],
            "B": ["WQ288fs E28del", "D623D"],
        }
    )
    fitted = ParserCompatibilityFamily(("A", "B")).fit(frame)
    names = fitted.descriptor.feature_names
    assert names[:5] == tuple(f"sample__{name}_count" for name in MUTATION_TYPES)
    assert names[5:] == tuple(
        f"{gene}__{name}" for gene in ("A", "B") for name in MUTATION_TYPES
    )
    assert fitted.base_feature_names_to_drop == names
    matrix = fitted.transform(frame).toarray()
    index = {name: i for i, name in enumerate(names)}
    assert matrix[0, index["sample__missense_count"]] == 1
    assert matrix[0, index["sample__nonsense_count"]] == 1
    assert matrix[0, index["sample__frameshift_count"]] == 1
    assert matrix[0, index["sample__complex_count"]] == 1
    assert matrix[1, index["sample__synonymous_count"]] == 1
    assert matrix[0, index["A__missense"]] == 1
    assert matrix[0, index["B__complex"]] == 1
