import os
import json
import pytest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "results", "task022", "task022_robustness_manifest.json")
EXPECTED_MODEL_SHA256 = "7cd08d2c086f5046eb2b5ef85aa68fec84b5ce7ae3c12bef50c1baea096a8e5f"

@pytest.fixture(scope="module")
def manifest():
    assert os.path.exists(MANIFEST_PATH), f"Task 022 manifest not found at {MANIFEST_PATH}"
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def test_1_manifest_provenance_and_integrity(manifest):
    """Verifies Task 022 manifest structure, completion status, and model weight provenance."""
    assert manifest["task_id"] == "022"
    assert manifest["task_name"] == "Run robustness tests"
    assert manifest["status"] == "COMPLETED"
    assert manifest["model_weights_sha256"] == EXPECTED_MODEL_SHA256
    assert os.path.exists(os.path.join(WORKSPACE_ROOT, manifest["model_weights_path"]))
    assert manifest["acceptance_criteria_verification"]["all_robustness_dimensions_verified"] is True
    assert manifest["acceptance_criteria_verification"]["status"] == "VERIFIED"

def test_2_input_perturbation_stability(manifest):
    """Verifies predictive stability and representation invariance under text perturbations."""
    exp1 = manifest["experiment_1_input_perturbations"]
    assert exp1["status"] == "COMPLETED"
    
    expected_types = {"ORIGINAL", "UPPERCASE", "WHITESPACE_FORMATTING", "TYPOGRAPHICAL_NOISE", "ENTITY_SUBSTITUTION"}
    assert set(exp1["evaluated_perturbation_types"]) == expected_types
    
    summary = exp1["summary_by_perturbation"]
    # Verify cosine similarities are above robustness thresholds
    assert summary["ORIGINAL"]["mean_probability_cosine_similarity"] == 1.0
    assert summary["UPPERCASE"]["mean_probability_cosine_similarity"] >= 0.99
    assert summary["WHITESPACE_FORMATTING"]["mean_probability_cosine_similarity"] >= 0.99
    assert summary["TYPOGRAPHICAL_NOISE"]["mean_probability_cosine_similarity"] >= 0.95
    assert summary["ENTITY_SUBSTITUTION"]["mean_probability_cosine_similarity"] >= 0.90
    
    # Check Jaccard overlap of predicted label sets at calibrated operating point tau* = 0.04
    assert summary["UPPERCASE"]["mean_prediction_jaccard_similarity"] >= 0.90
    assert summary["TYPOGRAPHICAL_NOISE"]["mean_prediction_jaccard_similarity"] >= 0.70
    assert summary["ENTITY_SUBSTITUTION"]["mean_prediction_jaccard_similarity"] >= 0.70

def test_3_context_stress_and_invariants(manifest):
    """Verifies target clause integrity under extreme context overflow, giant targets, and cross-document security."""
    exp2 = manifest["experiment_2_context_stress_and_invariants"]
    assert exp2["status"] == "COMPLETED"
    assert exp2["all_invariants_passed"] is True
    
    results = {r["test_name"]: r for r in exp2["stress_test_results"]}
    
    # 1. Budget overflow stress: Target preserved, context components truncated/excluded
    overflow = results["BUDGET_OVERFLOW_STRESS"]
    assert overflow["invariant_holds"] is True
    assert overflow["target_truncated"] is False
    assert overflow["context_truncated"] is True
    assert overflow["excluded_components"] > 0
    
    # 2. Giant target overflow: Target exceeds budget, truncation flag accurately set
    giant = results["GIANT_TARGET_OVERFLOW"]
    assert giant["invariant_holds"] is True
    assert giant["target_truncated"] is True
    
    # 3. Singleton boundary degradation: Isolated single clause builds without crash
    singleton = results["SINGLETON_BOUNDARY_DEGRADATION"]
    assert singleton["invariant_holds"] is True
    assert singleton["target_truncated"] is False
    
    # 4. Cross-document security: Multi-document injection strictly blocked
    cross_doc = results["CROSS_DOCUMENT_LEAKAGE_SECURITY"]
    assert cross_doc["invariant_holds"] is True
    assert cross_doc["leakage_blocked"] is True

def test_4_evidence_attribution_invariants_and_gini_caveat(manifest):
    """Verifies exact character offsets and resolves the Task 021 token Gini sparsity caveat."""
    exp3 = manifest["experiment_3_evidence_attribution_robustness"]
    assert exp3["status"] == "COMPLETED"
    assert exp3["all_character_offsets_verified"] is True
    
    evals = exp3["evaluations"]
    assert len(evals) >= 4
    
    for item in evals:
        # Every test case must have 100% verified character offsets
        assert item["character_offset_invariant_100pct"] is True
        assert item["alignment_status"] == "SUCCESS"
        for span in item["spans"]:
            assert span["offset_verified"] is True
            assert span["end"] > span["start"]
        
        # Verify resolution of Task 021 Gini caveat:
        # True full-sequence token Gini reflects genuine token sparsity across sequence tokens
        assert item["full_sequence_token_gini_sparsity"] > 0.30
        assert item["sequence_token_count"] >= 15
        # The full sequence Gini is distinct from the artificial K=3 span Gini
        assert item["full_sequence_token_gini_sparsity"] != item["extracted_span_gini_sparsity"]

def test_5_graph_topology_robustness_and_cyclicity(manifest):
    """Verifies that circular references and dangling citations terminate cleanly without infinite recursion."""
    exp4 = manifest["experiment_4_graph_topology_and_cyclicity"]
    assert exp4["status"] == "COMPLETED"
    assert exp4["mutual_cyclic_reference_handled"] is True
    assert exp4["dangling_reference_handled_gracefully"] is True
    assert exp4["dangling_reference_status"] == "UNRESOLVED"
    assert exp4["infinite_recursion_prevented_in_traversal"] is True
    assert exp4["node_count"] > 0
    assert exp4["edge_count"] > 0

def test_6_pathological_edge_case_and_failure_handling(manifest):
    """Verifies graceful handling of empty, whitespace, single-word, and numeric/symbolic inputs."""
    exp5 = manifest["experiment_5_edge_case_and_failure_handling"]
    assert exp5["status"] == "COMPLETED"
    assert exp5["all_pathological_cases_handled_safely"] is True
    
    results = {r["case_id"]: r for r in exp5["results"]}
    
    # Empty string must not crash and must emit 0 spans
    assert results["PATH_01_EMPTY_STRING"]["handled_safely"] is True
    assert results["PATH_01_EMPTY_STRING"]["spans_count"] == 0
    
    # Whitespace-only must not crash and must emit 0 spans
    assert results["PATH_02_WHITESPACE_ONLY"]["handled_safely"] is True
    assert results["PATH_02_WHITESPACE_ONLY"]["spans_count"] == 0
    
    # Single-word heading extracts valid spans
    assert results["PATH_03_SINGLE_WORD_HEADING"]["handled_safely"] is True
    assert results["PATH_03_SINGLE_WORD_HEADING"]["spans_count"] >= 1
    
    # Numeric and special characters (§, %, $, []) parse cleanly
    assert results["PATH_04_NUMERIC_AND_SPECIAL_CHARS"]["handled_safely"] is True
    assert results["PATH_04_NUMERIC_AND_SPECIAL_CHARS"]["spans_count"] >= 1
