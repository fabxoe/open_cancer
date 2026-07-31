from __future__ import annotations

import json
from pathlib import Path

from scipy import sparse

from open_cancer.mutation_features import (
    FEATURE_FACTORY_VERSION,
    GENE_FEATURES,
    GLOBAL_FEATURES,
    EXPANDED_DISTRIBUTION_FEATURES,
    EXP050_FIXED_DISTRIBUTION_FEATURES,
    LOG_BURDEN_FEATURES,
    RESIDUE_POSITION_FEATURES,
    ROBUST_GLOBAL_FEATURES,
    SAMPLE_DISTRIBUTION_FEATURES,
    build_mutation_features,
    classify_mutation_token,
    feature_names,
    parse_mutation_cell,
    parse_mutation_token,
)


def test_classify_mutation_tokens() -> None:
    assert classify_mutation_token("S27N") == "missense"
    assert classify_mutation_token("R895R") == "synonymous"
    assert classify_mutation_token("R1538*") == "nonsense"
    assert classify_mutation_token("L1854fs") == "frameshift"
    assert classify_mutation_token("WQ288fs") == "frameshift"
    assert classify_mutation_token("468_469LG>F*") == "complex"


def test_parse_mutation_tokens_preserves_explicit_residue_information() -> None:
    substitution = parse_mutation_token("R132H")
    assert substitution.residue_positions == (132,)
    assert substitution.reference_amino_acid == "R"
    assert substitution.alternate_amino_acid == "H"
    assert substitution.token_shape == "substitution"

    frameshift = parse_mutation_token("WQ288fs")
    assert frameshift.residue_positions == (288,)
    assert frameshift.reference_amino_acid == "WQ"
    assert frameshift.alternate_amino_acid is None
    assert frameshift.token_shape == "frameshift"

    range_change = parse_mutation_token("468_469LG>F*")
    assert range_change.residue_positions == (468, 469)
    assert range_change.reference_amino_acid == "LG"
    assert range_change.alternate_amino_acid == "F*"
    assert range_change.token_shape == "range_change"
    assert range_change.is_complex is True

    leading_deletion = parse_mutation_token("-287fs")
    assert leading_deletion.residue_positions == (287,)
    assert leading_deletion.reference_amino_acid is None

    malformed = parse_mutation_token("UNKNOWN")
    assert malformed.residue_positions == ()
    assert malformed.mutation_type == "complex"


def test_parse_multi_token_cell_collects_all_positions() -> None:
    parsed = parse_mutation_cell("R132H 312_313QY>HH WT")
    assert parsed.token_count == 2
    assert parsed.residue_positions == (132, 312, 313)
    assert parsed.mutation_types == frozenset({"missense", "complex"})
    assert parsed.has_complex_token is True


def test_feature_names_are_stable() -> None:
    names = feature_names(["GENE1", "GENE2"])
    assert names[: len(GLOBAL_FEATURES)] == list(GLOBAL_FEATURES)
    assert len(names) == len(GLOBAL_FEATURES) + 2 * len(GENE_FEATURES)
    assert "GENE1__frameshift" in names
    assert "GENE2__missing" in names
    robust_names = feature_names(["GENE1"], include_robust_aggregates=True)
    assert robust_names[len(GLOBAL_FEATURES) : len(GLOBAL_FEATURES) + len(ROBUST_GLOBAL_FEATURES)] == list(
        ROBUST_GLOBAL_FEATURES
    )
    position_names = feature_names(
        ["GENE1"],
        selected_position_features=RESIDUE_POSITION_FEATURES,
    )
    assert position_names[-1] == "GENE1__min_residue_position"
    assert position_names[:-1] == feature_names(["GENE1"])


def test_build_sparse_train_test_features(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    test = tmp_path / "test.csv"
    output = tmp_path / "features"
    train.write_text(
        "ID,SUBCLASS,GENE1,GENE2\n"
        'T1,A,"S27N R28R",WT\n'
        "T2,B,L1854fs,\n",
        encoding="utf-8",
    )
    test.write_text(
        "ID,GENE1,GENE2\n"
        "E1,R1538*,468_469LG>F*\n",
        encoding="utf-8",
    )

    report = build_mutation_features(train, test, output)
    train_matrix = sparse.load_npz(output / "train_features.npz")
    test_matrix = sparse.load_npz(output / "test_features.npz")
    names = json.loads((output / "feature_names.json").read_text(encoding="utf-8"))

    assert train_matrix.shape == (2, len(names))
    assert test_matrix.shape == (1, len(names))
    assert report["feature_contract"]["target_used_for_features"] is False
    assert train_matrix[0, names.index("sample__total_variant_count")] == 2
    assert train_matrix[0, names.index("GENE1__missense")] == 1
    assert train_matrix[0, names.index("GENE1__synonymous")] == 1
    assert train_matrix[1, names.index("GENE2__missing")] == 1
    assert test_matrix[0, names.index("GENE1__nonsense")] == 1
    assert test_matrix[0, names.index("GENE2__complex")] == 1


def test_robust_aggregate_features_are_finite_and_safe(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    test = tmp_path / "test.csv"
    output = tmp_path / "features"
    train.write_text(
        "ID,SUBCLASS,GENE1,GENE2\n"
        "T1,A,WT,WT\n"
        'T2,B,"S27N R28R",\n',
        encoding="utf-8",
    )
    test.write_text("ID,GENE1,GENE2\nE1,R1538*,L1854fs\n", encoding="utf-8")

    build_mutation_features(
        train,
        test,
        output,
        include_robust_aggregates=True,
    )
    matrix = sparse.load_npz(output / "train_features.npz")
    names = json.loads((output / "feature_names.json").read_text(encoding="utf-8"))
    robust_indices = [names.index(name) for name in ROBUST_GLOBAL_FEATURES]
    robust = matrix[:, robust_indices].toarray()

    assert all(value == 0 for value in robust[0])
    assert all(value == value for value in robust.ravel())
    assert matrix[1, names.index("sample__missense_ratio")] == 0.5
    assert matrix[1, names.index("sample__synonymous_ratio")] == 0.5
    assert matrix[1, names.index("sample__multi_variant_gene_ratio")] == 1.0
    assert matrix[1, names.index("sample__missing_gene_ratio")] == 0.5


def test_log_burden_ablation_excludes_ratio_features(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    test = tmp_path / "test.csv"
    output = tmp_path / "features"
    train.write_text(
        "ID,SUBCLASS,GENE1,GENE2\n"
        'T1,A,"S27N R28R",WT\n'
        "T2,B,WT,WT\n",
        encoding="utf-8",
    )
    test.write_text(
        "ID,GENE1,GENE2\n"
        "E1,R1538*,L1854fs\n",
        encoding="utf-8",
    )

    report = build_mutation_features(
        train,
        test,
        output,
        selected_robust_aggregates=LOG_BURDEN_FEATURES,
    )
    matrix = sparse.load_npz(output / "train_features.npz")
    names = json.loads((output / "feature_names.json").read_text(encoding="utf-8"))

    assert report["feature_contract"]["robust_aggregate_features"] == list(
        LOG_BURDEN_FEATURES
    )
    assert all(name in names for name in LOG_BURDEN_FEATURES)
    assert not any(name.endswith("_ratio") for name in names)
    assert matrix[0, names.index("sample__mutated_gene_count_log1p")] > 0
    assert matrix[0, names.index("sample__total_variant_count_log1p")] > 0
    assert matrix[0, names.index("sample__multi_variant_gene_count_log1p")] > 0


def test_min_residue_position_feature_and_qc(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    test = tmp_path / "test.csv"
    output = tmp_path / "features"
    train.write_text(
        "ID,SUBCLASS,GENE1,GENE2\n"
        'T1,A,"R132H 312_313QY>HH",WT\n'
        "T2,B,WQ288fs,UNKNOWN\n",
        encoding="utf-8",
    )
    test.write_text(
        "ID,GENE1,GENE2\n"
        "E1,-287fs,468_469LG>F*\n",
        encoding="utf-8",
    )

    report = build_mutation_features(
        train,
        test,
        output,
        selected_position_features=("min_residue_position",),
    )
    matrix = sparse.load_npz(output / "train_features.npz")
    test_matrix = sparse.load_npz(output / "test_features.npz")
    names = json.loads((output / "feature_names.json").read_text(encoding="utf-8"))

    assert matrix[0, names.index("GENE1__min_residue_position")] == 132
    assert matrix[1, names.index("GENE1__min_residue_position")] == 288
    assert matrix[1, names.index("GENE2__min_residue_position")] == 0
    assert test_matrix[0, names.index("GENE1__min_residue_position")] == 287
    assert test_matrix[0, names.index("GENE2__min_residue_position")] == 468
    assert report["feature_count"] == (
        len(GLOBAL_FEATURES)
        + 2 * (len(GENE_FEATURES) + len(RESIDUE_POSITION_FEATURES))
    )
    assert report["feature_contract"]["feature_factory_version"] == FEATURE_FACTORY_VERSION
    assert report["feature_contract"]["position_features"] == [
        "min_residue_position"
    ]
    assert report["parsing_qc"]["train"]["mutation_tokens_total"] == 4
    assert report["parsing_qc"]["train"]["tokens_with_residue_positions"] == 3
    assert report["parsing_qc"]["train"]["tokens_without_residue_positions"] == 1
    assert report["parsing_qc"]["test"]["residue_position_parse_rate"] == 1.0
    assert (output / "feature_spec.json").is_file()
    assert (output / "feature_registry.json").is_file()
    assert (output / "parsing_qc.json").is_file()


def test_feature_cache_requires_matching_spec_and_output_hashes(
    tmp_path: Path,
) -> None:
    train = tmp_path / "train.csv"
    test = tmp_path / "test.csv"
    output = tmp_path / "features"
    train.write_text("ID,SUBCLASS,GENE1\nT1,A,R132H\n", encoding="utf-8")
    test.write_text("ID,GENE1\nE1,R132H\n", encoding="utf-8")

    first = build_mutation_features(train, test, output)
    second = build_mutation_features(train, test, output)
    assert first["cache"]["reused"] is False
    assert second["cache"]["reused"] is True
    assert first["feature_contract"]["feature_spec_sha256"] == second[
        "feature_contract"
    ]["feature_spec_sha256"]

    (output / "feature_names.json").write_text("tampered\n", encoding="utf-8")
    rebuilt = build_mutation_features(train, test, output)
    assert rebuilt["cache"]["reused"] is False
    assert json.loads(
        (output / "feature_names.json").read_text(encoding="utf-8")
    ) == feature_names(["GENE1"])


def test_expanded_sample_distribution_features(tmp_path: Path) -> None:
    train = tmp_path / "train.csv"
    test = tmp_path / "test.csv"
    output = tmp_path / "features"
    train.write_text(
        "ID,SUBCLASS,GENE1,GENE2,GENE3\n"
        'T1,A,"S27N R28R",R1538*,WT\n'
        "T2,B,WT,WT,WT\n",
        encoding="utf-8",
    )
    test.write_text(
        "ID,GENE1,GENE2,GENE3\n"
        "E1,L1854fs,468_469LG>F*,WT\n",
        encoding="utf-8",
    )

    report = build_mutation_features(
        train,
        test,
        output,
        selected_robust_aggregates=EXPANDED_DISTRIBUTION_FEATURES,
    )
    matrix = sparse.load_npz(output / "train_features.npz")
    names = json.loads((output / "feature_names.json").read_text(encoding="utf-8"))

    assert report["feature_contract"]["robust_aggregate_features"] == list(
        EXPANDED_DISTRIBUTION_FEATURES
    )
    assert matrix[0, names.index("sample__missense_gene_count")] == 1
    assert matrix[0, names.index("sample__synonymous_gene_count")] == 1
    assert matrix[0, names.index("sample__nonsense_gene_count")] == 1
    assert matrix[0, names.index("sample__truncating_count")] == 1
    assert matrix[0, names.index("sample__damaging_count")] == 2
    assert matrix[0, names.index("sample__mutation_type_diversity")] == 3
    assert matrix[0, names.index("sample__variants_per_mutated_gene_mean")] == 1.5
    assert matrix[0, names.index("sample__max_variants_per_gene")] == 2
    assert matrix[0, names.index("sample__single_variant_gene_count")] == 1
    assert matrix[1, names.index("sample__mutation_type_entropy")] == 0


def test_exp045_candidate_groups_cover_all_exp043_features_once() -> None:
    from open_cancer.nested_feature_selection import EXP043_CANDIDATE_GROUPS

    candidates = [
        feature
        for features in EXP043_CANDIDATE_GROUPS.values()
        for feature in features
    ]

    assert len(candidates) == len(EXPANDED_DISTRIBUTION_FEATURES) == 28
    assert len(set(candidates)) == len(candidates)
    assert set(candidates) == set(EXPANDED_DISTRIBUTION_FEATURES)


def test_exp050_fixed_features_are_supported_and_pre_registered() -> None:
    assert len(EXP050_FIXED_DISTRIBUTION_FEATURES) == 2
    assert len(set(EXP050_FIXED_DISTRIBUTION_FEATURES)) == 2
    assert set(EXP050_FIXED_DISTRIBUTION_FEATURES).issubset(
        SAMPLE_DISTRIBUTION_FEATURES
    )
