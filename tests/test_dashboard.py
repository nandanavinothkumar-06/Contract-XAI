import os
import json
import pytest

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MANIFEST_PATH = os.path.join(WORKSPACE_ROOT, "results", "task024", "task024_dashboard_manifest.json")
STATIC_HTML_PATH = os.path.join(WORKSPACE_ROOT, "results", "task024", "index.html")
EXPECTED_MODEL_SHA256 = "7cd08d2c086f5046eb2b5ef85aa68fec84b5ce7ae3c12bef50c1baea096a8e5f"

from src.dashboard.data_loader import DashboardDataLoader
from src.dashboard.app import app

@pytest.fixture(scope="module")
def manifest():
    assert os.path.exists(MANIFEST_PATH), f"Task 024 manifest not found at {MANIFEST_PATH}"
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_1_dashboard_manifest_integrity(manifest):
    """Verifies Task 024 manifest schema, completed status, and provenance records."""
    assert manifest["task_id"] == "024"
    assert manifest["task_name"] == "Build dashboard"
    assert manifest["status"] == "COMPLETED"
    
    prov = manifest["displayed_provenance"]
    assert prov["model_weights_sha256"] == EXPECTED_MODEL_SHA256
    assert prov["operating_threshold"] == 0.04
    assert "NOT A VALIDATED LEGAL DECISION-MAKER" in prov["safety_notice"]
    
    assert manifest["acceptance_criteria_verification"]["status"] == "VERIFIED"
    assert manifest["acceptance_criteria_verification"]["all_data_sources_verified"] is True

def test_2_dashboard_data_loader_ledgar():
    """Verifies that DashboardDataLoader correctly parses and reports LEDGAR metrics."""
    loader = DashboardDataLoader(WORKSPACE_ROOT)
    ledgar = loader.get_ledgar_data()
    
    assert ledgar["status"] == "AVAILABLE"
    assert ledgar["test_sample_count"] == 87956
    assert ledgar["actual_positive_instances"] == 105283
    
    c_met = ledgar["calibrated_metrics_tau_0_04"]
    assert c_met["threshold"] == 0.04
    assert c_met["true_positives"] == 12699
    assert c_met["false_positives"] == 58947
    assert c_met["false_negatives"] == 92584
    assert c_met["micro_f1"] == 0.1435
    
    b_met = ledgar["baseline_metrics_tau_0_50"]
    assert b_met["threshold"] == 0.50
    assert b_met["true_positives"] == 989
    assert b_met["false_positives"] == 438
    assert b_met["false_negatives"] == 104294
    
    tiers = ledgar["label_frequency_tiers"]
    assert tiers["zero_shot_unlearned"]["count"] == 2833
    assert tiers["extreme_tail_rare"]["count"] == 8465

def test_3_dashboard_data_loader_contractnli():
    """Verifies that DashboardDataLoader accurately extracts ContractNLI confusion matrix and flows."""
    loader = DashboardDataLoader(WORKSPACE_ROOT)
    cnli = loader.get_contractnli_data()
    
    assert cnli["status"] == "AVAILABLE"
    assert cnli["test_sample_count"] == 2091
    assert cnli["accuracy"] == pytest.approx(0.6557, abs=1e-3)
    assert cnli["macro_f1"] == pytest.approx(0.5844, abs=1e-3)
    
    cm = cnli["confusion_matrix"]
    assert cm["matrix"] == [[81, 90, 49], [20, 834, 114], [64, 383, 456]]
    assert cnli["dominant_error_flow"]["count"] == 383
    assert cnli["dominant_error_flow"]["percentage_of_true_class"] == 42.41

def test_4_dashboard_data_loader_graceful_missing_handling(tmp_path):
    """Verifies that missing files are handled gracefully without raising unhandled exceptions."""
    empty_loader = DashboardDataLoader(str(tmp_path))
    
    ledgar = empty_loader.get_ledgar_data()
    assert ledgar["status"] == "UNAVAILABLE"
    
    cnli = empty_loader.get_contractnli_data()
    assert cnli["status"] == "UNAVAILABLE"
    
    rob = empty_loader.get_robustness_data()
    assert rob["status"] == "UNAVAILABLE"
    
    cases = empty_loader.get_error_cases_and_taxonomy()
    assert cases["status"] == "UNAVAILABLE"

def test_5_flask_rest_api_endpoints(client):
    """Verifies that all Flask REST endpoints respond with HTTP 200 and correct JSON structures."""
    # 1. Main UI
    res_index = client.get("/")
    assert res_index.status_code == 200
    html_text = res_index.get_data(as_text=True)
    assert "ContractRisk-XAI" in html_text
    assert "NOT a validated legal decision-maker" in html_text
    assert "12,699" in html_text
    assert "58,947" in html_text
    
    # 2. Provenance API
    res_prov = client.get("/api/provenance")
    assert res_prov.status_code == 200
    prov_data = res_prov.get_json()
    assert prov_data["expected_weights_sha256"] == EXPECTED_MODEL_SHA256
    assert prov_data["weights_file_exists"] is True
    
    # 3. LEDGAR API
    res_ledgar = client.get("/api/ledgar")
    assert res_ledgar.status_code == 200
    ledgar_data = res_ledgar.get_json()
    assert ledgar_data["calibrated_metrics_tau_0_04"]["micro_f1"] == 0.1435
    
    # 4. ContractNLI API
    res_cnli = client.get("/api/contractnli")
    assert res_cnli.status_code == 200
    cnli_data = res_cnli.get_json()
    assert cnli_data["dominant_error_flow"]["count"] == 383
    
    # 5. Health API
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    health_data = res_health.get_json()
    assert health_data["status"] == "HEALTHY"
    assert health_data["data_sources"]["model_weights"] is True

def test_6_static_dashboard_compiled_and_sanitized():
    """Verifies that the compiled standalone static dashboard exists, contains all tabs, and has legal notices."""
    assert os.path.exists(STATIC_HTML_PATH)
    assert os.path.getsize(STATIC_HTML_PATH) > 5000
    
    with open(STATIC_HTML_PATH, "r", encoding="utf-8") as f:
        content = f.read()
        
    assert "ContractRisk-XAI" in content
    assert "LEGAL SAFETY NOTICE & ACADEMIC RESEARCH DISCLAIMER" in content
    assert "NOT a validated legal decision-maker" in content
    assert "tab-overview" in content
    assert "tab-ledgar" in content
    assert "tab-contractnli" in content
    assert "tab-cases" in content
    assert "tab-robustness" in content
    assert "tab-taxonomy" in content
