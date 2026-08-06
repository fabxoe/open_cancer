from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from exp640_hierarchical_event_builders import (  # noqa: E402
    EVENT_FAMILIES,
    EVENT_FEATURE_NAMES,
    QC_FEATURE_NAMES,
    hierarchical_event_family,
    summarize_hierarchical_events,
)
from open_cancer.mutation_parser_contract import route_protein_mutation  # noqa: E402
from audit_exp640_notation_shift import fitted_subgroup_masks  # noqa: E402


def _family(token: str, gene: str = "TP53") -> str:
    return hierarchical_event_family(
        route_protein_mutation(token), gene_symbol=gene
    )


def test_hierarchical_family_aliases_and_semantics() -> None:
    assert _family("R582*") == "stop_gain"
    assert _family("R582X") == "stop_gain"
    assert _family("R582Ter") == "stop_gain"
    assert _family("R132H") == "missense"
    assert _family("R132R") == "no_change"
    assert _family("L452Wfs") == "frameshift"
    assert _family("E28del") == "deletion"
    assert _family("E1117delinsGGRRIIK") == "delins_or_complex_replacement"
    assert _family("S261_P262insQEPPDTTS") in {"insertion", "duplication"}


def test_summary_counts_genes_ratios_and_qc() -> None:
    frame = pd.DataFrame(
        {
            "ID": ["P1", "P2"],
            "SUBCLASS": ["ACC", "BRCA"],
            "TP53": ["R582X R132H", "WT"],
            "EGFR": ["R132R", "E28del"],
        }
    )
    event, qc = summarize_hierarchical_events(frame, ("TP53", "EGFR"))
    assert event.shape == (2, len(EVENT_FEATURE_NAMES))
    assert qc.shape == (2, len(QC_FEATURE_NAMES))
    assert np.isfinite(event.toarray()).all()
    assert np.isfinite(qc.toarray()).all()

    names = {name: index for index, name in enumerate(EVENT_FEATURE_NAMES)}
    values = event.toarray()
    assert values[0, names["exp640__stop_gain_event_count"]] == 1
    assert values[0, names["exp640__missense_event_count"]] == 1
    assert values[0, names["exp640__no_change_event_count"]] == 1
    assert values[1, names["exp640__deletion_event_count"]] == 1
    assert np.isclose(
        sum(
            values[0, names[f"exp640__{family}_event_ratio"]]
            for family in EVENT_FAMILIES
        ),
        1.0,
    )


def test_row_reordering_preserves_row_alignment() -> None:
    frame = pd.DataFrame(
        {
            "ID": ["P1", "P2"],
            "SUBCLASS": ["ACC", "BRCA"],
            "TP53": ["R582*", "R132H"],
            "EGFR": ["WT", "E28del"],
        }
    )
    event, qc = summarize_hierarchical_events(frame, ("TP53", "EGFR"))
    reversed_event, reversed_qc = summarize_hierarchical_events(
        frame.iloc[::-1].reset_index(drop=True), ("TP53", "EGFR")
    )
    assert np.allclose(event.toarray(), reversed_event.toarray()[::-1])
    assert np.allclose(qc.toarray(), reversed_qc.toarray()[::-1])


def test_notation_shift_masks_are_fit_from_outer_train_only() -> None:
    train_event = np.zeros((4, len(EVENT_FAMILIES) * 3 + 7), dtype=np.float32)
    valid_event = np.zeros((2, len(EVENT_FAMILIES) * 3 + 7), dtype=np.float32)
    train_qc = np.zeros((4, 10), dtype=np.float32)
    valid_qc = np.zeros((2, 10), dtype=np.float32)
    train_event[:, 0] = [1, 2, 3, 4]
    valid_event[:, 0] = [0, 1000]
    train_qc[:, 9] = [0.0, 0.1, 0.2, 0.3]
    valid_qc[:, 9] = [0.0, 999.0]

    masks, metadata = fitted_subgroup_masks(
        train_event, valid_event, train_qc, valid_qc
    )

    assert metadata["burden_q75"] == pytest.approx(3.25)
    assert metadata["multi_token_ratio_q75"] == pytest.approx(0.225)
    assert masks["burden_high"].tolist() == [False, True]
    assert masks["multi_token_high"].tolist() == [False, True]
