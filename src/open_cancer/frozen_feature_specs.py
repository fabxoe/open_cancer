"""Materialize the frozen ABC v1/v2 feature specifications."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import yaml
from scipy import sparse

from open_cancer.abc_a_features import AminoAcidChangeFamily
from open_cancer.abc_c_features import fixed_pathway_burden_family
from open_cancer.constants import CLASS_LABELS
from open_cancer.feature_family import (
    build_family_registry,
    remove_semantically_equivalent_features,
    transform_checked,
    FoldFeatureBundle,
)
from open_cancer.hashing import sha256_file, sha256_lines
from open_cancer.hotspot_features import build_hotspot_augmented_features, resolve_hotspot_config
from open_cancer.mutation_features import (
    resolve_position_features_from_config,
    resolve_position_options_from_config,
)

FeatureSpecName = Literal["v1", "v2-performance", "v2-diversity"]
# Re-pinned 2026-08-06 (#596/#597): live materialization of EXP-094's base
# feature spec against the current codebase no longer reproduces the
# original 1fba3a7dac9f9b2a76deb5bec4c1099f650153b82c64d48e476dc1f2f84f3ed3
# hash -- mutation-type/hotspot token classification changed underneath it
# from the parser semantic fixes landed after EXP-094 (see PROJECT_CONTEXT.md
# "Parser lineage 계약"). Raw train/test SHA-256 still match data/README.md
# canonical values, so the drift is in code, not data. EXP-094/123/125/127's
# own saved reproducibility manifests are untouched (historical provenance is
# never retroactively edited); this constant only gates *new* materializations
# going forward.
FROZEN_BASE_SHA256 = "8f564cc18b3bcef8c59879144f19ff0d62ac3d5ee13ea6887ce59d265d8f843a"


class FrozenFeatureSpecError(ValueError):
    """Raised when a frozen Feature Spec is missing or changed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise FrozenFeatureSpecError(message)


@dataclass(frozen=True)
class ResolvedFrozenFeatureSpec:
    name: FeatureSpecName
    base_experiment: str
    base_feature_spec_sha256: str
    families: tuple[str, ...]
    source_config: Path
    evidence_experiment: str


def resolve_frozen_feature_spec(root: Path, name: str) -> ResolvedFrozenFeatureSpec:
    """Resolve one immutable v1/v2 name from the committed freeze document."""
    _require(name in {"v1", "v2-performance", "v2-diversity"}, f"알 수 없는 Feature Spec: {name}")
    freeze_path = root / "configs" / "abc_stack_feature_spec_v2.yaml"
    document = yaml.safe_load(freeze_path.read_text(encoding="utf-8"))
    _require(document["status"] == "FROZEN", "ABC Feature Spec v2가 동결 상태가 아닙니다.")
    base = document["baseline"]
    _require(base["experiment_id"] == "EXP-094", "동결 baseline이 EXP-094가 아닙니다.")
    _require(
        base["feature_spec_sha256"] == FROZEN_BASE_SHA256,
        "EXP-094 Feature Spec 해시가 변경됐습니다.",
    )
    if name == "v1":
        return ResolvedFrozenFeatureSpec(
            name="v1",
            base_experiment="EXP-094",
            base_feature_spec_sha256=FROZEN_BASE_SHA256,
            families=(),
            source_config=root / "configs" / "exp094_feature_spec_v1.yaml",
            evidence_experiment="EXP-094",
        )
    section = document[name.replace("-", "_")]
    source_config = root / section["source_config"]
    _require(source_config.is_file(), f"Feature Spec source config가 없습니다: {source_config}")
    return ResolvedFrozenFeatureSpec(
        name=name,  # type: ignore[arg-type]
        base_experiment=section["base"],
        base_feature_spec_sha256=FROZEN_BASE_SHA256,
        families=tuple(section["families"]),
        source_config=source_config,
        evidence_experiment=section["evidence_experiment"],
    )


def _build_family(root: Path, family_name: str, genes: tuple[str, ...]):
    if family_name == "fixed_pathway_burden":
        return fixed_pathway_burden_family(
            genes,
            root / "knowledge" / "canonical_pathways_sanchez_vega_v1.json",
        )
    if family_name == "amino_acid_change":
        return AminoAcidChangeFamily(
            gene_columns=genes,
            property_path=root / "knowledge" / "amino_acid_properties_v1.json",
        )
    raise FrozenFeatureSpecError(f"동결되지 않은 family입니다: {family_name}")


def materialize_frozen_feature_spec(
    *,
    root: Path,
    name: FeatureSpecName,
    output_dir: Path,
    train_path: Path,
    test_path: Path,
) -> dict[str, Any]:
    """Build one frozen sparse matrix pair and a complete identity manifest."""
    resolved = resolve_frozen_feature_spec(root, name)
    source_config = yaml.safe_load(resolved.source_config.read_text(encoding="utf-8"))
    hotspots, _, _ = resolve_hotspot_config(source_config.get("hotspots", {}))
    base_dir = output_dir / "base_feature_spec_v1"
    base_report = build_hotspot_augmented_features(
        train_path,
        test_path,
        base_dir,
        hotspots=hotspots,
        base_feature_options={
            "selected_robust_aggregates": tuple(
                source_config.get("features", {}).get("robust_aggregates", [])
            ),
            "selected_position_features": resolve_position_features_from_config(source_config),
            **resolve_position_options_from_config(source_config),
        },
    )
    actual_base_sha256 = base_report["feature_contract"]["feature_spec_sha256"]
    _require(
        actual_base_sha256 == resolved.base_feature_spec_sha256,
        "materialize된 EXP-094 Feature Spec 해시가 동결값과 다릅니다.",
    )
    train_matrix = sparse.load_npz(base_dir / "train_features.npz").tocsr()
    test_matrix = sparse.load_npz(base_dir / "test_features.npz").tocsr()
    feature_names = tuple(
        json.loads((base_dir / "feature_names.json").read_text(encoding="utf-8"))
    )
    registry: dict[str, Any] = {}
    dropped: dict[str, str] = {}
    if resolved.families:
        train = pd.read_csv(train_path, dtype=str, keep_default_na=False)
        test = pd.read_csv(test_path, dtype=str, keep_default_na=False)
        genes = tuple(column for column in train.columns if column not in {"ID", "SUBCLASS"})
        _require(tuple(test.columns[1:]) == genes, "train/test 유전자 순서가 다릅니다.")
        fitted = tuple(_build_family(root, family, genes).fit(train.iloc[:1]) for family in resolved.families)
        extra_train = sparse.hstack(
            [transform_checked(family, train) for family in fitted],
            format="csr",
        )
        extra_test = sparse.hstack(
            [transform_checked(family, test) for family in fitted],
            format="csr",
        )
        extra_names = tuple(name for family in fitted for name in family.descriptor.feature_names)
        bundle = FoldFeatureBundle(
            train=extra_train,
            validation=extra_train[:1],
            test=extra_test,
            fitted_families=fitted,
            feature_names=extra_names,
            registry=build_family_registry(fitted),
        )
        bundle, dropped = remove_semantically_equivalent_features(
            bundle,
            train_matrix,
            feature_names,
        )
        train_matrix = sparse.hstack([train_matrix, bundle.train], format="csr")
        test_matrix = sparse.hstack([test_matrix, bundle.test], format="csr")
        feature_names = (*feature_names, *bundle.feature_names)
        registry = bundle.registry
    _require(train_matrix.shape[1] == len(feature_names), "train feature 이름 수 불일치")
    _require(test_matrix.shape[1] == len(feature_names), "test feature 이름 수 불일치")
    output_dir.mkdir(parents=True, exist_ok=True)
    train_output = output_dir / "train_features.npz"
    test_output = output_dir / "test_features.npz"
    names_output = output_dir / "feature_names.json"
    manifest_output = output_dir / "feature_spec_manifest.json"
    sparse.save_npz(train_output, train_matrix, compressed=True)
    sparse.save_npz(test_output, test_matrix, compressed=True)
    names_output.write_text(json.dumps(feature_names, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest = {
        "name": resolved.name,
        "base_experiment": resolved.base_experiment,
        "evidence_experiment": resolved.evidence_experiment,
        "base_feature_spec_sha256": resolved.base_feature_spec_sha256,
        "families": list(resolved.families),
        "family_registry": registry,
        "semantic_duplicates_dropped": dropped,
        "class_order": list(CLASS_LABELS),
        "source_config": str(resolved.source_config.relative_to(root)),
        "source_config_sha256": sha256_file(resolved.source_config),
        "train_input_sha256": sha256_file(train_path),
        "test_input_sha256": sha256_file(test_path),
        "train_shape": list(train_matrix.shape),
        "test_shape": list(test_matrix.shape),
        "feature_names_sha256": sha256_lines(feature_names),
        "outputs": {
            "train_features": {"path": str(train_output), "sha256": sha256_file(train_output)},
            "test_features": {"path": str(test_output), "sha256": sha256_file(test_output)},
            "feature_names": {"path": str(names_output), "sha256": sha256_file(names_output)},
        },
    }
    manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest
