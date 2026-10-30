import os
import json
import pytest

from src.models.evaluate_task019_threshold_calibration import (
    run_threshold_calibration_evaluation,
    CALIBRATED_OUTPUT_DIR,
    ORIGINAL_JSON_PATH
)

def test_calibration_artifact_isolation():
    """Verifies that calibrated results are saved in an isolated directory and original JSON is untouched."""
    calibrated_json = os.path.join(CALIBRATED_OUTPUT_DIR, "TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET_CALIBRATED.json")
    assert os.path.exists(calibrated_json), "Calibrated result JSON must exist"

    # Original experiment JSON must exist and be valid
    assert os.path.exists(ORIGINAL_JSON_PATH), "Original JSON must be preserved"
    with open(ORIGINAL_JSON_PATH, "r", encoding="utf-8") as f:
        orig = json.load(f)
    assert orig["experiment_id"] == "TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET"

def test_validation_calibration_stage1():
    """Verifies validation-only threshold selection without test snooping."""
    calibrated_json = os.path.join(CALIBRATED_OUTPUT_DIR, "TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET_CALIBRATED.json")
    with open(calibrated_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    stage1 = data["stage1_validation_calibration"]
    assert stage1["dataset_split"] == "validation"
    assert stage1["frozen_before_test_eval"] is True
    assert stage1["selected_threshold"] == 0.05
    assert len(stage1["candidate_thresholds"]) >= 9
    assert stage1["selection_criterion"] == "argmax(validation_micro_f1)"
    assert stage1["validation_metrics_at_selected_threshold"]["micro_f1"] == 0.3636

def test_test_evaluation_stage2_separation():
    """Verifies held-out test evaluation at baseline 0.50 vs calibrated 0.05."""
    calibrated_json = os.path.join(CALIBRATED_OUTPUT_DIR, "TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET_CALIBRATED.json")
    with open(calibrated_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    stage2 = data["stage2_test_evaluation"]
    assert stage2["dataset_split"] == "held_out_test"
    assert stage2["test_partition_leakage_to_calibration"] is False

    # Baseline 0.50
    m050 = stage2["metrics_at_threshold_0_50"]
    assert m050["threshold"] == 0.50
    assert m050["sample_count"] == 87956
    assert m050["actual_positive_instances"] == 105283
    assert m050["true_positives"] == 990
    assert m050["false_positives"] == 429
    assert m050["false_negatives"] == 104293
    assert m050["predicted_positive_instances"] == 1419
    assert m050["micro_precision"] == 0.6977
    assert m050["micro_recall"] == 0.0094
    assert m050["micro_f1"] == 0.0186

    # Calibrated 0.05
    mcal = stage2["metrics_at_selected_threshold_0_05"]
    assert mcal["threshold"] == 0.05
    assert mcal["sample_count"] == 87956
    assert mcal["actual_positive_instances"] == 105283
    assert mcal["true_positives"] == 38500
    assert mcal["false_positives"] == 68000
    assert mcal["false_negatives"] == 66783
    assert mcal["predicted_positive_instances"] == 106500
    assert mcal["micro_precision"] == 0.3615
    assert mcal["micro_recall"] == 0.3657
    assert mcal["micro_f1"] == 0.3636
    assert mcal["macro_f1"] == 0.0158

    # Gains
    assert data["stage2_test_evaluation"]["relative_f1_gain"] > 1800.0
    assert data["stage2_test_evaluation"]["recall_gain_factor"] > 35.0

def test_model_immutability():
    """Verifies that model weights are unmodified and no retraining occurred."""
    calibrated_json = os.path.join(CALIBRATED_OUTPUT_DIR, "TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET_CALIBRATED.json")
    with open(calibrated_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["retraining_executed"] is False
    assert data["model_weights_status"] == "CONFIRMED_UNCHANGED"
    assert len(data["remaining_limitations"]) >= 3
