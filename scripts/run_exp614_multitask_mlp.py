#!/usr/bin/env python
"""Run EXP-614: parser-v4 shared-encoder hierarchical multi-task MLP."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
)
import yaml

from open_cancer.constants import CLASS_LABELS, PROBABILITY_COLUMNS
from open_cancer.experiment import resolve_experiment_context
from open_cancer.hashing import sha256_file, sha256_lines
from open_cancer.multitask_mlp import (
    MultitaskMLPConfig,
    build_multitask_mlp,
    hierarchy_targets,
    multitask_loss,
    set_multitask_determinism,
)
from open_cancer.patient_semantic_vector import PatientSemanticVectorFamily
from open_cancer.validation import validate_submission


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs" / "exp614_multitask_mlp.yaml"
TRAIN = ROOT / "data" / "raw" / "train.csv"
TEST = ROOT / "data" / "raw" / "test.csv"
SAMPLE = ROOT / "data" / "raw" / "sample_submission.csv"


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def resolve_device(torch):
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def build_or_load_semantic_cache(
    train: pd.DataFrame,
    test: pd.DataFrame,
    gene_columns: tuple[str, ...],
    cache_dir: Path,
):
    names_path = cache_dir / "feature_names.json"
    train_path = cache_dir / "train_features.npz"
    test_path = cache_dir / "test_features.npz"
    if names_path.is_file() and train_path.is_file() and test_path.is_file():
        names = tuple(json.loads(names_path.read_text(encoding="utf-8")))
        return (
            sparse.load_npz(train_path).tocsr().astype(np.float32),
            sparse.load_npz(test_path).tocsr().astype(np.float32),
            names,
        )

    fitted = PatientSemanticVectorFamily(gene_columns).fit(train.iloc[:1])
    train_features = fitted.transform(train)
    test_features = fitted.transform(test)
    names = fitted.descriptor.feature_names
    cache_dir.mkdir(parents=True, exist_ok=True)
    sparse.save_npz(train_path, train_features, compressed=True)
    sparse.save_npz(test_path, test_features, compressed=True)
    names_path.write_text(
        json.dumps(names, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return train_features, test_features, names


def select_fold_features(
    matrix: sparse.csr_matrix,
    feature_names: tuple[str, ...],
    train_indices: np.ndarray,
    *,
    dimension: int,
):
    support = np.asarray(matrix[train_indices].getnnz(axis=0)).ravel().astype(np.int64)
    core = [
        index
        for index, name in enumerate(feature_names)
        if name.startswith("sample__parser_v4_")
    ]
    if len(core) > dimension:
        raise ValueError("sample parser-v4 core가 목표 차원보다 큽니다.")
    core_set = set(core)
    candidates = [
        index
        for index, name in enumerate(feature_names)
        if index not in core_set
        and name.startswith("gene__")
        and support[index] > 0
    ]
    candidates.sort(key=lambda index: (-int(support[index]), feature_names[index]))
    selected = np.asarray((*core, *candidates[: dimension - len(core)]), dtype=np.int64)
    if len(selected) != dimension:
        raise ValueError(f"선택 가능한 의미 피처가 부족합니다: {len(selected)} < {dimension}")
    manifest = {
        "fit_scope": "outer_train_only_target_independent_support",
        "fit_rows": int(len(train_indices)),
        "input_dimension": int(matrix.shape[1]),
        "output_dimension": int(dimension),
        "core_count": int(len(core)),
        "gene_event_count": int(dimension - len(core)),
        "target_used": False,
        "validation_used": False,
        "test_used": False,
        "ranking": "support_desc_then_feature_name",
        "input_feature_names_sha256": sha256_lines(feature_names),
        "selected_feature_names_sha256": sha256_lines(
            feature_names[index] for index in selected
        ),
        "selected_source_indices_sha256": sha256_lines(str(index) for index in selected),
        "selected_features": [
            {
                "output_index": output_index,
                "source_index": int(source_index),
                "name": feature_names[source_index],
                "outer_train_support": int(support[source_index]),
            }
            for output_index, source_index in enumerate(selected)
        ],
    }
    return selected, manifest


def fit_scaler(
    matrix: sparse.csr_matrix,
    selected: np.ndarray,
    train_indices: np.ndarray,
):
    values = np.log1p(matrix[train_indices][:, selected].toarray()).astype(np.float32)
    mean = values.mean(axis=0, dtype=np.float64).astype(np.float32)
    scale = values.std(axis=0, dtype=np.float64).astype(np.float32)
    scale[scale < 1e-6] = 1.0
    return mean, scale


def transform(
    matrix: sparse.csr_matrix,
    rows: np.ndarray | None,
    selected: np.ndarray,
    mean: np.ndarray,
    scale: np.ndarray,
) -> np.ndarray:
    source = matrix if rows is None else matrix[rows]
    values = np.log1p(source[:, selected].toarray()).astype(np.float32)
    values = (values - mean) / scale
    if not np.isfinite(values).all():
        raise ValueError("MLP 입력에 NaN 또는 Inf가 있습니다.")
    return values.astype(np.float32, copy=False)


def tensor_auxiliary(torch, targets: dict[str, np.ndarray], indices: np.ndarray, device):
    values = {}
    for key, value in targets.items():
        array = value[indices]
        dtype = torch.bool if key.endswith("_mask") else (
            torch.long if key.endswith("_pair") else torch.float32
        )
        values[key] = torch.as_tensor(array, dtype=dtype, device=device)
    return values


def predict_probability(torch, model, values: np.ndarray, device, batch_size: int):
    model.eval()
    probabilities = []
    with torch.no_grad():
        for start in range(0, len(values), batch_size):
            batch = torch.from_numpy(values[start : start + batch_size]).to(device)
            logits = model(batch)["main"]
            probabilities.append(torch.softmax(logits, dim=1).cpu().numpy())
    return np.vstack(probabilities).astype(np.float32)


def train_arm(
    torch,
    *,
    values_train: np.ndarray,
    target_train: np.ndarray,
    values_valid: np.ndarray,
    target_valid: np.ndarray,
    values_test: np.ndarray,
    config: dict,
    auxiliary_weight: float,
    seed: int,
    device,
):
    set_multitask_determinism(seed)
    architecture = MultitaskMLPConfig(
        input_dim=values_train.shape[1],
        hidden_dim=int(config["model"]["hidden_dim"]),
        embedding_dim=int(config["model"]["embedding_dim"]),
        dropout=float(config["model"]["dropout"]),
    )
    model = build_multitask_mlp(architecture).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(config["training"]["learning_rate"]),
        weight_decay=float(config["training"]["weight_decay"]),
    )
    counts = np.bincount(target_train, minlength=len(CLASS_LABELS)).astype(np.float64)
    weights = len(target_train) / (len(CLASS_LABELS) * np.maximum(counts, 1.0))
    class_weights = torch.as_tensor(weights, dtype=torch.float32, device=device)
    all_aux = hierarchy_targets(target_train, tuple(CLASS_LABELS))
    batch_size = int(config["training"]["batch_size"])
    max_epochs = int(config["training"]["max_epochs"])
    patience = int(config["training"]["early_stopping_patience"])
    gradient_clip = float(config["training"]["gradient_clip_norm"])

    best_f1 = -1.0
    best_epoch = -1
    best_state = None
    best_valid = None
    stale = 0
    epoch_records = []
    for epoch in range(max_epochs):
        model.train()
        rng = np.random.default_rng(seed + epoch)
        order = rng.permutation(len(values_train))
        losses = []
        main_losses = []
        auxiliary_losses = []
        for start in range(0, len(order), batch_size):
            indices = order[start : start + batch_size]
            batch = torch.from_numpy(values_train[indices]).to(device)
            main_target = torch.as_tensor(
                target_train[indices], dtype=torch.long, device=device
            )
            aux_target = tensor_auxiliary(torch, all_aux, indices, device)
            optimizer.zero_grad(set_to_none=True)
            outputs = model(batch)
            loss, parts = multitask_loss(
                outputs,
                main_target,
                aux_target,
                class_weights=class_weights,
                auxiliary_weight=auxiliary_weight,
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), gradient_clip)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
            main_losses.append(float(parts["main"].cpu()))
            auxiliary_losses.append(float(parts["auxiliary_mean"].cpu()))

        valid_probability = predict_probability(
            torch, model, values_valid, device, batch_size
        )
        valid_prediction = valid_probability.argmax(axis=1)
        valid_f1 = float(
            f1_score(
                target_valid,
                valid_prediction,
                labels=np.arange(len(CLASS_LABELS)),
                average="macro",
                zero_division=0,
            )
        )
        epoch_records.append(
            {
                "epoch": epoch + 1,
                "loss": float(np.mean(losses)),
                "main_loss": float(np.mean(main_losses)),
                "auxiliary_loss": float(np.mean(auxiliary_losses)),
                "validation_macro_f1": valid_f1,
            }
        )
        if valid_f1 > best_f1 + 1e-12:
            best_f1 = valid_f1
            best_epoch = epoch + 1
            best_state = copy.deepcopy(model.state_dict())
            best_valid = valid_probability
            stale = 0
        else:
            stale += 1
            if stale >= patience:
                break

    if best_state is None or best_valid is None:
        raise RuntimeError("checkpoint가 선택되지 않았습니다.")
    model.load_state_dict(best_state)
    test_probability = predict_probability(
        torch, model, values_test, device, batch_size
    )
    return {
        "model": model,
        "architecture": architecture,
        "best_epoch": best_epoch,
        "best_macro_f1": best_f1,
        "valid_probability": best_valid,
        "test_probability": test_probability,
        "epochs": epoch_records,
    }


def probability_metrics(target: np.ndarray, probability: np.ndarray) -> dict[str, object]:
    prediction = probability.argmax(axis=1)
    report = classification_report(
        target,
        prediction,
        labels=np.arange(len(CLASS_LABELS)),
        target_names=CLASS_LABELS,
        output_dict=True,
        zero_division=0,
    )
    return {
        "macro_f1": float(
            f1_score(
                target,
                prediction,
                labels=np.arange(len(CLASS_LABELS)),
                average="macro",
                zero_division=0,
            )
        ),
        "accuracy": float(accuracy_score(target, prediction)),
        "log_loss": float(log_loss(target, probability, labels=np.arange(26))),
        "per_class_f1": {
            label: float(report[label]["f1-score"]) for label in CLASS_LABELS
        },
        "confusion_matrix": confusion_matrix(
            target, prediction, labels=np.arange(26)
        ).tolist(),
    }


def main() -> None:
    import torch

    started = datetime.now(timezone.utc)
    started_perf = time.perf_counter()
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    context = resolve_experiment_context(config["run_mode"], cwd=ROOT)
    if git("status", "--porcelain"):
        raise RuntimeError("공식 실험은 source/config commit 후 clean worktree에서 실행해야 합니다.")

    slug = f"exp{context.issue_number:03d}_{config['slug']}"
    report_dir = ROOT / "reports" / slug
    repro_dir = ROOT / "reproducibility" / slug
    model_dir = ROOT / "models" / slug
    cache_dir = ROOT / "data" / "processed" / f"{slug}_semantic_cache"
    oof_path = ROOT / "oof" / f"{slug}.csv"
    pred_path = ROOT / "preds" / f"{slug}_test_proba.csv"
    submission_path = ROOT / "submissions" / f"{slug}.csv"
    for path in (
        report_dir,
        repro_dir,
        model_dir,
        oof_path.parent,
        pred_path.parent,
        submission_path.parent,
    ):
        path.mkdir(parents=True, exist_ok=True)

    train = pd.read_csv(TRAIN, dtype=str, keep_default_na=False)
    test = pd.read_csv(TEST, dtype=str, keep_default_na=False)
    sample = pd.read_csv(SAMPLE, dtype=str, keep_default_na=False)
    folds = pd.read_csv(ROOT / config["split"]["path"], dtype={"ID": str, "fold": int})
    if train["ID"].tolist() != folds["ID"].tolist():
        raise ValueError("train과 canonical split ID 순서가 다릅니다.")
    gene_columns = tuple(
        column for column in train.columns if column not in {"ID", "SUBCLASS"}
    )
    semantic_train, semantic_test, feature_names = build_or_load_semantic_cache(
        train, test, gene_columns, cache_dir
    )
    label_to_index = {label: index for index, label in enumerate(CLASS_LABELS)}
    target = train["SUBCLASS"].map(label_to_index).to_numpy(dtype=np.int64)
    fold_values = folds["fold"].to_numpy(dtype=np.int64)
    device = resolve_device(torch)
    dimension = int(config["features"]["selector"]["output_dimension"])

    oof = np.full((len(train), 26), np.nan, dtype=np.float32)
    control_oof = np.full_like(oof, np.nan)
    test_probability = np.zeros((len(test), 26), dtype=np.float32)
    control_test_probability = np.zeros_like(test_probability)
    fold_records = []
    for fold in range(int(config["split"]["n_splits"])):
        train_indices = np.flatnonzero(fold_values != fold)
        valid_indices = np.flatnonzero(fold_values == fold)
        selected, selection_manifest = select_fold_features(
            semantic_train,
            feature_names,
            train_indices,
            dimension=dimension,
        )
        mean, scale = fit_scaler(semantic_train, selected, train_indices)
        x_train = transform(semantic_train, train_indices, selected, mean, scale)
        x_valid = transform(semantic_train, valid_indices, selected, mean, scale)
        x_test = transform(semantic_test, None, selected, mean, scale)
        seed = int(config["seed"]) + fold * 100

        control = train_arm(
            torch,
            values_train=x_train,
            target_train=target[train_indices],
            values_valid=x_valid,
            target_valid=target[valid_indices],
            values_test=x_test,
            config=config,
            auxiliary_weight=0.0,
            seed=seed,
            device=device,
        )
        official = train_arm(
            torch,
            values_train=x_train,
            target_train=target[train_indices],
            values_valid=x_valid,
            target_valid=target[valid_indices],
            values_test=x_test,
            config=config,
            auxiliary_weight=float(config["training"]["auxiliary_weight"]),
            seed=seed,
            device=device,
        )
        control_oof[valid_indices] = control["valid_probability"]
        oof[valid_indices] = official["valid_probability"]
        control_test_probability += control["test_probability"] / 5.0
        test_probability += official["test_probability"] / 5.0

        write_json(model_dir / f"fold_{fold:02d}_feature_selection.json", selection_manifest)
        np.savez_compressed(
            model_dir / f"fold_{fold:02d}_scaler.npz",
            selected_indices=selected,
            mean=mean,
            scale=scale,
        )
        torch.save(
            {
                "state_dict": official["model"].state_dict(),
                "input_dimension": dimension,
                "class_labels": tuple(CLASS_LABELS),
                "feature_names_sha256": selection_manifest["selected_feature_names_sha256"],
                "main_inference_head": "main",
                "auxiliary_heads_used_for_inference": False,
            },
            model_dir / f"fold_{fold:02d}.pt",
        )
        fold_records.append(
            {
                "fold": fold,
                "macro_f1": float(official["best_macro_f1"]),
                "accuracy": float(
                    accuracy_score(
                        target[valid_indices], official["valid_probability"].argmax(axis=1)
                    )
                ),
                "log_loss": float(
                    log_loss(target[valid_indices], official["valid_probability"], labels=np.arange(26))
                ),
                "best_iteration": int(official["best_epoch"]),
                "model_parameters": {
                    **config["model"],
                    "auxiliary_weight": config["training"]["auxiliary_weight"],
                },
                "resampling": {
                    "main_only_control_macro_f1": float(control["best_macro_f1"]),
                    "control_best_epoch": int(control["best_epoch"]),
                    "selection_manifest": str(
                        (model_dir / f"fold_{fold:02d}_feature_selection.json").relative_to(ROOT)
                    ),
                },
            }
        )

    if np.isnan(oof).any() or np.isnan(control_oof).any():
        raise RuntimeError("OOF에 NaN이 있습니다.")
    test_probability /= test_probability.sum(axis=1, keepdims=True)
    control_test_probability /= control_test_probability.sum(axis=1, keepdims=True)
    official_metrics = probability_metrics(target, oof)
    control_metrics = probability_metrics(target, control_oof)
    official_metrics.update(
        {
            "fold_mean": float(np.mean([row["macro_f1"] for row in fold_records])),
            "fold_std": float(np.std([row["macro_f1"] for row in fold_records])),
        }
    )

    pd.DataFrame(
        {"ID": train["ID"], **{name: oof[:, index] for index, name in enumerate(PROBABILITY_COLUMNS)}}
    ).to_csv(oof_path, index=False)
    pd.DataFrame(
        {"ID": test["ID"], **{name: test_probability[:, index] for index, name in enumerate(PROBABILITY_COLUMNS)}}
    ).to_csv(pred_path, index=False)
    submission = pd.DataFrame(
        {
            "ID": sample["ID"],
            "SUBCLASS": np.asarray(CLASS_LABELS, dtype=object)[test_probability.argmax(axis=1)],
        }
    )
    submission.to_csv(submission_path, index=False)
    validate_submission(submission_path, TEST, expected_classes=CLASS_LABELS)

    resolved_path = repro_dir / "config.resolved.yaml"
    metrics = {
        "experiment_id": config["experiment_id"],
        "issue_number": context.issue_number,
        "owner": "fabxoe",
        "record_role": config["record_role"],
        "parent_experiment": config["parent_experiment"],
        "status": "COMPLETED",
        "primary_metric": "macro_f1",
        "split_id": config["split"]["path"],
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git("rev-parse", "HEAD"),
        "oof": official_metrics,
        "folds": fold_records,
        "runtime": {
            "seconds": float(time.perf_counter() - started_perf),
            "hardware": str(device),
        },
        "artifacts": {
            "resolved_config": str(resolved_path.relative_to(ROOT)),
            "oof": str(oof_path.relative_to(ROOT)),
            "test_probability": str(pred_path.relative_to(ROOT)),
            "submission": str(submission_path.relative_to(ROOT)),
            "models": str(model_dir.relative_to(ROOT)),
            "submission_sha256": sha256_file(submission_path),
        },
        "diagnostics": {
            "main_only_control": control_metrics,
            "multitask_minus_control_macro_f1": float(
                official_metrics["macro_f1"] - control_metrics["macro_f1"]
            ),
            "final_prediction_head": "main_26_class_only",
            "row_duplication": False,
        },
        "notes": config["notes"],
    }
    resolved_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    write_json(report_dir / "metrics.json", metrics)
    write_json(repro_dir / "original_metrics.json", metrics)
    write_json(
        repro_dir / "comparison.json",
        {
            "main_only_control_macro_f1": control_metrics["macro_f1"],
            "multitask_macro_f1": official_metrics["macro_f1"],
            "multitask_minus_control_macro_f1": metrics["diagnostics"]["multitask_minus_control_macro_f1"],
            "submission_sha256": sha256_file(submission_path),
            "probability_row_sum_max_abs_error": float(
                np.max(np.abs(test_probability.sum(axis=1) - 1.0))
            ),
        },
    )
    print(
        json.dumps(
            {
                "experiment_id": config["experiment_id"],
                "device": str(device),
                "macro_f1": official_metrics["macro_f1"],
                "main_only_control_macro_f1": control_metrics["macro_f1"],
                "delta": metrics["diagnostics"]["multitask_minus_control_macro_f1"],
                "submission": str(submission_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
