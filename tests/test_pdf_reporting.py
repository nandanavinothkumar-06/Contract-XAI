"""
Unit and Integration Tests for Task 025: Academic PDF Reporting.
Verifies PDF generation, page count, section ordering, exact metric traceability,
figure existence, and research integrity disclaimers.
"""

import os
import json
import hashlib
import pytest
import pypdf

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TASK025_DIR = os.path.join(WORKSPACE_ROOT, "results", "task025")
PDF_PATH = os.path.join(TASK025_DIR, "CONTRACTRISK_XAI_ACADEMIC_REPORT.pdf")
MD_PATH = os.path.join(TASK025_DIR, "CONTRACTRISK_XAI_ACADEMIC_REPORT.md")
MANIFEST_PATH = os.path.join(TASK025_DIR, "task025_pdf_manifest.json")
FIGURES_DIR = os.path.join(TASK025_DIR, "figures")

EXPECTED_WEIGHTS_SHA256 = "7cd08d2c086f5046eb2b5ef85aa68fec84b5ce7ae3c12bef50c1baea096a8e5f"

def test_task025_files_exist():
    """Verify that all Task 025 output deliverables exist and have valid sizes."""
    assert os.path.exists(PDF_PATH), f"PDF report missing: {PDF_PATH}"
    assert os.path.getsize(PDF_PATH) > 500_000, f"PDF report too small: {os.path.getsize(PDF_PATH)} bytes"

    assert os.path.exists(MD_PATH), f"Markdown source missing: {MD_PATH}"
    assert os.path.getsize(MD_PATH) > 10_000, f"Markdown source too small: {os.path.getsize(MD_PATH)} bytes"

    assert os.path.exists(MANIFEST_PATH), f"Manifest missing: {MANIFEST_PATH}"
    assert os.path.exists(FIGURES_DIR), f"Figures directory missing: {FIGURES_DIR}"

def test_task025_figures_valid():
    """Verify that all 6 academic figures are generated and have PNG headers."""
    for i in range(1, 7):
        fig_name = f"figure{i}_"
        matching = [f for f in os.listdir(FIGURES_DIR) if f.startswith(f"figure{i}")]
        assert len(matching) == 1, f"Expected 1 matching file for figure {i}, found {matching}"
        fig_path = os.path.join(FIGURES_DIR, matching[0])
        assert os.path.getsize(fig_path) > 10_000, f"Figure {matching[0]} too small"
        with open(fig_path, "rb") as f:
            header = f.read(8)
            # Standard PNG magic number: \x89PNG\r\n\x1a\n
            assert header == b"\x89PNG\r\n\x1a\n", f"File {matching[0]} is not a valid PNG"

def test_pdf_structure_and_page_count():
    """Verify that the PDF opens, has valid structure, and contains at least 5 pages."""
    reader = pypdf.PdfReader(PDF_PATH)
    page_count = len(reader.pages)
    assert page_count >= 5, f"Expected >= 5 pages, got {page_count}"
    assert page_count <= 15, f"Unusually high page count: {page_count}"

def test_pdf_all_18_sections_present():
    """Verify that all 18 numbered sections are present in the PDF text."""
    reader = pypdf.PdfReader(PDF_PATH)
    full_text = "\n".join([p.extract_text() or "" for p in reader.pages])

    required_sections = [
        "1. Abstract & Executive Summary",
        "2. Problem Statement, Research Questions & Objectives",
        "3. Research Methodology & Verification Safeguards",
        "4. System Architecture & Engineering Pipelines",
        "5. Dataset Descriptions, Legal Provenance & Split Invariants",
        "6. Non-Destructive Preprocessing & Hierarchical Clause Segmentation",
        "7. Model Architecture, Parameter Isolation & Training Ingestion",
        "8. Evidence Extraction, Saliency Attribution & Offset Invariants",
        "9. Cross-Domain Compatibility & Representation Geometry",
        "10. Component Ablation Studies",
        "11. Empirical Robustness & Boundary Stress Testing",
        "12. Forensic Error Analysis & Systemic Failure Mode Taxonomy",
        "13. Interactive Dashboard & Algorithmic Governance",
        "14. Comprehensive Results Synthesis & Comparative Discussion",
        "15. Threats to Validity & Research Limitations",
        "16. Conclusions & Roadmap for Future Work",
        "17. Complete Verified References & Bibliography",
        "18. Artifact Provenance, Cryptographic Checksums & Audit Ledger"
    ]

    for section in required_sections:
        assert section in full_text, f"Missing section in PDF: {section}"

def test_pdf_metric_accuracy_against_manifests():
    """Verify that key numerical results in PDF text match source artifacts exactly."""
    reader = pypdf.PdfReader(PDF_PATH)
    full_text = "\n".join([p.extract_text() or "" for p in reader.pages])

    # 1. Model Provenance Hash
    assert EXPECTED_WEIGHTS_SHA256 in full_text, "Model weights SHA-256 missing from PDF"

    # 2. LEDGAR Calibrated Metrics (from TASK019 calibrated JSON)
    calib_json_path = os.path.join(
        WORKSPACE_ROOT, "results", "models", "ledgar_frozen_subset_fresh", "calibrated",
        "TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET_FRESH_CALIBRATED.json"
    )
    with open(calib_json_path, "r", encoding="utf-8") as f:
        calib_data = json.load(f)

    stage2 = calib_data["stage2_held_out_test_evaluation"]
    calib_m = stage2["metrics_at_calibrated_threshold"]
    base_m = stage2["metrics_at_baseline_0_50"]

    assert str(calib_m["micro_f1"]) in full_text, f"Calibrated Micro-F1 {calib_m['micro_f1']} missing"
    assert str(calib_m["macro_f1"]) in full_text, f"Calibrated Macro-F1 {calib_m['macro_f1']} missing"
    assert str(calib_m["weighted_f1"]) in full_text, f"Calibrated Weighted-F1 {calib_m['weighted_f1']} missing"
    assert str(base_m["micro_f1"]) in full_text, f"Baseline Micro-F1 {base_m['micro_f1']} missing"
    assert str(base_m["macro_f1"]) in full_text, f"Baseline Macro-F1 {base_m['macro_f1']} missing"
    assert f"{calib_m['true_positives']:,}" in full_text, f"Calibrated TP {calib_m['true_positives']} missing"
    assert f"{calib_m['false_positives']:,}" in full_text, f"Calibrated FP {calib_m['false_positives']} missing"

    # 3. ContractNLI Baseline (from TASK018 JSON)
    cnli_json_path = os.path.join(WORKSPACE_ROOT, "results", "baseline", "contractnli", "TASK018_CONTRACTNLI_TFIDF_SVM.json")
    with open(cnli_json_path, "r", encoding="utf-8") as f:
        cnli_data = json.load(f)

    assert "65.57%" in full_text or "0.6557" in full_text, "ContractNLI accuracy missing"
    assert "0.5844" in full_text, "ContractNLI Macro-F1 missing"
    assert "42.41%" in full_text, "ContractNLI dominant error flow rate missing"

    # 4. Long-Tail Breakdown & Failure Modes
    assert "2,833" in full_text, "Zero-shot class count 2,833 missing"
    assert "8,465" in full_text, "Extreme tail class count 8,465 missing"
    assert "1,208" in full_text, "Moderate tail class count 1,208 missing"
    assert "102" in full_text, "Head class count 102 missing"
    for fm_id in ["FM-01", "FM-02", "FM-03", "FM-04", "FM-05"]:
        assert fm_id in full_text, f"Failure mode {fm_id} missing from PDF"

def test_pdf_legal_safety_notice_present():
    """Verify that the prominent legal safety notice is present in PDF text."""
    reader = pypdf.PdfReader(PDF_PATH)
    full_text = "\n".join([p.extract_text() or "" for p in reader.pages])

    assert "NOT A VALIDATED LEGAL DECISION-MAKER" in full_text, "Mandatory safety notice missing from PDF"
    assert "CS Research Benchmark Only" in full_text or "computer science research" in full_text

def test_task025_manifest_consistency():
    """Verify the integrity and fields of task025_pdf_manifest.json."""
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["task_id"] == "025"
    assert manifest["task_name"] == "Build PDF reporting"
    assert manifest["status"] == "COMPLETED"
    assert manifest["verification_audit"]["status"] == "VERIFIED"
    assert manifest["pdf_document_metadata"]["page_count"] >= 5
    assert manifest["source_artifacts"]["model_weights"]["sha256"] == EXPECTED_WEIGHTS_SHA256
