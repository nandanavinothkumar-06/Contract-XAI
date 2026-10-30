import os
import json
import pytest

from src.models.verify_task019_threshold_calibration import (
    run_independent_calibration_verification,
    INDEPENDENT_AUDIT_DIR,
    ORIGINAL_CALIBRATED_JSON,
    ORIGINAL_EXPERIMENT_JSON
)

def test_historical_artifacts_untouched():
    """Verifies that original experiment JSON and calibrated JSON remain untouched."""
    audit_file = os.path.join(INDEPENDENT_AUDIT_DIR, "calibration_verification_audit.json")
    assert os.path.exists(audit_file), "Independent audit artifact must exist"

    # Original files must remain intact
    assert os.path.exists(ORIGINAL_EXPERIMENT_JSON)
    assert os.path.exists(ORIGINAL_CALIBRATED_JSON)

    with open(audit_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["step5_reconciliation"]["historical_artifacts_modified"] is False

def test_partitions_are_strictly_distinct_and_disjoint():
    """Verifies that validation and test partitions have different example counts, hashes, and disjoint contracts."""
    audit_file = os.path.join(INDEPENDENT_AUDIT_DIR, "calibration_verification_audit.json")
    with open(audit_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    p = data["step4_partition_identity"]
    assert p["validation_example_count"] == 84250
    assert p["test_example_count"] == 87956
    assert p["validation_ground_truth_positives"] == 100129
    assert p["test_ground_truth_positives"] == 105283
    assert p["contract_overlap"] == 0
    assert p["partitions_are_disjoint"] is True
    assert p["shapes_differ"] is True
    assert p["validation_target_array_shape"] != p["test_target_array_shape"]
    assert p["validation_ordered_id_sha256"] != p["test_ordered_id_sha256"]

def test_threshold_selected_on_validation_only():
    """Verifies that threshold 0.05 is selected strictly from validation data."""
    with open(ORIGINAL_CALIBRATED_JSON, "r", encoding="utf-8") as f:
        cal = json.load(f)

    assert cal["stage1_validation_calibration"]["selected_threshold"] == 0.05
    assert cal["stage1_validation_calibration"]["dataset_split"] == "validation"
    assert cal["stage1_validation_calibration"]["frozen_before_test_eval"] is True

def test_calibrated_evaluation_classified_not_verified():
    """Verifies that the audit correctly classifies the run as NOT_VERIFIED due to derived test projection."""
    audit_file = os.path.join(INDEPENDENT_AUDIT_DIR, "calibration_verification_audit.json")
    with open(audit_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["classification"] == "NOT_VERIFIED"
    assert data["step2_code_inspection"]["derived_projection_detected"] is True
    assert data["step2_code_inspection"]["distinct_evaluation_execution"] is False
    assert data["step3_recomputation_status"]["local_model_weights_present"] is False
