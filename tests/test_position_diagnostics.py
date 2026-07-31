import json
from pathlib import Path

import numpy as np
from scipy import sparse

from open_cancer.position_diagnostics import diagnose_position_artifacts


def _write_fixture(feature_dir: Path, *, introduce_mismatch: bool = False) -> None:
    feature_dir.mkdir(parents=True)
    names = [
        "GENE1__mutated",
        "GENE1__max_residue_position",
        "GENE1__residue_position_observed",
        "GENE2__mutated",
        "GENE2__max_residue_position",
        "GENE2__residue_position_observed",
    ]
    (feature_dir / "feature_names.json").write_text(
        json.dumps(names) + "\n", encoding="utf-8"
    )
    train = np.asarray(
        [
            [1, 12, 1, 0, 0, 0],
            [0, 0, 0, 1, 35, 1],
        ],
        dtype=np.float32,
    )
    test = np.asarray([[1, 18, 0 if introduce_mismatch else 1, 0, 0, 0]], dtype=np.float32)
    sparse.save_npz(feature_dir / "train_features.npz", sparse.csr_matrix(train))
    sparse.save_npz(feature_dir / "test_features.npz", sparse.csr_matrix(test))
    parsing_qc = {
        "train": {
            "non_wt_gene_cells": 2,
            "mutation_tokens_total": 2,
            "tokens_with_residue_positions": 2,
            "tokens_without_residue_positions": 0,
            "complex_tokens": 0,
            "multi_position_tokens": 0,
            "residue_position_parse_rate": 1.0,
            "complex_token_ratio": 0.0,
        },
        "test": {
            "non_wt_gene_cells": 1,
            "mutation_tokens_total": 1,
            "tokens_with_residue_positions": 1,
            "tokens_without_residue_positions": 0,
            "complex_tokens": 1,
            "multi_position_tokens": 1,
            "residue_position_parse_rate": 1.0,
            "complex_token_ratio": 1.0,
        },
    }
    (feature_dir / "parsing_qc.json").write_text(
        json.dumps(parsing_qc) + "\n", encoding="utf-8"
    )


def test_detects_exact_indicator_duplicate_without_labels(tmp_path: Path) -> None:
    feature_dir = tmp_path / "features"
    _write_fixture(feature_dir)

    report = diagnose_position_artifacts(feature_dir)

    assert report["target_or_labels_used"] is False
    assert report["feature_contract"][
        "indicator_exactly_duplicates_mutation_presence"
    ] is True
    assert report["feature_contract"]["indicator_interpretation"] == (
        "duplicate_feature_weighting_not_missingness_resolution"
    )
    assert report["splits"]["train"]["indicator_presence_mismatches"] == 0
    assert report["splits"]["test"]["p_zero_given_position_observed"] == 0.0


def test_reports_indicator_mismatch_and_positive_without_observed(tmp_path: Path) -> None:
    feature_dir = tmp_path / "features"
    _write_fixture(feature_dir, introduce_mismatch=True)

    report = diagnose_position_artifacts(feature_dir)

    assert report["feature_contract"][
        "indicator_exactly_duplicates_mutation_presence"
    ] is False
    assert report["splits"]["test"]["indicator_presence_mismatches"] == 1
    assert report["splits"]["test"]["positive_position_without_observed"] == 1


def test_committed_semantics_qc_is_target_free_and_portable() -> None:
    report = json.loads(
        Path("reports/analysis/residue_position_semantics_qc.json").read_text(
            encoding="utf-8"
        )
    )

    assert report["target_or_labels_used"] is False
    assert report["feature_contract"][
        "indicator_exactly_duplicates_mutation_presence"
    ] is True
    assert all(
        split["indicator_presence_mismatches"] == 0
        for split in report["splits"].values()
    )
    for artifact in report["inputs"].values():
        assert not Path(artifact["path"]).is_absolute()
        assert len(artifact["sha256"]) == 64
