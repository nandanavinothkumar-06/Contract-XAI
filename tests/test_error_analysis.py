import os
import json
import pytest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "results", "task023", "task023_error_analysis_manifest.json")
EXPECTED_MODEL_SHA256 = "7cd08d2c086f5046eb2b5ef85aa68fec84b5ce7ae3c12bef50c1baea096a8e5f"

@pytest.fixture(scope="module")
def manifest():
    assert os.path.exists(MANIFEST_PATH), f"Task 023 manifest not found at {MANIFEST_PATH}"
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def test_1_error_analysis_manifest_integrity(manifest):
    """Verifies Task 023 manifest schema, completion status, and provenance records."""
    assert manifest["task_id"] == "023"
    assert manifest["task_name"] == "Run error analysis"
    assert manifest["status"] == "COMPLETED"
    
    prov = manifest["provenance"]
    assert prov["model_weights_sha256"] == EXPECTED_MODEL_SHA256
    assert os.path.exists(os.path.join(WORKSPACE_ROOT, prov["model_weights_path"]))
    assert os.path.exists(os.path.join(WORKSPACE_ROOT, prov["calibrated_eval_json"]))
    assert os.path.exists(os.path.join(WORKSPACE_ROOT, prov["contractnli_baseline_json"]))
    assert prov["operating_threshold"] == 0.04
    
    assert manifest["acceptance_criteria_verification"]["status"] == "VERIFIED"

def test_2_ledgar_confusion_and_threshold_tradeoff(manifest):
    """Verifies LEDGAR test confusion numbers and precision-recall trade-off between tau=0.50 and tau*=0.04."""
    ledgar = manifest["ledgar_classification_error_analysis"]
    assert ledgar["status"] == "COMPLETED"
    assert ledgar["test_split_provisions"] == 87956
    assert ledgar["actual_positive_labels"] == 105283
    
    # Calibrated metrics at tau* = 0.04
    c_met = ledgar["calibrated_metrics"]
    assert c_met["threshold"] == 0.04
    assert c_met["true_positives"] == 12699
    assert c_met["false_positives"] == 58947
    assert c_met["false_negatives"] == 92584
    assert c_met["predicted_positives"] == 71646
    assert c_met["micro_precision"] == 0.1772
    assert c_met["micro_recall"] == 0.1206
    assert c_met["micro_f1"] == 0.1435
    assert c_met["macro_f1"] == 0.0045
    
    # Uncalibrated baseline metrics at tau = 0.50
    b_met = ledgar["baseline_metrics_0_50"]
    assert b_met["threshold"] == 0.50
    assert b_met["true_positives"] == 989
    assert b_met["false_positives"] == 438
    assert b_met["false_negatives"] == 104294
    assert b_met["micro_precision"] == 0.6931
    assert b_met["micro_recall"] == 0.0094
    assert b_met["micro_f1"] == 0.0185
    
    # Relative gains
    gains = ledgar["relative_gains"]
    assert gains["relative_f1_gain_pct"] > 600.0
    assert gains["recall_multiplier"] > 12.0
    assert gains["fp_inflation_multiplier"] > 100.0

def test_3_label_tier_accounting_and_macro_collapse(manifest):
    """Verifies taxonomy breakdown, unlearned zero-shot classes, and macro-F1 collapse explanation."""
    tier_info = manifest["ledgar_classification_error_analysis"]["label_tier_distribution"]
    assert tier_info["total_taxonomy_labels"] == 12608
    assert tier_info["evaluated_model_classes"] == 12407
    assert tier_info["excluded_canonical_labels"] == 201
    
    tiers = tier_info["tiers"]
    assert tiers["zero_shot_unlearned"]["count"] == 2833
    assert tiers["zero_shot_unlearned"]["training_examples"] == 0
    assert tiers["zero_shot_unlearned"]["theoretical_recall"] == 0.0
    
    assert tiers["extreme_tail_rare"]["count"] == 8465
    assert tiers["moderate_tail"]["count"] == 1208
    assert tiers["head_common"]["count"] == 102
    
    assert sum(t["count"] for t in tiers.values()) == 12608
    assert len(manifest["ledgar_classification_error_analysis"]["macro_f1_collapse_root_cause"]) > 50

def test_4_contractnli_baseline_error_flows(manifest):
    """Verifies ContractNLI TF-IDF Linear SVM baseline confusion matrix and error flows."""
    cnli = manifest["contractnli_baseline_error_analysis"]
    assert cnli["status"] == "COMPLETED"
    assert cnli["total_test_instances"] == 2091
    assert cnli["accuracy"] == pytest.approx(0.655667, abs=1e-4)
    assert cnli["macro_f1"] == pytest.approx(0.584392, abs=1e-4)
    
    cm = cnli["confusion_matrix"]
    assert cm["labels"] == ["Contradiction", "Entailment", "NotMentioned"]
    matrix = cm["matrix"]
    assert matrix[0] == [81, 90, 49] # Contradiction row
    assert matrix[1] == [20, 834, 114] # Entailment row
    assert matrix[2] == [64, 383, 456] # NotMentioned row
    
    # Verify primary error flow: NotMentioned -> Entailment is 383 instances
    flows = {f["flow"]: f for f in cnli["dominant_confusion_flows"]}
    assert "NotMentioned -> Entailment" in flows
    assert flows["NotMentioned -> Entailment"]["error_count"] == 383
    assert flows["NotMentioned -> Entailment"]["percentage_of_true_class"] == 42.41
    
    assert "Contradiction -> Entailment" in flows
    assert flows["Contradiction -> Entailment"]["error_count"] == 90

def test_5_representative_cases_provenance(manifest):
    """Verifies that representative concrete error cases are well-formed and categorized."""
    cases = manifest["representative_concrete_cases"]
    assert len(cases) == 4
    
    case_ids = [c["case_id"] for c in cases]
    assert "ERR_CASE_01_TAXONOMY_COLLISION" in case_ids
    assert "ERR_CASE_02_SUBTHRESHOLD_FALSE_NEGATIVE" in case_ids
    assert "ERR_CASE_03_CONTRACTNLI_LEXICAL_OVERLAP" in case_ids
    assert "ERR_CASE_04_ATTRIBUTION_FUNCTION_WORD_BIAS" in case_ids
    
    for c in cases:
        assert len(c["analysis"]) > 20
        assert "category" in c

def test_6_failure_mode_taxonomy(manifest):
    """Verifies that the failure mode taxonomy covers all 5 systemic failure modes."""
    modes = manifest["failure_mode_taxonomy"]["failure_modes"]
    assert len(modes) == 5
    
    mode_ids = {m["id"] for m in modes}
    expected_ids = {
        "FM_01_TAIL_STARVATION",
        "FM_02_THRESHOLD_DILEMMA",
        "FM_03_FROZEN_ENCODER_BOTTLENECK",
        "FM_04_BAG_OF_WORDS_FALLACY",
        "FM_05_ATTRIBUTION_ARTIFACTS"
    }
    assert mode_ids == expected_ids
