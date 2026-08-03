#!/usr/bin/env python
"""Normalize and connect original artifacts for Issue #260 Release bundles."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from open_cancer.hashing import sha256_file


ROOT = Path(__file__).resolve().parents[1]
SLUGS = {
    "EXP-209": "exp209_lightgbm_v2_performance",
    "EXP-229": "exp229_pathway_mutation_types",
    "EXP-253": "exp253_lightgbm_xgboost_blend",
}


def manifest(experiment_id: str) -> tuple[Path, dict[str, Any]]:
    path = ROOT / "reproducibility" / SLUGS[experiment_id] / "artifact_manifest.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def verified_copy(record: dict[str, Any], kind: str | None = None) -> dict[str, Any]:
    copied = deepcopy(record)
    path = ROOT / copied["path"]
    if not path.is_file():
        raise FileNotFoundError(copied["path"])
    actual = sha256_file(path)
    if actual != copied["sha256"]:
        raise ValueError(f"SHA-256 불일치: {copied['path']}")
    copied["size_bytes"] = path.stat().st_size
    copied["storage_uri"] = None
    if kind is not None:
        copied["kind"] = kind
    return copied


def by_kind(value: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [item for item in value["artifacts"] if item["kind"] == kind]


def first(value: dict[str, Any], kind: str) -> dict[str, Any]:
    matches = by_kind(value, kind)
    if len(matches) != 1:
        raise ValueError(f"{value['experiment_id']} {kind} 개수: {len(matches)}")
    return matches[0]


def main() -> None:
    path209, exp209 = manifest("EXP-209")
    path229, exp229 = manifest("EXP-229")
    path253, exp253 = manifest("EXP-253")

    for item in exp209["artifacts"]:
        if item["kind"].startswith("checkpoint_fold_"):
            item["kind"] = "checkpoint"
        elif item["kind"] == "oof":
            item["kind"] = "oof_probability"
        verified_copy(item)

    for item in exp229["artifacts"]:
        verified_copy(item)
    for item in exp253["artifacts"]:
        verified_copy(item)

    connected: list[dict[str, Any]] = []
    for parent in (exp209, exp229):
        connected.extend(verified_copy(item, "checkpoint") for item in by_kind(parent, "checkpoint"))
        connected.append(verified_copy(first(parent, "oof_probability"), "component_oof_probability"))
        connected.append(verified_copy(first(parent, "test_probability"), "component_test_probability"))
        connected.append(verified_copy(first(parent, "resolved_config"), "component_resolved_config"))

    base = [item for item in exp253["artifacts"] if item["kind"] != "release_bundle"]
    exp253["artifacts"] = base + connected

    for path, value in ((path209, exp209), (path229, exp229), (path253, exp253)):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({key: SLUGS[key] for key in SLUGS}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
