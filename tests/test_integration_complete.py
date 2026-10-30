"""
ContractRisk-XAI: Complete Integration Test Suite (Task 026)
Verifies end-to-end integration across Environment, Artifacts, Pipelines,
Dashboard (REST API + Static HTML), and Academic PDF Reporting.
"""

import os
import json
import hashlib
import pytest
import pypdf
import torch

from src.adapters.schema import DatasetRecord, TaskType
from src.preprocessing.pipeline import PreprocessingPipeline
from src.segmentation.pipeline import SegmentationPipeline
from src.segmentation.schema import Segment, SegmentType
from src.context.builder import ContextBuilder
from src.graph.builder import GraphBuilder
from src.graph.query import GraphQueryInterface
from src.graph.schema import RelationType, ResolutionStatus
from src.evidence.aggregation import aggregate_and_rank_evidence
from src.dashboard.app import app
from src.dashboard.data_loader import DashboardDataLoader

WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
EXPECTED_WEIGHTS_SHA256 = "7cd08d2c086f5046eb2b5ef85aa68fec84b5ce7ae3c12bef50c1baea096a8e5f"

def get_file_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()

# =========================================================================
# PHASE 1: ENVIRONMENT AND ARTIFACTS
# =========================================================================

def test_phase1_environment_dependencies():
    """Verify that all core dependencies are installed with compatible versions."""
    import importlib.metadata
    import transformers
    import reportlab
    import flask
    import sklearn
    import numpy
    import pandas
    import matplotlib

    assert torch.__version__.startswith("2.")
    assert int(transformers.__version__.split(".")[0]) >= 4
    assert reportlab.__version__.startswith("5.")
    assert int(pypdf.__version__.split(".")[0]) >= 5
    assert importlib.metadata.version("flask").startswith("3.")
    assert int(sklearn.__version__.split(".")[0]) >= 1

def test_phase1_model_weights_provenance():
    """Verify physical model weights existence, file size, and SHA-256 hash."""
    weights_path = os.path.join(
        WORKSPACE_ROOT, "results", "models", "ledgar_frozen_subset_fresh", "final_model", "model.safetensors"
    )
    assert os.path.exists(weights_path), f"Model weights missing: {weights_path}"
    assert os.path.getsize(weights_path) == 476_116_436, f"Unexpected weights size: {os.path.getsize(weights_path)}"
    actual_sha = get_file_sha256(weights_path)
    assert actual_sha == EXPECTED_WEIGHTS_SHA256, f"Weights hash mismatch: {actual_sha}"

def test_phase1_required_manifests_exist():
    """Verify existence and integrity of all historical task manifests from 018 to 025."""
    required_manifests = [
        os.path.join("results", "baseline", "contractnli", "TASK018_CONTRACTNLI_TFIDF_SVM.json"),
        os.path.join("results", "models", "ledgar_frozen_subset_fresh", "calibrated", "TASK019_LEDGAR_LEGALBERT_FROZEN_SUBSET_FRESH_CALIBRATED.json"),
        os.path.join("results", "task020", "task020_cross_domain_manifest.json"),
        os.path.join("results", "task021", "task021_ablation_manifest.json"),
        os.path.join("results", "task022", "task022_robustness_manifest.json"),
        os.path.join("results", "task023", "task023_error_analysis_manifest.json"),
        os.path.join("results", "task024", "task024_dashboard_manifest.json"),
        os.path.join("results", "task025", "task025_pdf_manifest.json"),
    ]
    for rel_path in required_manifests:
        full_path = os.path.join(WORKSPACE_ROOT, rel_path)
        assert os.path.exists(full_path), f"Required manifest missing: {full_path}"
        assert os.path.getsize(full_path) > 100, f"Manifest file empty: {full_path}"
        with open(full_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert isinstance(data, dict), f"Manifest {rel_path} is not a valid JSON dict"

# =========================================================================
# PHASE 2: PIPELINE INTEGRATION
# =========================================================================

def test_phase2_preprocessing_pipeline_and_offsets():
    """Verify non-destructive preprocessing preserves exact character offsets and metadata."""
    from src.adapters.schema import EvidenceSpan as AdapterEvidenceSpan
    raw_text = "CONFIDENTIALITY AGREEMENT\n\n1. Obligations. The Recipient shall maintain secrecy."
    span = AdapterEvidenceSpan(start=58, end=74, text="maintain secrecy", source_field="text")
    rec = DatasetRecord.model_construct(
        record_id="REC_001",
        source_dataset="TEST_CORPUS",
        source_document_id="DOC_001",
        contract_id="CTR_001",
        clause_id="SEC_1",
        text=raw_text,
        task=TaskType.QA_SPAN_EXTRACTION,
        original_label="Confidentiality",
        normalized_label="confidentiality",
        evidence=[span],
        rationale=None,
        domain="Commercial",
        language="en",
        annotation_source="expert",
        source_reference=None,
        license_status="open",
        access_status="verified",
        metadata={"is_test_fixture": True}
    )
    p = PreprocessingPipeline()
    processed = p.preprocess_record(rec)
    assert processed.original_record.text == raw_text
    assert processed.processed_text is not None

def test_phase2_segmentation_pipeline_hierarchy():
    """Verify clause segmentation extracts numbering and structural hierarchy."""
    text = "CONFIDENTIALITY\n\n1. First clause.\n\n1.1 Subclause definition."
    rec = DatasetRecord.model_construct(
        record_id="REC_002", source_dataset="TEST", source_document_id="DOC_002", contract_id=None, clause_id=None,
        text=text, task=TaskType.QA_SPAN_EXTRACTION, original_label="Label", normalized_label=None,
        evidence=[], rationale=None, domain=None, language=None, annotation_source=None, source_reference=None,
        license_status=None, access_status=None, metadata={"is_test_fixture": True}
    )
    p = PreprocessingPipeline()
    prep = p.preprocess_record(rec)

    sp = SegmentationPipeline()
    doc = sp.segment_record(prep)
    assert len(doc.segments) >= 2
    # Verify segments have valid coordinates
    for seg in doc.segments:
        assert seg.original_start >= 0
        assert seg.original_end <= len(text)
        assert text[seg.original_start : seg.original_end] == seg.text

def test_phase2_context_builder_budget_invariants():
    """Verify context builder enforces token budget without target truncation."""
    class DummyTokenizer:
        def tokenize(self, text):
            return text.split()
        def num_special_tokens_to_add(self):
            return 2

    class DummyWrapper:
        def __init__(self):
            self.tokenizer = DummyTokenizer()

    segments = [
        Segment(
            segment_id=f"s{i}",
            segment_type=SegmentType.CLAUSE,
            text=f"Clause text number {i} with several words for testing context budgeting.",
            original_start=i * 50,
            original_end=i * 50 + 45,
            sequence=i,
            source_dataset="TEST",
            source_document_id="DOC_CTX",
            metadata={"partition": "TEST"}
        ) for i in range(10)
    ]

    builder = ContextBuilder(DummyWrapper(), max_sequence_length=60)
    ctx_res = builder.build(segments[5], segments, strategy="PREVIOUS_NEXT")
    assert len(ctx_res.components) >= 1
    # Target must always be present
    target_comp = [c for c in ctx_res.components if c.role == "TARGET"]
    assert len(target_comp) == 1
    assert target_comp[0].text == segments[5].text

def test_phase2_graph_builder_and_query_interface():
    """Verify relationship graph constructs nodes, cross-references, and traverses safely."""
    segments = [
        Segment(
            segment_id="s0", segment_type=SegmentType.SECTION_HEADING, text="1. Termination",
            original_start=0, original_end=14, sequence=0, source_dataset="TEST", source_document_id="DOC_G",
            metadata={"partition": "TRAIN"}
        ),
        Segment(
            segment_id="s1", segment_type=SegmentType.CLAUSE, text="1.1 The contract terminates as subject to Section 2.",
            original_start=15, original_end=67, sequence=1, parent_segment_id="s0", source_dataset="TEST",
            source_document_id="DOC_G", metadata={"partition": "TRAIN"}
        ),
        Segment(
            segment_id="s2", segment_type=SegmentType.SECTION_HEADING, text="2. Obligations",
            original_start=68, original_end=82, sequence=2, source_dataset="TEST",
            source_document_id="DOC_G", metadata={"partition": "TRAIN"}
        )
    ]
    builder = GraphBuilder()
    graph = builder.build(segments)
    assert len(graph.nodes) == 3

    query = GraphQueryInterface(graph)
    parents = query.get_parents("s1")
    assert len(parents) == 1
    assert parents[0].clause_id == "s0"

    refs = query.get_cross_references("s1")
    assert len(refs) == 1
    assert refs[0].resolution_status == ResolutionStatus.RESOLVED
    assert refs[0].target_node == "DOC_G_s2"

def test_phase2_evidence_aggregation_invariants():
    """Verify evidence aggregation preserves 100% exact substring match."""
    text = "The quick brown fox jumps over the lazy dog"
    token_scores = [0.1, 0.9, 0.85, 0.2, 0.1, 0.1, 0.1, 0.1, 0.1]
    offsets = [(0, 3), (4, 9), (10, 15), (16, 19), (20, 25), (26, 30), (31, 34), (35, 39), (40, 43)]
    special_tokens_mask = [0] * len(token_scores)

    spans = aggregate_and_rank_evidence(
        token_scores=token_scores,
        offsets=offsets,
        special_tokens_mask=special_tokens_mask,
        source_text=text,
        top_k=2
    )
    assert len(spans) > 0
    top_span = spans[0]
    assert top_span.text == "quick brown"
    assert top_span.source_start == 4
    assert top_span.source_end == 15
    assert text[top_span.source_start : top_span.source_end] == top_span.text

# =========================================================================
# PHASE 3: DASHBOARD INTEGRATION
# =========================================================================

@pytest.fixture
def dashboard_client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

def test_phase3_dashboard_routes(dashboard_client):
    """Test all dashboard routes and verify HTTP 200, valid JSON/HTML, and safety notice."""
    # 1. Main Page
    res_root = dashboard_client.get("/")
    assert res_root.status_code == 200
    html_text = res_root.get_data(as_text=True)
    assert "ContractRisk-XAI" in html_text
    assert "NOT a validated legal decision-maker" in html_text

    # 2. API Health
    res_health = dashboard_client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.get_json()["status"] == "HEALTHY"

    # 3. API Provenance
    res_prov = dashboard_client.get("/api/provenance")
    assert res_prov.status_code == 200
    prov = res_prov.get_json()
    assert prov["expected_weights_sha256"] == EXPECTED_WEIGHTS_SHA256
    assert prov["output_dimensions"] == 12407
    assert "NOT A VALIDATED LEGAL DECISION-MAKER" in prov["legal_safety_notice"]

    # 4. API LEDGAR
    res_ledgar = dashboard_client.get("/api/ledgar")
    assert res_ledgar.status_code == 200
    ledgar = res_ledgar.get_json()
    assert ledgar["status"] == "AVAILABLE"
    assert ledgar["calibrated_metrics_tau_0_04"]["micro_f1"] == 0.1435
    assert ledgar["baseline_metrics_tau_0_50"]["micro_f1"] == 0.0185
    assert ledgar["label_frequency_tiers"]["zero_shot_unlearned"]["count"] == 2833

    # 5. API ContractNLI
    res_cnli = dashboard_client.get("/api/contractnli")
    assert res_cnli.status_code == 200
    cnli = res_cnli.get_json()
    assert cnli["status"] == "AVAILABLE"
    assert round(cnli["accuracy"], 4) == 0.6557
    assert cnli["dominant_error_flow"]["count"] == 383

    # 6. API Cross-Domain
    res_cd = dashboard_client.get("/api/cross_domain")
    assert res_cd.status_code == 200
    cd = res_cd.get_json()
    assert cd["status"] == "AVAILABLE"
    assert cd["concept_separation_margin"] == 0.0686

    # 7. API Robustness
    res_rob = dashboard_client.get("/api/robustness")
    assert res_rob.status_code == 200
    rob = res_rob.get_json()
    assert rob["status"] == "AVAILABLE"
    assert rob["attribution_character_invariants"] is True

    # 8. API Cases
    res_cases = dashboard_client.get("/api/cases")
    assert res_cases.status_code == 200
    cases_data = res_cases.get_json()
    assert cases_data["status"] == "AVAILABLE"
    assert len(cases_data["cases"]) >= 4
    assert len(cases_data["failure_modes"]) >= 5

def test_phase3_dashboard_missing_artifact_graceful_fallback():
    """Verify that data loader gracefully returns UNAVAILABLE when pointed to empty root."""
    empty_loader = DashboardDataLoader(workspace_root=os.path.join(WORKSPACE_ROOT, "non_existent_dir"))
    prov = empty_loader.get_provenance()
    assert prov["weights_file_exists"] is False

    ledgar = empty_loader.get_ledgar_data()
    assert ledgar["status"] == "UNAVAILABLE"

    cnli = empty_loader.get_contractnli_data()
    assert cnli["status"] == "UNAVAILABLE"

    cd = empty_loader.get_cross_domain_data()
    assert cd["status"] == "UNAVAILABLE"

def test_phase3_static_dashboard_file():
    """Verify static dashboard HTML exists and contains safety disclaimer."""
    static_html_path = os.path.join(WORKSPACE_ROOT, "results", "task024", "index.html")
    assert os.path.exists(static_html_path), "Static dashboard index.html missing"
    assert os.path.getsize(static_html_path) > 20_000, "Static dashboard index.html too small"
    with open(static_html_path, "r", encoding="utf-8") as f:
        html = f.read()
        assert "NOT a validated legal decision-maker" in html
        assert "ContractRisk-XAI" in html

# =========================================================================
# PHASE 4: REPORTING INTEGRATION
# =========================================================================

def test_phase4_pdf_integrity_and_disclaimers():
    """Verify PDF report exists, opens cleanly, has 7 pages, all 18 sections, and disclaimers."""
    pdf_path = os.path.join(WORKSPACE_ROOT, "results", "task025", "CONTRACTRISK_XAI_ACADEMIC_REPORT.pdf")
    assert os.path.exists(pdf_path), f"PDF missing: {pdf_path}"
    assert os.path.getsize(pdf_path) > 1_000_000, f"PDF too small: {os.path.getsize(pdf_path)}"

    reader = pypdf.PdfReader(pdf_path)
    assert len(reader.pages) == 7, f"Expected 7 pages, found {len(reader.pages)}"

    full_text = "\n".join([p.extract_text() or "" for p in reader.pages])

    # Required Sections
    for i in range(1, 19):
        assert f"{i}. " in full_text, f"Section {i} missing from PDF"

    # Key Quantitative Metrics
    assert "0.1435" in full_text
    assert "0.0045" in full_text
    assert "0.0937" in full_text
    assert "0.0185" in full_text
    assert "12,699" in full_text
    assert "58,947" in full_text
    assert "65.57%" in full_text
    assert "42.41%" in full_text
    assert "0.0686" in full_text
    assert "2,833" in full_text
    assert "8,465" in full_text
    assert EXPECTED_WEIGHTS_SHA256 in full_text

    # Legal Safety Notice on every page
    for i, page in enumerate(reader.pages):
        page_txt = page.extract_text() or ""
        assert "NOT A VALIDATED LEGAL DECISION-MAKER" in page_txt, f"Safety notice missing from page {i+1}"
