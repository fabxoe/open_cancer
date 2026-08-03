#!/usr/bin/env python
"""Run EXP-232: nested pathway-group permutation selection over EXP-229."""

from __future__ import annotations

import json

import numpy as np
import xgboost as xgb
import yaml
from scipy import sparse
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedKFold
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.constants import CLASS_LABELS
from open_cancer.feature_family import FoldFeatureBundle
from open_cancer.pathway_group_selection import select_recurrent_positive_groups
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_hotspot_xgb import ROOT, main


CONFIG = ROOT / "configs" / "exp232_pathway_group_selection.yaml"
REPORT_DIR = ROOT / "reports" / "exp232_pathway_group_selection"
MUTATION_TYPES = ("missense", "synonymous", "nonsense", "frameshift", "complex")


class NestedPathwayGroupSelectionBuilder(PathwayMutationTypeFoldBuilder):
    """Select pathway groups using only each outer fold's training rows."""

    def __init__(self) -> None:
        super().__init__(REPORT_DIR / "pathway_membership.json")
        self.config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        self.selector = self.config["abc_families"]["pathway_group_permutation_selector"]

    @staticmethod
    def _pathway_columns(feature_names: tuple[str, ...]) -> dict[str, tuple[int, ...]]:
        groups: dict[str, list[int]] = {}
        for index, name in enumerate(feature_names):
            for mutation_type in MUTATION_TYPES:
                suffix = f"__{mutation_type}_gene_count"
                if name.startswith("sample__pathway_") and name.endswith(suffix):
                    pathway = name[len("sample__pathway_") : -len(suffix)]
                    groups.setdefault(pathway, []).append(index)
                    break
        return {name: tuple(indices) for name, indices in sorted(groups.items())}

    def __call__(self, **kwargs) -> FoldFeatureBundle:
        bundle = super().__call__(**kwargs)
        fold = int(kwargs["fold"])
        target = np.asarray(kwargs["target"], dtype=np.int32)
        base_train = sparse.csr_matrix(kwargs["base_train"], dtype=np.float32)
        groups = self._pathway_columns(bundle.feature_names)
        inner = StratifiedKFold(
            n_splits=int(self.selector["inner_folds"]),
            shuffle=True,
            random_state=int(self.selector["seed"]) + fold,
        )
        records: list[dict[str, object]] = []
        full = sparse.hstack([base_train, bundle.train], format="csr", dtype=np.float32)
        model_params = {**self.config["model"], "num_class": len(CLASS_LABELS)}
        for inner_fold, (inner_train, inner_valid) in enumerate(inner.split(full, target)):
            model = xgb.XGBClassifier(
                **model_params,
                random_state=int(self.selector["seed"]) + fold * 10 + inner_fold,
            )
            weights = compute_sample_weight(class_weight="balanced", y=target[inner_train])
            model.fit(
                full[inner_train],
                target[inner_train],
                sample_weight=weights,
                eval_set=[(full[inner_valid], target[inner_valid])],
                verbose=False,
            )
            baseline = f1_score(
                target[inner_valid],
                model.predict(full[inner_valid]),
                labels=np.arange(len(CLASS_LABELS)),
                average="macro",
                zero_division=0,
            )
            inner_extra = bundle.train[inner_valid]
            inner_base = base_train[inner_valid]
            for pathway, columns in groups.items():
                deltas: list[float] = []
                for repeat in range(int(self.selector["permutation_repeats"])):
                    rng = np.random.default_rng(
                        int(self.selector["seed"])
                        + fold * 1000
                        + inner_fold * 100
                        + repeat
                    )
                    order = rng.permutation(len(inner_valid))
                    permuted = inner_extra.tolil(copy=True)
                    permuted[:, list(columns)] = inner_extra[order][:, list(columns)]
                    matrix = sparse.hstack(
                        [inner_base, permuted.tocsr()], format="csr", dtype=np.float32
                    )
                    score = f1_score(
                        target[inner_valid],
                        model.predict(matrix),
                        labels=np.arange(len(CLASS_LABELS)),
                        average="macro",
                        zero_division=0,
                    )
                    deltas.append(float(baseline - score))
                records.append(
                    {
                        "inner_fold": inner_fold,
                        "group": pathway,
                        "baseline_macro_f1": float(baseline),
                        "permutation_deltas": deltas,
                        "mean_delta": float(np.mean(deltas)),
                    }
                )

        selected, summary = select_recurrent_positive_groups(
            records,
            minimum_positive_inner_folds=int(
                self.selector["minimum_positive_inner_folds"]
            ),
            minimum_mean_delta=float(self.selector["minimum_mean_macro_f1_delta"]),
        )
        selected_set = set(selected)
        keep = [
            index
            for index, name in enumerate(bundle.feature_names)
            if not any(name.endswith(f"__{kind}_gene_count") for kind in MUTATION_TYPES)
            or any(index in groups[pathway] for pathway in selected_set)
        ]
        selection_record = {
            "outer_fold": fold,
            "selection_scope": "outer_fold_train_only",
            "inner_folds": int(self.selector["inner_folds"]),
            "permutation_repeats": int(self.selector["permutation_repeats"]),
            "selected_pathways": list(selected),
            "selected_candidate_features": len(keep) - 20,
            "summary": summary,
            "records": records,
        }
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        (REPORT_DIR / f"selection_fold_{fold:02d}.json").write_text(
            json.dumps(selection_record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        names = tuple(bundle.feature_names[index] for index in keep)
        registry = {
            **bundle.registry,
            "pathway_group_permutation_selector": {
                "definition_version": "1.0.0",
                "enabled": True,
                "fit_scope": "fold_train",
                "output_dimension": len(names),
                "external_knowledge": None,
                "selected_pathways": list(selected),
                "selection_report": str(
                    (REPORT_DIR / f"selection_fold_{fold:02d}.json").relative_to(ROOT)
                ),
            },
        }
        return FoldFeatureBundle(
            train=bundle.train[:, keep],
            validation=bundle.validation[:, keep],
            test=bundle.test[:, keep],
            fitted_families=bundle.fitted_families,
            feature_names=names,
            registry=registry,
        )


if __name__ == "__main__":
    main(
        CONFIG,
        fold_feature_builder=NestedPathwayGroupSelectionBuilder(),
        runner_command="uv run python scripts/run_exp232_pathway_group_selection.py",
    )
