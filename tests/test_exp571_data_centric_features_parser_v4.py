from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from exp571_data_centric_feature_builders import (  # noqa: E402
    EVENT_SPAN_NAMES,
    PARSER_QC_NAMES,
    mutation_tokens,
    summarize_frame,
    summarize_tokens,
)
from run_exp571_data_centric_features_parser_v4 import (  # noqa: E402
    ALLOWED_VERIFICATION_FIELDS,
)


def test_mutation_tokens_preserve_blank_and_wt_policy() -> None:
    assert mutation_tokens("") == ()
    assert mutation_tokens("WT") == ()
    assert mutation_tokens(None) == ()
    assert mutation_tokens("A10V Q20*") == ("A10V", "Q20*")


def test_parser_qc_ratios_are_bounded() -> None:
    qc, _span = summarize_tokens(("A10V", "Q20*", "unusual"))
    assert qc.shape == (len(PARSER_QC_NAMES),)
    assert np.all((qc[:4] >= 0.0) & (qc[:4] <= 1.0))
    assert np.isclose(qc[:4].sum(), 1.0)


def test_event_span_uses_within_event_endpoints() -> None:
    _qc, span = summarize_tokens(("A10_A15del", "Q20R"))
    assert span.shape == (len(EVENT_SPAN_NAMES),)
    assert span[0] >= 1
    assert span[5] > 0


def test_summarize_frame_is_row_aligned_and_stateless() -> None:
    frame = pd.DataFrame(
        {
            "ID": ["P1", "P2"],
            "SUBCLASS": ["ACC", "BRCA"],
            "GENE_A": ["A10V", "WT"],
            "GENE_B": ["A10_A15del", "Q20*"],
        }
    )
    qc, span = summarize_frame(frame, ("GENE_A", "GENE_B"))
    assert qc.shape == (2, len(PARSER_QC_NAMES))
    assert span.shape == (2, len(EVENT_SPAN_NAMES))
    repeated_qc, repeated_span = summarize_frame(
        frame.iloc[::-1].reset_index(drop=True), ("GENE_A", "GENE_B")
    )
    assert np.allclose(qc.toarray(), repeated_qc.toarray()[::-1])
    assert np.allclose(span.toarray(), repeated_span.toarray()[::-1])


def test_reproducibility_verification_fields_match_current_schema() -> None:
    allowed = set(ALLOWED_VERIFICATION_FIELDS)
    assert "data_hashes_match" in allowed
    assert "submission_sha256_match" in allowed
    assert "passed" in allowed
    assert "verified_at" not in allowed
    assert "original_submission_sha256" not in allowed
    assert "reproduced_submission_sha256" not in allowed
    assert "test_probability_max_abs_diff" not in allowed
