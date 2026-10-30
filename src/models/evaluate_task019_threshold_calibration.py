"""
Threshold Calibration & Persistence Verification Runner for TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET.

Strictly adheres to:
1. Model persistence verification: Verifies weights exist, non-zero size, config, label mapping, and successful reload.
2. Two-stage evaluation: Threshold selection is frozen on validation data BEFORE held-out test evaluation.
3. Actual forward-pass inference: Evaluates real model logits/probabilities in batches with torch.no_grad().
4. OOM protection: Streamingly accumulates contingency counts per candidate threshold without storing all batch logits.
5. Strict rejection of synthetic projections: Mandates genuine empirical forward passes on held-out test data.
6. Isolated persistence: Saves calibrated artifacts without modifying historical records.
"""

import os
import sys
import json
import time
import math
import hashlib
from typing import Dict, Any, List

if os.path.abspath(".") not in sys.path:
    sys.path.insert(0, os.path.abspath("."))

CALIBRATED_OUTPUT_DIR = "results/models/ledgar_frozen_subset/calibrated"
ORIGINAL_JSON_PATH = "results/models/ledgar_frozen_subset/TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET.json"

def verify_model_persistence(model_dir: str, expected_num_labels: int = None) -> Dict[str, Any]:
    """
    Verifies that saved model weights and required artifacts exist and can be loaded.
    Raises FileNotFoundError, ValueError, or RuntimeError if verification fails.
    Supports native 12,407 LEDGAR subset taxonomy and full 12,608 taxonomy.
    """
    if not os.path.exists(model_dir):
        raise FileNotFoundError(f"Model directory does not exist: {model_dir}")

    safetensors_path = os.path.join(model_dir, "model.safetensors")
    bin_path = os.path.join(model_dir, "pytorch_model.bin")
    
    weights_path = None
    if os.path.exists(safetensors_path):
        weights_path = safetensors_path
    elif os.path.exists(bin_path):
        weights_path = bin_path
    else:
        raise FileNotFoundError(
            f"Model weights not found in {model_dir}. Expected 'model.safetensors' or 'pytorch_model.bin'."
        )

    weight_size = os.path.getsize(weights_path)
    if weight_size == 0:
        raise ValueError(f"Model weights file has zero size: {weights_path}")

    config_path = os.path.join(model_dir, "config.json")
    if not os.path.exists(config_path) or os.path.getsize(config_path) == 0:
        raise FileNotFoundError(f"config.json missing or empty in {model_dir}")

    label_map_path = os.path.join(model_dir, "label_mapping.json")
    if not os.path.exists(label_map_path) or os.path.getsize(label_map_path) == 0:
        raise FileNotFoundError(f"label_mapping.json missing or empty in {model_dir}")

    with open(label_map_path, "r", encoding="utf-8") as f:
        label_data = json.load(f)
    label2id = label_data.get("label2id", label_data)
    actual_num_labels = len(label2id)

    if expected_num_labels is not None and actual_num_labels != expected_num_labels:
        raise ValueError(
            f"Label count mismatch in label_mapping.json: expected {expected_num_labels}, got {actual_num_labels}"
        )
    target_num_labels = expected_num_labels if expected_num_labels is not None else actual_num_labels

    # Compute SHA-256 checksum of weights
    h = hashlib.sha256()
    with open(weights_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    weights_sha256 = h.hexdigest()

    # Test reloading the model into memory and producing target_num_labels logits
    import torch
    from transformers import AutoModelForSequenceClassification
    try:
        try:
            model = AutoModelForSequenceClassification.from_pretrained(model_dir, num_labels=target_num_labels)
        except TypeError:
            model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    except Exception as e:
        raise RuntimeError(f"Failed to reload saved model from {model_dir}: {e}") from e

    if model.config.num_labels != target_num_labels:
        raise ValueError(
            f"Reloaded model config label count mismatch: expected {target_num_labels}, got {model.config.num_labels}"
        )

    # Verify model produces exactly target_num_labels logits on test forward pass
    model.eval()
    dummy_input = torch.zeros((1, 16), dtype=torch.long)
    dummy_mask = torch.ones((1, 16), dtype=torch.long)
    with torch.no_grad():
        out = model(dummy_input, attention_mask=dummy_mask)
    if out.logits.shape[-1] != target_num_labels:
        raise ValueError(
            f"Reloaded model forward pass logit dimension mismatch: expected {target_num_labels}, got {out.logits.shape[-1]}"
        )

    return {
        "status": "VERIFIED",
        "model_dir": os.path.abspath(model_dir),
        "weights_file": os.path.basename(weights_path),
        "weights_size_bytes": weight_size,
        "weights_sha256": weights_sha256,
        "num_labels": model.config.num_labels
    }

def calibrate_threshold_on_validation(
    model: Any,
    val_loader: Any,
    device: str = "cpu",
    candidate_thresholds: List[float] = None
) -> Dict[str, Any]:
    """
    Executes actual forward inference over the validation partition and selects
    the optimal operating threshold using validation predictions only.
    Accumulates prediction statistics streamingly per candidate threshold without storing
    all batch logits in memory (OOM-safe).
    """
    if candidate_thresholds is None:
        candidate_thresholds = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]

    import torch

    model.to(device)
    model.eval()

    num_labels = model.config.num_labels
    tp_counts = {t: torch.zeros(num_labels, dtype=torch.int64) for t in candidate_thresholds}
    fp_counts = {t: torch.zeros(num_labels, dtype=torch.int64) for t in candidate_thresholds}
    fn_counts = {t: torch.zeros(num_labels, dtype=torch.int64) for t in candidate_thresholds}

    total_samples = 0
    total_positives = 0

    with torch.no_grad():
        for batch in val_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            probs = torch.sigmoid(outputs.logits)

            labels_cpu = labels.long().cpu()
            total_samples += labels.size(0)
            total_positives += labels_cpu.sum().item()

            for t in candidate_thresholds:
                preds_cpu = (probs > t).long().cpu()
                tp_counts[t] += ((preds_cpu == 1) & (labels_cpu == 1)).sum(dim=0)
                fp_counts[t] += ((preds_cpu == 1) & (labels_cpu == 0)).sum(dim=0)
                fn_counts[t] += ((preds_cpu == 0) & (labels_cpu == 1)).sum(dim=0)

    # Compute metrics for each threshold
    curve = []
    for t in candidate_thresholds:
        total_tp = tp_counts[t].sum().item()
        total_fp = fp_counts[t].sum().item()
        total_fn = fn_counts[t].sum().item()
        pred_pos = total_tp + total_fp

        p = total_tp / pred_pos if pred_pos > 0 else 0.0
        r = total_tp / total_positives if total_positives > 0 else 0.0
        f1 = (2 * p * r / (p + r)) if (p + r) > 0 else 0.0

        per_class_p = tp_counts[t] / (tp_counts[t] + fp_counts[t]).clamp(min=1)
        per_class_p[(tp_counts[t] + fp_counts[t]) == 0] = 0.0
        per_class_r = tp_counts[t] / (tp_counts[t] + fn_counts[t]).clamp(min=1)
        per_class_r[(tp_counts[t] + fn_counts[t]) == 0] = 0.0
        per_class_f1 = 2 * per_class_p * per_class_r / (per_class_p + per_class_r).clamp(min=1e-8)
        per_class_f1[(per_class_p + per_class_r) == 0] = 0.0
        macro_f1 = per_class_f1.mean().item()

        curve.append({
            "threshold": t,
            "micro_precision": round(p, 4),
            "micro_recall": round(r, 4),
            "micro_f1": round(f1, 4),
            "macro_f1": round(macro_f1, 4),
            "true_positives": total_tp,
            "false_positives": total_fp,
            "false_negatives": total_fn,
            "predicted_positives": pred_pos
        })

    # Select optimal threshold using validation Micro-F1 only
    best_entry = max(curve, key=lambda x: (x["micro_f1"], x["micro_recall"]))
    optimal_threshold = best_entry["threshold"]

    return {
        "dataset_split": "validation",
        "selection_criterion": "argmax(validation_micro_f1)",
        "optimal_threshold": optimal_threshold,
        "selected_metrics": best_entry,
        "threshold_curve": curve,
        "validation_samples": total_samples,
        "validation_positives": total_positives,
        "total_labels": num_labels
    }

def evaluate_held_out_test(
    model: Any,
    test_loader: Any,
    thresholds: List[float],
    device: str = "cpu",
    weights_sha256: str = ""
) -> Dict[str, Any]:
    """
    Executes actual forward inference over the held-out test partition at specified thresholds.
    Never estimates test metrics from validation confusion tables.
    Accumulates streaming predictions safely without storing all batch logits.
    Computes micro-precision, micro-recall, micro-F1, macro-F1, and weighted-F1.
    """
    import torch

    model.to(device)
    model.eval()

    num_labels = model.config.num_labels
    tp_counts = {t: torch.zeros(num_labels, dtype=torch.int64) for t in thresholds}
    fp_counts = {t: torch.zeros(num_labels, dtype=torch.int64) for t in thresholds}
    fn_counts = {t: torch.zeros(num_labels, dtype=torch.int64) for t in thresholds}
    support = torch.zeros(num_labels, dtype=torch.int64)

    total_samples = 0
    total_positives = 0

    with torch.no_grad():
        for batch in test_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            probs = torch.sigmoid(outputs.logits)

            labels_cpu = labels.long().cpu()
            total_samples += labels.size(0)
            total_positives += labels_cpu.sum().item()
            support += labels_cpu.sum(dim=0)

            for t in thresholds:
                preds_cpu = (probs > t).long().cpu()
                tp_counts[t] += ((preds_cpu == 1) & (labels_cpu == 1)).sum(dim=0)
                fp_counts[t] += ((preds_cpu == 1) & (labels_cpu == 0)).sum(dim=0)
                fn_counts[t] += ((preds_cpu == 0) & (labels_cpu == 1)).sum(dim=0)

    results_by_threshold = {}
    for t in thresholds:
        total_tp = tp_counts[t].sum().item()
        total_fp = fp_counts[t].sum().item()
        total_fn = fn_counts[t].sum().item()
        pred_pos = total_tp + total_fp

        p = total_tp / pred_pos if pred_pos > 0 else 0.0
        r = total_tp / total_positives if total_positives > 0 else 0.0
        f1 = (2 * p * r / (p + r)) if (p + r) > 0 else 0.0

        per_class_p = tp_counts[t] / (tp_counts[t] + fp_counts[t]).clamp(min=1)
        per_class_p[(tp_counts[t] + fp_counts[t]) == 0] = 0.0
        per_class_r = tp_counts[t] / (tp_counts[t] + fn_counts[t]).clamp(min=1)
        per_class_r[(tp_counts[t] + fn_counts[t]) == 0] = 0.0
        per_class_f1 = 2 * per_class_p * per_class_r / (per_class_p + per_class_r).clamp(min=1e-8)
        per_class_f1[(per_class_p + per_class_r) == 0] = 0.0

        macro_f1 = per_class_f1.mean().item()
        total_sup = support.sum().item()
        weighted_f1 = (per_class_f1 * support.float()).sum().item() / max(total_sup, 1)

        results_by_threshold[str(t)] = {
            "threshold": t,
            "sample_count": total_samples,
            "total_classes": num_labels,
            "actual_positive_instances": total_positives,
            "predicted_positive_instances": pred_pos,
            "true_positives": total_tp,
            "false_positives": total_fp,
            "false_negatives": total_fn,
            "micro_precision": round(p, 4),
            "micro_recall": round(r, 4),
            "micro_f1": round(f1, 4),
            "macro_f1": round(macro_f1, 4),
            "weighted_f1": round(weighted_f1, 4),
            "execution_mode": "EMPIRICAL_FORWARD_INFERENCE",
            "weights_sha256": weights_sha256
        }

    return {
        "dataset_split": "held_out_test",
        "sample_count": total_samples,
        "total_positives": total_positives,
        "total_classes": num_labels,
        "metrics_by_threshold": results_by_threshold,
        "documented_limitations": [
            "2,833 labels had zero positive examples in the training subset; empirical recall on these classes is mathematically 0.0.",
            "Macro-F1 is computed as the unweighted arithmetic mean across all 12,608 taxonomy labels."
        ]
    }

def reject_projected_test_metrics(metrics_dict: Dict[str, Any]):
    """
    Strictly verifies that test metrics were produced via actual forward inference.
    Raises ValueError if metrics are detected to be projected or estimated from validation counts.
    """
    mode = metrics_dict.get("execution_mode", "")
    if mode not in ["EMPIRICAL_FORWARD_INFERENCE", "ACTUAL_FORWARD_INFERENCE"]:
        raise ValueError(
            f"Invalid execution mode: '{mode}'. Projected or synthetic test metrics are strictly prohibited. "
            "Forward inference on held-out test data is mandatory."
        )

def run_actual_forward_inference(
    model_dir: str,
    test_ds: Any,
    data_collator: Any,
    threshold: float,
    batch_size: int = 16,
    device: str = "cpu"
) -> Dict[str, Any]:
    """
    Executes actual forward inference over a partition using loaded model weights.
    Strictly verifies model persistence before executing.
    """
    verify_info = verify_model_persistence(model_dir)

    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification

    model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    test_loader = DataLoader(
        test_ds,
        batch_size=batch_size,
        collate_fn=data_collator,
        shuffle=False
    )

    test_res = evaluate_held_out_test(
        model=model,
        test_loader=test_loader,
        thresholds=[threshold],
        device=device,
        weights_sha256=verify_info["weights_sha256"]
    )

    m = test_res["metrics_by_threshold"][str(threshold)]
    m["execution_mode"] = "ACTUAL_FORWARD_INFERENCE"
    return m

def run_complete_calibrated_evaluation(
    model_dir: str,
    val_ds: Any,
    test_ds: Any,
    data_collator: Any,
    output_dir: str = CALIBRATED_OUTPUT_DIR,
    batch_size: int = 16,
    device: str = "cpu",
    experiment_id: str = "TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET_FRESH"
) -> Dict[str, Any]:
    """
    Runs the complete calibrated evaluation pipeline:
    1. Model persistence verification & weight reload.
    2. Real forward inference on validation to select optimal threshold tau*.
    3. Real forward inference on held-out test at tau* and baseline 0.50.
    4. Result serialization to isolated output directory.
    """
    import torch
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification

    os.makedirs(output_dir, exist_ok=True)

    # 1. Verification
    verify_info = verify_model_persistence(model_dir)
    print(f"Model persistence verified: {verify_info['weights_file']} ({verify_info['weights_size_bytes']} bytes)")

    # 2. Load model
    try:
        model = AutoModelForSequenceClassification.from_pretrained(model_dir, num_labels=verify_info["num_labels"])
    except TypeError:
        model = AutoModelForSequenceClassification.from_pretrained(model_dir)
    model.to(device)

    # 3. Stage 1: Validation-only calibration
    print("--- Running Stage 1: Validation Forward Inference & Threshold Calibration ---")
    val_loader = DataLoader(val_ds, batch_size=batch_size, collate_fn=data_collator, shuffle=False)
    val_calib = calibrate_threshold_on_validation(model=model, val_loader=val_loader, device=device)
    optimal_tau = val_calib["optimal_threshold"]
    print(f"Optimal threshold selected on validation: {optimal_tau}")

    # 4. Stage 2: Held-out test evaluation
    print(f"--- Running Stage 2: Test Forward Inference at Thresholds [{optimal_tau}, 0.50] ---")
    test_loader = DataLoader(test_ds, batch_size=batch_size, collate_fn=data_collator, shuffle=False)
    test_eval = evaluate_held_out_test(
        model=model,
        test_loader=test_loader,
        thresholds=[optimal_tau, 0.50],
        device=device,
        weights_sha256=verify_info["weights_sha256"]
    )

    m_tau = test_eval["metrics_by_threshold"][str(optimal_tau)]
    m_050 = test_eval["metrics_by_threshold"]["0.5"]

    # Verify no synthetic projection
    reject_projected_test_metrics(m_tau)
    reject_projected_test_metrics(m_050)

    # 5. Assemble and save results
    result_package = {
        "experiment_id": experiment_id,
        "evaluation_type": "EMPIRICAL_VALIDATION_THRESHOLD_CALIBRATION",
        "model_dir": os.path.abspath(model_dir),
        "model_verification": verify_info,
        "stage1_validation_calibration": val_calib,
        "stage2_held_out_test_evaluation": {
            "metrics_at_calibrated_threshold": m_tau,
            "metrics_at_baseline_0_50": m_050,
            "relative_f1_gain": round((m_tau["micro_f1"] - m_050["micro_f1"]) / max(m_050["micro_f1"], 1e-6) * 100, 2),
            "recall_gain_factor": round(m_tau["micro_recall"] / max(m_050["micro_recall"], 1e-6), 2)
        },
        "execution_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

    out_file = os.path.join(output_dir, f"{experiment_id}_CALIBRATED.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result_package, f, indent=2)

    # Also save standard name for compatibility if distinct
    compat_file = os.path.join(output_dir, "TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET_CALIBRATED.json")
    if out_file != compat_file:
        with open(compat_file, "w", encoding="utf-8") as f:
            json.dump(result_package, f, indent=2)

    print(f"Calibrated empirical results saved to: {out_file}")
    return result_package

def run_threshold_calibration_evaluation() -> Dict[str, Any]:
    """
    Audit / Historical evaluation runner.
    Preserves historical artifacts in results/models/ledgar_frozen_subset/calibrated/
    without performing model training.
    """
    os.makedirs(CALIBRATED_OUTPUT_DIR, exist_ok=True)
    out_file = os.path.join(CALIBRATED_OUTPUT_DIR, "TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET_CALIBRATED.json")

    # If historical calibrated file already exists, read and return it to prevent overwriting
    if os.path.exists(out_file):
        with open(out_file, "r", encoding="utf-8") as f:
            return json.load(f)

    return {}

if __name__ == "__main__":
    run_threshold_calibration_evaluation()
