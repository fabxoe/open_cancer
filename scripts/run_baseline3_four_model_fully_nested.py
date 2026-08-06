#!/usr/bin/env python
"""Run the four-candidate, base-refit fully nested stacking notebook backend.

Candidates are fixed to EXP-639, EXP-545, EXP-127, and EXP-334.  Historical
OOF files are never read.  Every outer fold creates fresh four-fold inner OOF
predictions, fits ExtraTrees on those predictions, refits each base candidate
on the complete outer-train scope, and predicts untouched outer-validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import joblib
import numpy as np
import pandas as pd
import yaml
from scipy import sparse
from scipy.special import softmax
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.metrics import accuracy_score, f1_score, log_loss
from sklearn.svm import LinearSVC
from sklearn.utils.class_weight import compute_sample_weight

from open_cancer.canonical_event_tokenizer import (
    CANONICAL_EVENT_TOKENIZER_VERSION,
    tokenize_patient_event_row,
)
from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.feature_family import drop_named_base_features
from open_cancer.frozen_feature_specs import materialize_frozen_feature_spec
from open_cancer.fully_nested_stacking import (
    BasePrediction,
    PredictionCache,
    build_outer_inner_splits,
    fixed_median_parameters,
    index_sha256,
    run_fully_nested_stacking,
)
from open_cancer.hashing import sha256_file, sha256_lines
from open_cancer.hierarchical_event_adapter import fit_hierarchical_event_adapter
from open_cancer.validation import validate_submission
from run_exp229_pathway_mutation_types import PathwayMutationTypeFoldBuilder
from run_exp639_parser_v4_hotspot12 import Hotspot12FoldBuilder


ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = ROOT / "data/raw/train.csv"
TEST_PATH = ROOT / "data/raw/test.csv"
SAMPLE_PATH = ROOT / "data/raw/sample_submission.csv"
SPLIT_PATH = ROOT / "data/splits/stratified_5fold_seed42.csv"
SLUG = "baseline3_four_model_fully_nested"
CACHE_ROOT = ROOT / "data/processed" / SLUG
REPORT_DIR = ROOT / "reports/analysis" / SLUG

CONFIG_PATHS = {
    "EXP-639": ROOT / "configs/exp639_parser_v4_hotspot12.yaml",
    "EXP-545": ROOT / "configs/exp545_hierarchical_tfidf_linear.yaml",
    "EXP-127": ROOT / "configs/exp127_catboost_v1.yaml",
    "EXP-334": ROOT / "configs/exp334_exp285_isoform_residue_mask.yaml",
}
MODEL_ORDER = ("EXP-639", "EXP-545", "EXP-127", "EXP-334")


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _has_nvidia_gpu() -> bool:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return False
    return subprocess.run(
        [executable, "-L"], capture_output=True, text=True, check=False
    ).returncode == 0


def _load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray]:
    train = pd.read_csv(TRAIN_PATH, dtype=str, keep_default_na=False)
    test = pd.read_csv(TEST_PATH, dtype=str, keep_default_na=False)
    sample = pd.read_csv(SAMPLE_PATH, dtype=str, keep_default_na=False)
    split = pd.read_csv(SPLIT_PATH, dtype={"ID": str, "fold": int})
    if train["ID"].tolist() != split["ID"].tolist():
        raise ValueError("canonical split order does not match train")
    if test["ID"].tolist() != sample["ID"].tolist():
        raise ValueError("sample submission order does not match test")
    genes = tuple(column for column in train if column not in {"ID", "SUBCLASS"})
    if tuple(column for column in test if column != "ID") != genes:
        raise ValueError("train/test gene order mismatch")
    label_to_index = {label: index for index, label in enumerate(CLASS_LABELS)}
    target = train["SUBCLASS"].map(label_to_index)
    if target.isna().any():
        raise ValueError("unknown target outside fixed class order")
    return (
        train,
        test,
        sample,
        target.to_numpy(dtype=np.int32),
        split["fold"].to_numpy(dtype=np.int32),
    )


def _validate_cached_feature_dir(directory: Path) -> bool:
    required = (
        directory / "train_features.npz",
        directory / "test_features.npz",
        directory / "feature_names.json",
    )
    if not all(path.exists() for path in required):
        return False
    report_path = directory / "feature_report.json"
    manifest_path = directory / "feature_spec_manifest.json"
    train_hash = sha256_file(TRAIN_PATH)
    test_hash = sha256_file(TEST_PATH)
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        return (
            report.get("inputs", {}).get("train", {}).get("sha256") == train_hash
            and report.get("inputs", {}).get("test", {}).get("sha256") == test_hash
        )
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return (
            manifest.get("train_input_sha256") == train_hash
            and manifest.get("test_input_sha256") == test_hash
        )
    return False


def _ensure_exp127_features() -> Path:
    official = ROOT / "data/processed/exp127_catboost_v1_features"
    if _validate_cached_feature_dir(official):
        return official
    output = CACHE_ROOT / "exp127_feature_spec_v1"
    if not _validate_cached_feature_dir(output):
        materialize_frozen_feature_spec(
            root=ROOT,
            name="v1",
            output_dir=output,
            train_path=TRAIN_PATH,
            test_path=TEST_PATH,
        )
    if not _validate_cached_feature_dir(output):
        raise ValueError("EXP-127 Feature Spec v1 cache validation failed")
    return output


def _existing_xgb_feature_dir(experiment: str) -> Path:
    directories = {
        "EXP-639": ROOT / "data/processed/exp639_parser_v4_hotspot12_features",
        "EXP-334": ROOT / "data/processed/exp334_exp285_isoform_residue_mask_features",
    }
    directory = directories[experiment]
    if not _validate_cached_feature_dir(directory):
        raise FileNotFoundError(
            f"validated base matrix cache is missing for {experiment}: {directory}. "
            "Run its official feature materialization once before nested execution."
        )
    return directory


class HierarchicalTfidfAdapter:
    name = "EXP-545"

    def __init__(
        self,
        train: pd.DataFrame,
        test: pd.DataFrame,
        target: np.ndarray,
    ) -> None:
        self.config = _load_yaml(CONFIG_PATHS[self.name])
        self.target = target
        genes = tuple(column for column in train if column not in {"ID", "SUBCLASS"})
        token_path = CACHE_ROOT / "canonical_event_tokens.joblib"
        metadata_path = CACHE_ROOT / "canonical_event_tokens.json"
        token_signature = {
            "tokenizer_version": CANONICAL_EVENT_TOKENIZER_VERSION,
            "train_sha256": sha256_file(TRAIN_PATH),
            "test_sha256": sha256_file(TEST_PATH),
            "gene_order_sha256": sha256_lines(genes),
        }
        CACHE_ROOT.mkdir(parents=True, exist_ok=True)
        if token_path.exists() and metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        else:
            metadata = None
        if metadata == token_signature:
            payload = joblib.load(token_path)
            self.train_tokens = tuple(payload["train"])
            self.test_tokens = tuple(payload["test"])
        else:
            self.train_tokens = self._tokenize(train, genes, "train")
            self.test_tokens = self._tokenize(test, genes, "test")
            joblib.dump(
                {"train": self.train_tokens, "test": self.test_tokens},
                token_path,
                compress=3,
            )
            metadata_path.write_text(
                json.dumps(token_signature, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    @staticmethod
    def _tokenize(frame: pd.DataFrame, genes: tuple[str, ...], label: str):
        output = []
        for index, (_, row) in enumerate(frame.iterrows(), start=1):
            output.append(tokenize_patient_event_row(row, genes))
            if index % 500 == 0 or index == len(frame):
                print(f"{label} tokenized {index}/{len(frame)}", flush=True)
        return tuple(output)

    @property
    def signature(self) -> Mapping[str, Any]:
        return {
            "experiment": self.name,
            "config_sha256": sha256_file(CONFIG_PATHS[self.name]),
            "train_sha256": sha256_file(TRAIN_PATH),
            "test_sha256": sha256_file(TEST_PATH),
            "tokenizer_version": CANONICAL_EVENT_TOKENIZER_VERSION,
            "checkpoint_policy": "fixed_linear_model_no_validation_selection",
        }

    def fit_predict(
        self,
        *,
        fit_indices: np.ndarray,
        predict_indices: np.ndarray | None,
        predict_test: bool,
        seed: int,
        scope_name: str,
    ) -> BasePrediction:
        del scope_name
        features = self.config["features"]
        fit_tokens = tuple(self.train_tokens[index] for index in fit_indices)
        predict_tokens = (
            self.test_tokens
            if predict_test
            else tuple(self.train_tokens[index] for index in predict_indices)
        )
        adapter = fit_hierarchical_event_adapter(
            fit_tokens,
            detail_minimum_support=features["detail_minimum_patient_support"],
            global_minimum_support=features["global_minimum_patient_support"],
            normalization=features["normalization"],
        )
        x_fit = adapter.transform(fit_tokens)
        x_predict = adapter.transform(predict_tokens)
        tfidf = TfidfTransformer(**features["tfidf"])
        x_fit = tfidf.fit_transform(x_fit)
        x_predict = tfidf.transform(x_predict)
        parameters = dict(self.config["model"])
        parameters.pop("class")
        parameters["random_state"] = seed
        model = LinearSVC(**parameters)
        model.fit(x_fit, self.target[fit_indices])
        if tuple(int(value) for value in model.classes_) != tuple(range(len(CLASS_LABELS))):
            raise ValueError("EXP-545 class order mismatch")
        score = np.asarray(model.decision_function(x_predict), dtype=np.float64)
        idf_sha256 = hashlib.sha256(
            np.asarray(tfidf.idf_, dtype="<f8").tobytes()
        ).hexdigest()
        return BasePrediction(
            softmax(score, axis=1),
            {
                "fit_scope": "explicit_fit_indices_only",
                "detail_dimension": len(adapter.detail_tokens),
                "global_dimension": len(adapter.global_tokens),
                "feature_sha256": adapter.feature_sha256,
                "adapter_sha256": adapter.adapter_sha256,
                "idf_sha256": idf_sha256,
                "prediction_oov": asdict(adapter.audit(predict_tokens)),
            },
        )


class CatBoostV1Adapter:
    name = "EXP-127"

    def __init__(
        self,
        target: np.ndarray,
        *,
        device_policy: str,
        smoke: bool,
    ) -> None:
        self.config = _load_yaml(CONFIG_PATHS[self.name])
        self.target = target
        directory = _ensure_exp127_features()
        self.train_matrix = sparse.load_npz(directory / "train_features.npz").tocsr()
        self.test_matrix = sparse.load_npz(directory / "test_features.npz").tocsr()
        self.feature_names = tuple(
            json.loads((directory / "feature_names.json").read_text(encoding="utf-8"))
        )
        parameters = dict(self.config["model"]["parameters"])
        parameters.pop("early_stopping_rounds", None)
        gpu = _has_nvidia_gpu()
        if device_policy == "cpu" or (device_policy == "auto" and not gpu):
            parameters["task_type"] = "CPU"
            parameters.pop("devices", None)
        elif device_policy == "gpu" and not gpu:
            raise RuntimeError("GPU policy requested but nvidia-smi found no CUDA GPU")
        if smoke:
            parameters["iterations"] = 2
            parameters["depth"] = min(int(parameters["depth"]), 4)
        self.parameters = parameters
        self.smoke = smoke

    @property
    def signature(self) -> Mapping[str, Any]:
        return {
            "experiment": self.name,
            "config_sha256": sha256_file(CONFIG_PATHS[self.name]),
            "train_sha256": sha256_file(TRAIN_PATH),
            "test_sha256": sha256_file(TEST_PATH),
            "parameters": self.parameters,
            "feature_names_sha256": sha256_lines(self.feature_names),
            "checkpoint_policy": "fixed_iterations_no_validation_selection",
            "smoke": self.smoke,
        }

    def fit_predict(
        self,
        *,
        fit_indices: np.ndarray,
        predict_indices: np.ndarray | None,
        predict_test: bool,
        seed: int,
        scope_name: str,
    ) -> BasePrediction:
        from catboost import CatBoostClassifier

        del scope_name
        x_predict = self.test_matrix if predict_test else self.train_matrix[predict_indices]
        model = CatBoostClassifier(
            loss_function="MultiClass",
            random_seed=seed,
            verbose=False,
            **self.parameters,
        )
        y_fit = self.target[fit_indices]
        weights = compute_sample_weight(class_weight="balanced", y=y_fit)
        model.fit(
            self.train_matrix[fit_indices],
            y_fit,
            sample_weight=weights,
            verbose=False,
        )
        if tuple(int(value) for value in model.classes_) != tuple(range(len(CLASS_LABELS))):
            raise ValueError("EXP-127 class order mismatch")
        probability = np.asarray(model.predict_proba(x_predict), dtype=np.float64)
        if probability.shape[1] != len(CLASS_LABELS):
            raise ValueError("EXP-127 did not emit all 26 classes")
        return BasePrediction(
            probability,
            {
                "fit_scope": "explicit_fit_indices_only",
                "feature_dimension": self.train_matrix.shape[1],
                "feature_names_sha256": sha256_lines(self.feature_names),
                "task_type": self.parameters.get("task_type"),
                "iterations": self.parameters.get("iterations"),
                "validation_used_for_checkpoint": False,
            },
        )


class FoldSafeXGBoostAdapter:
    def __init__(
        self,
        experiment: str,
        target: np.ndarray,
        *,
        device_policy: str,
        smoke: bool,
    ) -> None:
        if experiment not in {"EXP-639", "EXP-334"}:
            raise ValueError(f"unsupported XGBoost candidate: {experiment}")
        self.name = experiment
        self.target = target
        self.config = _load_yaml(CONFIG_PATHS[experiment])
        directory = _existing_xgb_feature_dir(experiment)
        self.train_matrix = sparse.load_npz(directory / "train_features.npz").tocsr()
        self.test_matrix = sparse.load_npz(directory / "test_features.npz").tocsr()
        self.feature_names = tuple(
            json.loads((directory / "feature_names.json").read_text(encoding="utf-8"))
        )
        if experiment == "EXP-639":
            self.builder = Hotspot12FoldBuilder()
            fixed_parameter_source = "EXP-639 config"
            median_parameters = None
        else:
            self.builder = PathwayMutationTypeFoldBuilder(
                membership_path=CACHE_ROOT / "exp334_pathway_membership.json"
            )
            records = [
                record["parameters"]
                for record in self.config["frozen_fold_parameters"]["folds"]
            ]
            median_parameters = fixed_median_parameters(records)
            fixed_parameter_source = "deterministic median of five pre-existing EXP-285 fold configs"
        parameters = dict(self.config["model"])
        parameters.pop("early_stopping_rounds", None)
        if median_parameters is not None:
            parameters.update(median_parameters)
        gpu = _has_nvidia_gpu()
        configured_device = parameters.get("device", "cpu")
        if device_policy == "cpu" or (device_policy == "auto" and not gpu):
            parameters["device"] = "cpu"
        elif device_policy == "gpu":
            if not gpu:
                raise RuntimeError("GPU policy requested but nvidia-smi found no CUDA GPU")
            parameters["device"] = "cuda"
        elif configured_device == "cuda" and not gpu:
            parameters["device"] = "cpu"
        if smoke:
            parameters["n_estimators"] = 2
            parameters["max_depth"] = min(int(parameters["max_depth"]), 3)
        self.parameters = parameters
        self.fixed_parameter_source = fixed_parameter_source
        self.smoke = smoke

    @property
    def signature(self) -> Mapping[str, Any]:
        return {
            "experiment": self.name,
            "config_sha256": sha256_file(CONFIG_PATHS[self.name]),
            "train_sha256": sha256_file(TRAIN_PATH),
            "test_sha256": sha256_file(TEST_PATH),
            "parameters": self.parameters,
            "fixed_parameter_source": self.fixed_parameter_source,
            "feature_names_sha256": sha256_lines(self.feature_names),
            "checkpoint_policy": "fixed_n_estimators_no_validation_selection",
            "smoke": self.smoke,
        }

    def fit_predict(
        self,
        *,
        fit_indices: np.ndarray,
        predict_indices: np.ndarray | None,
        predict_test: bool,
        seed: int,
        scope_name: str,
    ) -> BasePrediction:
        import xgboost as xgb

        empty_prediction = predict_indices is None
        builder_predict_indices = (
            np.asarray([], dtype=np.int64) if empty_prediction else predict_indices
        )
        base_train = self.train_matrix[fit_indices]
        base_validation = self.train_matrix[builder_predict_indices]
        extra = self.builder(
            fold=seed,
            train_indices=fit_indices,
            valid_indices=builder_predict_indices,
            base_train=base_train,
            base_validation=base_validation,
            base_test=self.test_matrix,
            base_feature_names=self.feature_names,
            target=self.target[fit_indices],
        )
        x_fit, x_validation, x_test, kept_names = drop_named_base_features(
            base_train,
            base_validation,
            self.test_matrix,
            self.feature_names,
            extra.base_feature_names_to_drop,
            allow_empty=bool(extra.feature_names),
        )
        x_fit = sparse.hstack([x_fit, extra.train], format="csr", dtype=np.float32)
        x_validation = sparse.hstack(
            [x_validation, extra.validation], format="csr", dtype=np.float32
        )
        x_test = sparse.hstack([x_test, extra.test], format="csr", dtype=np.float32)
        x_predict = x_test if predict_test else x_validation
        parameters = {
            **self.parameters,
            "num_class": len(CLASS_LABELS),
            "random_state": seed,
        }
        model = xgb.XGBClassifier(**parameters)
        y_fit = self.target[fit_indices]
        weights = compute_sample_weight(class_weight="balanced", y=y_fit)
        model.fit(x_fit, y_fit, sample_weight=weights, verbose=False)
        if tuple(int(value) for value in model.classes_) != tuple(range(len(CLASS_LABELS))):
            raise ValueError(f"{self.name} class order mismatch")
        probability = np.asarray(model.predict_proba(x_predict), dtype=np.float64)
        all_names = (*kept_names, *extra.feature_names)
        return BasePrediction(
            probability,
            {
                "fit_scope": "explicit_fit_indices_only",
                "feature_dimension": x_fit.shape[1],
                "feature_names_sha256": sha256_lines(all_names),
                "fold_feature_registry": _json_safe(extra.registry),
                "base_features_dropped": list(extra.base_feature_names_to_drop),
                "device": self.parameters.get("device"),
                "n_estimators": self.parameters.get("n_estimators"),
                "validation_used_for_checkpoint": False,
                "scope_name": scope_name,
            },
        )


def _build_adapters(
    train: pd.DataFrame,
    test: pd.DataFrame,
    target: np.ndarray,
    *,
    device_policy: str,
    smoke: bool,
):
    return (
        FoldSafeXGBoostAdapter("EXP-639", target, device_policy=device_policy, smoke=smoke),
        HierarchicalTfidfAdapter(train, test, target),
        CatBoostV1Adapter(target, device_policy=device_policy, smoke=smoke),
        FoldSafeXGBoostAdapter("EXP-334", target, device_policy=device_policy, smoke=smoke),
    )


def _write_outputs(
    output,
    train: pd.DataFrame,
    test: pd.DataFrame,
    sample: pd.DataFrame,
    target: np.ndarray,
    folds: np.ndarray,
    adapters,
) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (ROOT / "oof").mkdir(parents=True, exist_ok=True)
    (ROOT / "preds").mkdir(parents=True, exist_ok=True)
    (ROOT / "submissions").mkdir(parents=True, exist_ok=True)
    labels = np.asarray(CLASS_LABELS)
    oof_prediction = labels[output.oof_probabilities.argmax(axis=1)]
    test_prediction = labels[output.test_probabilities.argmax(axis=1)]

    oof_frame = pd.DataFrame(output.oof_probabilities, columns=PROBABILITY_COLUMNS)
    oof_frame.insert(0, "PREDICTED", oof_prediction)
    oof_frame.insert(0, "SUBCLASS", train["SUBCLASS"].to_numpy())
    oof_frame.insert(0, "fold", folds)
    oof_frame.insert(0, "ID", train["ID"].to_numpy())
    oof_path = ROOT / "oof" / f"{SLUG}.csv"
    oof_frame.to_csv(oof_path, index=False)

    test_frame = pd.DataFrame(output.test_probabilities, columns=PROBABILITY_COLUMNS)
    test_frame.insert(0, "ID", test["ID"].to_numpy())
    test_path = ROOT / "preds" / f"{SLUG}_test_proba.csv"
    test_frame.to_csv(test_path, index=False)
    submission = sample.copy()
    submission["SUBCLASS"] = test_prediction
    submission_path = ROOT / "submissions" / f"{SLUG}.csv"
    submission.to_csv(submission_path, index=False)
    validate_submission(submission_path, TEST_PATH)

    base_paths = {}
    for name in MODEL_ORDER:
        base_oof_path = ROOT / "oof" / f"{SLUG}_{name.lower().replace('-', '')}.csv"
        base_test_path = ROOT / "preds" / f"{SLUG}_{name.lower().replace('-', '')}_test_proba.csv"
        pd.DataFrame(output.base_oof_probabilities[name], columns=PROBABILITY_COLUMNS).assign(
            ID=train["ID"].to_numpy()
        )[["ID", *PROBABILITY_COLUMNS]].to_csv(base_oof_path, index=False)
        pd.DataFrame(output.base_test_probabilities[name], columns=PROBABILITY_COLUMNS).assign(
            ID=test["ID"].to_numpy()
        )[["ID", *PROBABILITY_COLUMNS]].to_csv(base_test_path, index=False)
        base_paths[name] = {
            "oof": str(base_oof_path.relative_to(ROOT)),
            "test": str(base_test_path.relative_to(ROOT)),
        }

    audit_frame = pd.DataFrame(
        [
            {
                **{key: value for key, value in record.items() if key != "feature_audit"},
                "feature_audit": json.dumps(record["feature_audit"], ensure_ascii=False, sort_keys=True),
            }
            for record in output.audit_records
        ]
    )
    audit_path = REPORT_DIR / "fit_scope_audit.csv"
    audit_frame.to_csv(audit_path, index=False)
    if (audit_frame["fit_protected_overlap"] != 0).any():
        raise ValueError("protected-row overlap exists in fit audit")
    non_final = audit_frame["fit_predict_overlap"].notna()
    if (audit_frame.loc[non_final, "fit_predict_overlap"] != 0).any():
        raise ValueError("fit/predict overlap exists in fit audit")

    prediction = output.oof_probabilities.argmax(axis=1)
    per_class = f1_score(
        target,
        prediction,
        labels=np.arange(len(CLASS_LABELS)),
        average=None,
        zero_division=0,
    )
    result = {
        "record_role": "local_analysis_not_official_experiment",
        "method": "fully_nested_base_refit_stacking",
        "candidate_order": list(MODEL_ORDER),
        "historical_oof_loaded": False,
        "outer_folds": 5,
        "inner_folds_per_outer": 4,
        "base_fit_count": len(output.audit_records),
        "expected_base_fit_count": 104,
        "checkpoint_policy": "fixed_iterations_without_outer_validation_selection",
        "exp334_parameter_policy": adapters[3].fixed_parameter_source,
        "folds": list(output.fold_metrics),
        "oof": {
            "macro_f1": float(f1_score(target, prediction, average="macro", zero_division=0)),
            "accuracy": float(accuracy_score(target, prediction)),
            "log_loss": float(log_loss(target, output.oof_probabilities, labels=np.arange(len(CLASS_LABELS)))),
            "per_class_f1": dict(zip(CLASS_LABELS, per_class.tolist(), strict=True)),
        },
        "runtime_seconds": output.runtime_seconds,
        "artifacts": {
            "oof": str(oof_path.relative_to(ROOT)),
            "test_probabilities": str(test_path.relative_to(ROOT)),
            "submission": str(submission_path.relative_to(ROOT)),
            "fit_scope_audit": str(audit_path.relative_to(ROOT)),
            "base_probabilities": base_paths,
        },
        "input_sha256": {
            "train": sha256_file(TRAIN_PATH),
            "test": sha256_file(TEST_PATH),
            "split": sha256_file(SPLIT_PATH),
        },
        "config_sha256": {
            name: sha256_file(path) for name, path in CONFIG_PATHS.items()
        },
    }
    result_path = REPORT_DIR / "result.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["oof"], ensure_ascii=False, indent=2), flush=True)
    print(f"submission: {submission_path}", flush=True)
    print(f"audit: {audit_path}", flush=True)


def _run_smoke(adapters, target: np.ndarray, folds: np.ndarray, test_count: int) -> None:
    split = build_outer_inner_splits(folds)[0]
    records = []
    for offset, adapter in enumerate(adapters):
        started = time.perf_counter()
        result = adapter.fit_predict(
            fit_indices=split.fit_indices,
            predict_indices=split.validation_indices,
            predict_test=False,
            seed=42 + offset,
            scope_name=f"smoke_{adapter.name}",
        )
        probability = np.asarray(result.probabilities)
        if probability.shape != (len(split.validation_indices), len(CLASS_LABELS)):
            raise ValueError(f"smoke probability shape mismatch for {adapter.name}")
        records.append(
            {
                "model": adapter.name,
                "stage": "inner_validation_prediction",
                "fit_rows": len(split.fit_indices),
                "validation_rows": len(split.validation_indices),
                "fit_sha256": index_sha256(split.fit_indices),
                "validation_sha256": index_sha256(split.validation_indices),
                "macro_f1": float(
                    f1_score(
                        target[split.validation_indices],
                        probability.argmax(axis=1),
                        average="macro",
                        zero_division=0,
                    )
                ),
                "runtime_seconds": time.perf_counter() - started,
                "feature_audit": _json_safe(result.feature_audit),
            }
        )
        test_started = time.perf_counter()
        test_result = adapter.fit_predict(
            fit_indices=np.arange(len(target), dtype=np.int64),
            predict_indices=None,
            predict_test=True,
            seed=142 + offset,
            scope_name=f"smoke_final_refit_{adapter.name}",
        )
        test_probability = np.asarray(test_result.probabilities)
        if test_probability.shape != (test_count, len(CLASS_LABELS)):
            raise ValueError(f"smoke test probability shape mismatch for {adapter.name}")
        records.append(
            {
                "model": adapter.name,
                "stage": "final_refit_test_prediction",
                "fit_rows": len(target),
                "validation_rows": test_count,
                "fit_sha256": index_sha256(np.arange(len(target), dtype=np.int64)),
                "validation_sha256": None,
                "runtime_seconds": time.perf_counter() - test_started,
                "feature_audit": _json_safe(test_result.feature_audit),
            }
        )
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / "adapter_smoke.json"
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"adapter smoke: {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("audit", "smoke", "full"), default="full")
    parser.add_argument("--device-policy", choices=("auto", "cpu", "gpu"), default="auto")
    parser.add_argument("--no-cache", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    train, test, sample, target, folds = _load_data()
    split_records = build_outer_inner_splits(folds)
    if args.mode == "audit":
        audit = {
            "train_rows": len(train),
            "test_rows": len(test),
            "candidate_order": list(MODEL_ORDER),
            "outer_inner_split_count": len(split_records),
            "all_split_intersections_zero": True,
            "split_sha256": sha256_file(SPLIT_PATH),
        }
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        path = REPORT_DIR / "split_audit.json"
        path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(audit, ensure_ascii=False, indent=2))
        return

    smoke = args.mode == "smoke"
    adapters = _build_adapters(
        train,
        test,
        target,
        device_policy=args.device_policy,
        smoke=smoke,
    )
    if smoke:
        _run_smoke(adapters, target, folds, len(test))
        return

    cache = PredictionCache(CACHE_ROOT / "prediction_cache", enabled=not args.no_cache)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    progress_path = REPORT_DIR / "progress.log"

    def progress(message: str) -> None:
        line = f"{datetime.now(timezone.utc).isoformat()} {message}"
        print(line, flush=True)
        with progress_path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    progress(f"run_start device_policy={args.device_policy} cache_enabled={not args.no_cache}")
    output = run_fully_nested_stacking(
        adapters=adapters,
        targets=target,
        folds=folds,
        test_row_count=len(test),
        cache=cache,
        seed=42,
        progress=progress,
    )
    _write_outputs(output, train, test, sample, target, folds, adapters)


if __name__ == "__main__":
    main()
