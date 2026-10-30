import os
import json
import pytest
import torch
import numpy as np

from src.models.audit_task019_recall_investigation import (
    verify_model_and_label_mapping,
    recompute_test_contingency,
    diagnose_prediction_distribution,
    simulate_validation_threshold_curve,
    AUDIT_OUTPUT_DIR
)

def test_audit_artifact_preservation():
    """Verifies that original artifacts were preserved and audit directory is isolated."""
    # 1. Audit report must exist in isolated audit directory
    report_path = os.path.join(AUDIT_OUTPUT_DIR, "audit_report.json")
    assert os.path.exists(report_path), "audit_report.json must exist in isolated audit dir"
    
    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["experiment_id"] == "TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET"
    assert data["step7_experiment_status"]["task_019_status"] == "ACTIVE"
    assert data["step7_experiment_status"]["task_020_status"] == "LOCKED"

    # 2. Existing experiment JSON must remain intact
    frozen_json = "results/models/ledgar_frozen_subset/TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET.json"
    assert os.path.exists(frozen_json), "Original experiment JSON must not be deleted"

def test_model_and_collator_mapping_verification():
    """Step 2: Verifies model dimensions, target encoding, and label order."""
    res = verify_model_and_label_mapping()
    assert res["model_output_dimension"] == 12608
    assert res["label_mapping_count"] == 12608
    assert res["target_tensor_shape"] == "[batch_size, 12608]"
    assert res["target_tensor_dtype"] == "torch.float32"
    assert res["target_encoding"] == "multi_hot_binary_indicator"
    assert res["label_order_consistency"] == "VERIFIED_IDENTICAL"
    assert res["example_alignment"] == "VERIFIED_ALIGNED"
    assert res["has_label_mapping_bug"] is False
    assert res["has_tensor_shape_mismatch"] is False

def test_metric_recomputation_and_contingency():
    """Step 3: Verifies exact mathematical recomputation of contingency matrix from recorded metrics."""
    res = recompute_test_contingency(micro_p=0.6975, micro_r=0.0094, total_test_positives=105283)
    assert res["total_actual_positives"] == 105283
    assert res["true_positives"] == 990
    assert res["false_positives"] == 429
    assert res["false_negatives"] == 104293
    assert res["total_predicted_positives"] == 1419
    assert abs(res["micro_precision"] - 0.6977) < 0.001
    assert abs(res["micro_recall"] - 0.0094) < 0.0001
    assert abs(res["micro_f1"] - 0.0186) < 0.001
    assert res["macro_f1"] == 0.0009
    assert res["matches_recorded_metrics"] is True

def test_extreme_imbalance_distribution_quantiles():
    """Step 4: Diagnoses extreme class imbalance and prior log-odds."""
    res = diagnose_prediction_distribution()
    assert res["total_test_provisions"] == 87956
    assert res["total_classes"] == 12608
    assert res["total_prediction_pairs"] == 87956 * 12608
    assert res["prior_log_odds"] < -9.0  # prior log odds is ~ -9.26
    assert res["under_prediction_factor"] > 70.0
    assert res["predicted_positive_instances_at_threshold_0_50"] == 1419
    
    # Check frequency tiers
    freq = res["label_frequency_breakdown_test"]
    assert freq["unrepresented_in_train_0"]["recall"] == 0.0
    assert freq["unrepresented_in_train_0"]["test_positive_instances"] == 4033
    assert freq["common_ge_100"]["predicted_positives_at_0_5"] > 1000

def test_validation_only_threshold_optimization():
    """Step 5: Verifies threshold curve on validation data and optimal threshold selection."""
    res = simulate_validation_threshold_curve()
    assert "validation" in res["dataset_split"]
    assert res["optimal_validation_threshold"] in [0.02, 0.05, 0.10]
    assert res["optimal_validation_micro_f1"] > 0.30  # Substantial improvement over 0.0185
    
    curve = res["threshold_curve"]
    assert len(curve) >= 8
    
    # Precision must increase as threshold increases
    precisions = [entry["micro_precision"] for entry in curve]
    recalls = [entry["micro_recall"] for entry in curve]
    assert precisions[0] < precisions[-1], "Precision should increase with higher threshold"
    assert recalls[0] > recalls[-1], "Recall should decrease with higher threshold"
