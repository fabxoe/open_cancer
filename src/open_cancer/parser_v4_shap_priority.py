"""Parser-v4 event counts combined with validation-only SHAP gene priors.

The module deliberately keeps two evidence sources separate:

* TreeSHAP tables provide a *gene-level prior* from historical adopted models.
* Parser-v4 counts describe observed train support and class concentration.

The resulting ``priority_votes`` are transparent triage votes, not a learned
importance score and never a claim of biological causality.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

from open_cancer.canonical_mutation_events import (
    canonical_event_sha256,
    parse_canonical_gene_cell,
)
from open_cancer.parser_semantic_completeness import semantic_subfamily_key
from open_cancer.sparse_gene_cells import extract_non_wt_gene_cells


PARSER_V4_SHAP_PRIORITY_VERSION = "1.0.0"
PRIORITY_VOTE_COLUMNS = (
    "vote_shap_global_top100",
    "vote_shap_repeated_models",
    "vote_shap_class_top_repeated",
    "vote_patient_support",
    "vote_parse_complete",
    "vote_class_specific",
)


def extract_gene_from_feature(
    feature: str, *, known_genes: Sequence[str]
) -> str | None:
    """Resolve a gene symbol from a historical model feature name.

    Pathway and sample aggregate features intentionally return ``None``.
    Hotspot names use ``hotspot__GENE_position`` while ordinary gene features
    use ``GENE__family``.
    """

    genes = set(known_genes)
    if "__" in feature:
        prefix = feature.split("__", 1)[0]
        if prefix in genes:
            return prefix
    if feature.startswith("hotspot__"):
        suffix = feature.removeprefix("hotspot__")
        for gene in sorted(genes, key=lambda value: (-len(value), value)):
            if suffix == gene or suffix.startswith(f"{gene}_"):
                return gene
    return None


def build_shap_gene_evidence(
    global_tables: Mapping[str, pd.DataFrame],
    class_tables: Mapping[str, pd.DataFrame],
    *,
    known_genes: Sequence[str],
) -> pd.DataFrame:
    """Aggregate global/class SHAP tables into a transparent gene prior."""

    global_rows: list[pd.DataFrame] = []
    class_rows: list[pd.DataFrame] = []
    for model, frame in global_tables.items():
        current = frame.copy()
        current["model"] = model
        current["gene"] = current["feature"].map(
            lambda value: extract_gene_from_feature(
                str(value), known_genes=known_genes
            )
        )
        global_rows.append(current.dropna(subset=["gene"]))
    for model, frame in class_tables.items():
        current = frame.copy()
        current["model"] = model
        current["gene"] = current["feature"].map(
            lambda value: extract_gene_from_feature(
                str(value), known_genes=known_genes
            )
        )
        class_rows.append(current.dropna(subset=["gene"]))

    global_long = pd.concat(global_rows, ignore_index=True)
    class_long = pd.concat(class_rows, ignore_index=True)
    global_summary = (
        global_long.groupby("gene", as_index=False)
        .agg(
            shap_global_share=("share", "sum"),
            shap_global_feature_count=("feature", "size"),
            shap_global_model_count=("model", "nunique"),
            shap_best_global_rank=("rank", "min"),
        )
    )
    class_summary = (
        class_long.groupby("gene", as_index=False)
        .agg(
            shap_class_abs_sum=("mean_abs_true_class_shap", "sum"),
            shap_class_top_appearance_count=("feature", "size"),
            shap_class_count=("class", "nunique"),
            shap_class_model_count=("model", "nunique"),
        )
    )
    result = global_summary.merge(class_summary, on="gene", how="outer")
    numeric = [column for column in result if column != "gene"]
    result[numeric] = result[numeric].fillna(0)
    model_count = len(global_tables)
    result["vote_shap_global_top100"] = (
        result["shap_best_global_rank"].between(1, 100)
    ).astype(int)
    result["vote_shap_repeated_models"] = (
        result["shap_global_model_count"] == model_count
    ).astype(int)
    result["vote_shap_class_top_repeated"] = (
        result["shap_class_top_appearance_count"] >= 2
    ).astype(int)
    result["shap_priority_votes"] = result[
        [
            "vote_shap_global_top100",
            "vote_shap_repeated_models",
            "vote_shap_class_top_repeated",
        ]
    ].sum(axis=1)
    return result.sort_values(
        ["shap_priority_votes", "shap_global_share", "gene"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def build_parser_v4_event_table(
    train: pd.DataFrame,
    *,
    gene_columns: Sequence[str],
    id_column: str = "ID",
    target_column: str = "SUBCLASS",
) -> pd.DataFrame:
    """Expand non-WT train cells to one row per parser-v4 source token."""

    required = {id_column, target_column, *gene_columns}
    missing = sorted(required - set(train.columns))
    if missing:
        raise ValueError(f"missing train columns: {missing[:5]}")
    genes = tuple(gene_columns)
    sparse_cells = extract_non_wt_gene_cells(
        train,
        genes,
        feature_version=PARSER_V4_SHAP_PRIORITY_VERSION,
    )
    records: list[dict[str, Any]] = []
    for row_raw, gene_raw, cell in zip(
        sparse_cells.row_indices,
        sparse_cells.gene_indices,
        sparse_cells.values,
    ):
        row_index = int(row_raw)
        gene = genes[int(gene_raw)]
        parsed = parse_canonical_gene_cell(cell)
        for event in parsed.events:
            records.append(
                {
                    "ID": str(train.iloc[row_index][id_column]),
                    "SUBCLASS": str(train.iloc[row_index][target_column]),
                    "gene": gene,
                    "raw_token": event.raw_token,
                    "normalized_token": event.normalized_token,
                    "route": event.route,
                    "event_type": event.event_type,
                    "semantic_subfamily": semantic_subfamily_key(event),
                    "parse_status": event.parse_status,
                    "canonical_event_sha256": canonical_event_sha256(event),
                    "position_start": min(event.positions) if event.positions else np.nan,
                    "position_end": max(event.positions) if event.positions else np.nan,
                }
            )
    columns = [
        "ID", "SUBCLASS", "gene", "raw_token", "normalized_token", "route",
        "event_type", "semantic_subfamily", "parse_status",
        "canonical_event_sha256", "position_start", "position_end",
    ]
    return pd.DataFrame.from_records(records, columns=columns)


def _class_enrichment(
    events: pd.DataFrame,
    *,
    group_columns: Sequence[str],
    class_sample_counts: Mapping[str, int],
    total_samples: int,
) -> pd.DataFrame:
    unique = events[[*group_columns, "ID", "SUBCLASS"]].drop_duplicates()
    grouped = (
        unique.groupby([*group_columns, "SUBCLASS"], as_index=False)
        .agg(class_patient_count=("ID", "nunique"))
    )
    patient_count = (
        unique.groupby(list(group_columns))["ID"].nunique().rename("patient_count")
    )
    grouped = grouped.join(patient_count, on=list(group_columns))
    class_total = grouped["SUBCLASS"].map(class_sample_counts).astype(float)
    grouped["class_lift"] = (
        (grouped["class_patient_count"] + 0.5)
        / (grouped["patient_count"] + 1.0)
        / ((class_total + 0.5) / (total_samples + 1.0))
    )
    grouped = grouped.sort_values(
        [*group_columns, "class_lift", "class_patient_count", "SUBCLASS"],
        ascending=[*[True] * len(group_columns), False, False, True],
    )
    return grouped.drop_duplicates(list(group_columns)).rename(
        columns={
            "SUBCLASS": "top_class",
            "class_patient_count": "top_class_patient_count",
            "class_lift": "top_class_lift",
        }
    )[[*group_columns, "top_class", "top_class_patient_count", "top_class_lift"]]


def summarize_event_priority(
    events: pd.DataFrame,
    *,
    group_columns: Sequence[str],
    shap_gene_evidence: pd.DataFrame,
    class_sample_counts: Mapping[str, int],
    total_samples: int,
    minimum_patient_support: int = 5,
) -> pd.DataFrame:
    """Summarise support, enrichment and independent priority votes."""

    group_columns = tuple(group_columns)
    summary = (
        events.groupby(list(group_columns), as_index=False)
        .agg(
            token_count=("raw_token", "size"),
            patient_count=("ID", "nunique"),
            class_count=("SUBCLASS", "nunique"),
            raw_alias_count=("raw_token", "nunique"),
            canonical_event_count=("canonical_event_sha256", "nunique"),
            complete_token_count=(
                "parse_status",
                lambda values: int((values == "complete").sum()),
            ),
        )
    )
    summary["complete_fraction"] = (
        summary["complete_token_count"] / summary["token_count"]
    )
    enrichment = _class_enrichment(
        events,
        group_columns=group_columns,
        class_sample_counts=class_sample_counts,
        total_samples=total_samples,
    )
    summary = summary.merge(enrichment, on=list(group_columns), how="left")
    summary = summary.merge(shap_gene_evidence, on="gene", how="left")
    shap_columns = [
        column
        for column in shap_gene_evidence.columns
        if column != "gene"
    ]
    summary[shap_columns] = summary[shap_columns].fillna(0)
    summary["vote_patient_support"] = (
        summary["patient_count"] >= minimum_patient_support
    ).astype(int)
    summary["vote_parse_complete"] = (
        summary["complete_fraction"] >= 0.95
    ).astype(int)
    summary["vote_class_specific"] = (
        (summary["top_class_patient_count"] >= 3)
        & (summary["top_class_lift"] >= 2.0)
    ).astype(int)
    summary["priority_votes"] = summary[list(PRIORITY_VOTE_COLUMNS)].sum(axis=1)
    return summary.sort_values(
        ["priority_votes", "patient_count", "token_count", *group_columns],
        ascending=[False, False, False, *[True] * len(group_columns)],
    ).reset_index(drop=True)


def build_priority_tables(
    events: pd.DataFrame,
    *,
    shap_gene_evidence: pd.DataFrame,
    class_sample_counts: Mapping[str, int],
    total_samples: int,
) -> dict[str, pd.DataFrame]:
    """Build gene, gene-event and canonical-variant priority tables."""

    gene = summarize_event_priority(
        events,
        group_columns=("gene",),
        shap_gene_evidence=shap_gene_evidence,
        class_sample_counts=class_sample_counts,
        total_samples=total_samples,
    )
    gene_event = summarize_event_priority(
        events,
        group_columns=("gene", "route", "event_type", "semantic_subfamily"),
        shap_gene_evidence=shap_gene_evidence,
        class_sample_counts=class_sample_counts,
        total_samples=total_samples,
    )
    canonical_variant = summarize_event_priority(
        events,
        group_columns=(
            "gene", "route", "event_type", "semantic_subfamily",
            "canonical_event_sha256",
        ),
        shap_gene_evidence=shap_gene_evidence,
        class_sample_counts=class_sample_counts,
        total_samples=total_samples,
    )
    representative = (
        events.sort_values(
            ["gene", "canonical_event_sha256", "normalized_token", "raw_token"]
        )
        .groupby(["gene", "canonical_event_sha256"], as_index=False)
        .agg(
            canonical_variant=("normalized_token", "first"),
            raw_alias_examples=(
                "raw_token",
                lambda values: " | ".join(sorted(set(values))[:5]),
            ),
        )
    )
    canonical_variant = canonical_variant.merge(
        representative,
        on=["gene", "canonical_event_sha256"],
        how="left",
    ).sort_values(
        ["priority_votes", "patient_count", "token_count", "gene", "canonical_variant"],
        ascending=[False, False, False, True, True],
    ).reset_index(drop=True)
    return {
        "gene_priority": gene,
        "gene_event_priority": gene_event,
        "canonical_variant_priority": canonical_variant,
    }
