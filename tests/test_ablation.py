import os
import json
import pytest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "results", "task021", "task021_ablation_manifest.json")

@pytest.fixture(scope="module")
def manifest():
    assert os.path.exists(MANIFEST_PATH), f"Manifest not found at {MANIFEST_PATH}"
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def test_1_threshold_ablation_sweep(manifest):
    exp_a = manifest["experiment_a_threshold_ablation"]
    assert exp_a["status"] == "COMPLETED"
    assert exp_a["calibrated_threshold"] == 0.04
    eval_thresholds = exp_a["evaluated_thresholds"]
    assert eval_thresholds == [0.02, 0.04, 0.10, 0.20, 0.50]
    
    sweep = exp_a["data"]["empirical_test_sample_sweep"]
    assert len(sweep) == 5
    # Verify peak Micro-F1 occurs at calibrated tau = 0.04
    f1_dict = {s["threshold"]: s["micro_f1"] for s in sweep}
    assert f1_dict[0.04] >= f1_dict[0.50], "Calibrated threshold must exceed uncalibrated baseline"
    assert f1_dict[0.04] >= f1_dict[0.10], "Calibrated threshold must exceed conservative threshold"

def test_2_calibrated_threshold_preservation(manifest):
    exp_a = manifest["experiment_a_threshold_ablation"]
    calib_data = exp_a["data"]
    assert calib_data["calibrated_optimal_threshold_tau_star"] == 0.04
    assert calib_data["selection_split"] == "validation"
    assert calib_data["selection_rule"] == "argmax(validation_micro_f1)"
    
    # Check that baseline comparison anchor exists
    anchors = calib_data["full_held_out_test_metrics_anchors"]
    assert anchors["tau_0_04_calibrated"]["micro_f1"] == 0.1435
    assert anchors["tau_0_50_baseline"]["micro_f1"] == 0.0185
    assert anchors["relative_f1_gain_pct"] > 600.0

def test_3_context_ablation_strategies(manifest):
    exp_b = manifest["experiment_b_context_ablation"]
    assert exp_b["status"] == "COMPLETED"
    strategies = exp_b["evaluated_strategies"]
    assert set(strategies) == {"NONE", "PREVIOUS_NEXT", "WINDOW", "PARENT_CHILD"}
    
    evals = {e["strategy"]: e for e in exp_b["strategy_evaluations"]}
    assert len(evals) == 4
    # NONE has 1 component (target only)
    assert evals["NONE"]["component_count"] == 1
    assert evals["PREVIOUS_NEXT"]["component_count"] == 3
    assert evals["WINDOW"]["component_count"] == 5

def test_4_context_target_preservation_invariant(manifest):
    exp_b = manifest["experiment_b_context_ablation"]
    assert exp_b["leakage_invariants"]["target_preservation_invariant_verified"] is True
    for e in exp_b["strategy_evaluations"]:
        assert e["target_preserved_without_truncation"] is True
        assert e["context_budget_compliant"] is True

def test_5_context_representation_drift(manifest):
    exp_b = manifest["experiment_b_context_ablation"]
    evals = {e["strategy"]: e for e in exp_b["strategy_evaluations"]}
    # All strategies should have cosine similarity between 0.7 and 1.0
    for strat, data in evals.items():
        sim = data["cosine_similarity_to_isolated_target"]
        assert 0.7 <= sim <= 1.0, f"Strategy {strat} similarity {sim} out of expected range"

def test_6_graph_topology_ablation_variants(manifest):
    exp_c = manifest["experiment_c_graph_topology_ablation"]
    assert exp_c["status"] == "COMPLETED"
    topologies = exp_c["topologies_evaluated"]
    assert set(topologies) == {"FULL_GRAPH", "HIERARCHICAL_ONLY", "SEQUENTIAL_ONLY", "DISJOINT_NODES"}
    
    res = {r["topology_variant"]: r for r in exp_c["results"]}
    # FULL_GRAPH has highest density and resolves references
    assert res["FULL_GRAPH"]["edge_count"] > res["HIERARCHICAL_ONLY"]["edge_count"]
    assert res["FULL_GRAPH"]["resolved_cross_references"] == 3
    assert res["HIERARCHICAL_ONLY"]["resolved_cross_references"] == 0
    assert res["DISJOINT_NODES"]["edge_count"] == 0

def test_7_graph_zero_cross_document_leakage(manifest):
    exp_c = manifest["experiment_c_graph_topology_ablation"]
    assert exp_c["boundary_safety"]["cross_document_edges_strictly_prohibited"] is True
    assert exp_c["boundary_safety"]["boundary_violations_detected"] == 0
    for r in exp_c["results"]:
        assert r["cross_document_boundary_violations"] == 0

def test_8_evidence_attribution_ablation(manifest):
    exp_d = manifest["experiment_d_evidence_attribution_ablation"]
    assert exp_d["status"] == "COMPLETED"
    assert exp_d["method"] == "GradientXInput"
    variants = exp_d["variants_evaluated"]
    assert set(variants) == {"SPAN_AGGREGATED", "RAW_TOKENS", "SIGNED_GRADIENT", "UNWEIGHTED_SPAN"}
    
    res = {r["attribution_variant"]: r for r in exp_d["results"]}
    # UNWEIGHTED_SPAN has 0.0 Gini sparsity
    assert res["UNWEIGHTED_SPAN"]["average_gini_sparsity"] == 0.0
    # SPAN_AGGREGATED has positive Gini sparsity
    assert res["SPAN_AGGREGATED"]["average_gini_sparsity"] > 0.0

def test_9_evidence_character_offset_invariants(manifest):
    exp_d = manifest["experiment_d_evidence_attribution_ablation"]
    assert exp_d["invariants"]["character_offset_invariant_100pct_verified"] is True
    for r in exp_d["results"]:
        assert r["offset_invariants_preserved_100pct"] is True

def test_10_ablation_manifest_integrity(manifest):
    assert manifest["task_id"] == "021"
    assert manifest["task_name"] == "Run ablation"
    assert manifest["status"] == "COMPLETED"
    assert manifest["model_weights_sha256"] == "7cd08d2c086f5046eb2b5ef85aa68fec84b5ce7ae3c12bef50c1baea096a8e5f"
    assert os.path.exists(os.path.join(WORKSPACE_ROOT, manifest["model_weights_path"]))
    assert manifest["acceptance_criteria_verification"]["all_10_criteria_verified"] is True
