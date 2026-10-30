"""
End-to-End Test Suite for CONTRACTRISK-XAI Core NLP Pipeline.

Verifies the complete real execution path on synthetic contract clauses:
Contract upload
  → Text extraction
  → Preprocessing
  → Clause segmentation
  → LegalBERT tokenization and inference (authentic local checkpoint)
  → Risk-label prediction
  → Gradient × Input explainability
  → BM25 statutory retrieval
  → Evidence-aware abstention
  → Reviewable prediction output linked to input clauses.
"""

import os
import io
import json
import uuid
import datetime
import pytest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.persistence.database import Base, get_session_factory
from src.persistence.models import (
    UserRecord,
    DocumentRecord,
    SegmentRecord,
    ReviewRecord,
    ClauseFindingRecord,
    UserRole,
    AccountStatus,
    AdvocateStatus,
    ReviewStatus,
    FindingOrigin,
)
from src.auth.token import TokenManager
from src.auth.password import PasswordManager
from src.ingestion.pipeline import IngestionPipeline
from src.review.service import ReviewService
from src.review.screening import ContractScreeningService, get_contract_screening_service
from src.dashboard.app import app


@pytest.fixture
def nlp_db_engine():
    """Isolated in-memory SQLite database for testing the end-to-end NLP workflow."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def nlp_db_session(nlp_db_engine):
    """Provides a transactional session on the isolated database."""
    session_factory = sessionmaker(bind=nlp_db_engine, expire_on_commit=False)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def test_advocate_user(nlp_db_session):
    """Creates a verified advocate user in the test database."""
    pwd_mgr = PasswordManager()
    user = UserRecord(
        id=str(uuid.uuid4()),
        email="advocate.e2e@legal.in",
        password_hash=pwd_mgr.hash_password("Advocate@Test2026!"),
        full_name="Lead Commercial Advocate",
        role=UserRole.SUPERVISING_LAWYER.value,
        account_status=AccountStatus.ACTIVE.value,
        advocate_status=AdvocateStatus.VERIFIED.value,
        bar_enrolment_id="D/1998/2026",
        state_bar_council="Delhi",
        year_of_enrolment=2026,
    )
    nlp_db_session.add(user)
    nlp_db_session.commit()
    return user


@pytest.fixture
def advocate_jwt_token(test_advocate_user):
    """Generates a valid JWT bearer token for the test advocate."""
    tm = TokenManager()
    return tm.generate_token(test_advocate_user)


@pytest.fixture
def flask_test_client(nlp_db_engine):
    """Flask test client wired to the isolated in-memory test database."""
    app.config["TESTING"] = True
    factory = get_session_factory(nlp_db_engine)
    with patch("src.persistence.database.get_engine", return_value=nlp_db_engine):
        with patch("src.auth.rbac.get_db_session", side_effect=factory):
            with patch("src.review.routes.get_db_session", side_effect=factory):
                with patch("src.auth.routes.get_db_session", side_effect=factory):
                    with app.test_client() as client:
                        yield client


SYNTHETIC_CONTRACT_TEXT = """MASTER SERVICES AGREEMENT

1. Governing Law & Jurisdiction. This agreement shall be governed by and construed in accordance with the substantive laws of India. The courts of competent jurisdiction at New Delhi shall have exclusive jurisdiction to settle any dispute or claim arising out of this agreement.

2. Indemnification Obligations. The Contractor shall indemnify, defend, and hold harmless the Company and its directors, officers, and employees against any and all liabilities, losses, damages, claims, and expenses (including reasonable attorneys' fees) arising out of any breach or willful misconduct.

3. Limitation of Liability. To the maximum extent permitted by applicable law, neither party shall be liable to the other for any indirect, special, incidental, punitive, or consequential damages, or loss of profits, whether in contract, tort, or otherwise.

4. Confidentiality & Non-Disclosure. Each party agrees to maintain in strict confidence all proprietary technical, financial, and business information disclosed by the other party and shall not disclose such information to any third party without prior written consent.
"""


def test_end_to_end_nlp_pipeline_execution(nlp_db_session, test_advocate_user):
    """
    Tests the complete NLP workflow from contract ingestion to reviewable findings:
    - Text extraction
    - Preprocessing & Clause segmentation
    - LegalBERT tokenization & inference
    - Risk prediction
    - Gradient x Input explainability
    - BM25 statutory retrieval
    - Evidence-aware abstention policy (5-tier cascade)
    - Reviewable database persistence
    """
    # 1. Ingestion: Ingest synthetic contract text
    pipeline = IngestionPipeline()
    ingest_result = pipeline.ingest_document(
        file_bytes=SYNTHETIC_CONTRACT_TEXT.encode("utf-8"),
        original_filename="synthetic_commercial_agreement.txt",
        owner_id=test_advocate_user.id,
        session=nlp_db_session,
    )
    assert ingest_result.status.value == "SEGMENTED"
    assert ingest_result.document_id is not None
    assert ingest_result.segment_count >= 4

    # 2. Review Initiation
    review_svc = ReviewService(nlp_db_session)
    review = review_svc.initiate_review(ingest_result.document_id, actor_user=test_advocate_user)
    assert review.id is not None
    assert review.status == ReviewStatus.DOCUMENT_SUBMITTED.value

    # 3. Core NLP Screening Execution
    screening_service = get_contract_screening_service()
    screening_result = screening_service.screen_review(review.id, session=nlp_db_session)
    nlp_db_session.commit()

    # 4. Verify Screening Results
    assert screening_result["review_id"] == review.id
    assert screening_result["findings_count"] >= 4

    # 5. Verify Database Persistence of Findings
    findings = (
        nlp_db_session.query(ClauseFindingRecord)
        .filter_by(review_id=review.id)
        .order_by(ClauseFindingRecord.created_at)
        .all()
    )
    assert len(findings) >= 4

    # Check each clause finding for the required pipeline attributes
    risk_labels = [f.risk_label for f in findings]
    assert "GOVERNING_LAW_DISPUTE" in risk_labels or "INDEMNIFICATION" in risk_labels

    for f in findings:
        # Document and review linkage
        assert f.review_id == review.id
        assert f.document_id == ingest_result.document_id
        assert f.segment_id is not None
        assert f.finding_origin == FindingOrigin.AI_GENERATED.value
        assert f.is_disclosed_to_client is False  # Strict client isolation invariant

        # Model Inference attributes
        assert f.risk_label is not None
        assert f.ai_confidence_score is not None
        assert float(f.ai_confidence_score) >= 0.0  # Real probability, not null or mock

        # AI observation
        assert "Risk Archetype:" in f.ai_observation
        assert "Policy Decision:" in f.ai_observation

        # AI metadata
        meta = json.loads(f.ai_metadata_json)
        assert meta["model_name"] == "nlpaueb/legal-bert-base-uncased"
        assert meta["calibrated_threshold"] == 0.04
        assert "policy_action" in meta
        assert "policy_reason_code" in meta
        assert "disclaimer" in meta

        # Gradient x Input Explainability
        if f.model_attribution_json:
            attr = json.loads(f.model_attribution_json)
            assert attr["method"] == "GradientXInput"
            assert "research_warning" in attr
            assert "attributed_spans" in attr
            assert isinstance(attr["attributed_spans"], list)
            if attr["attributed_spans"]:
                span = attr["attributed_spans"][0]
                assert "text" in span
                assert "raw_score" in span
                assert "source_start" in span
                assert "source_end" in span

        # BM25 Statutory Retrieval Evidence
        assert f.statutory_evidence_json is not None
        stat_ev = json.loads(f.statutory_evidence_json)
        assert "evidence_quality_status" in stat_ev
        assert "passages" in stat_ev
        assert "corpus_disclosure" in stat_ev
        assert "score_disclaimer" in stat_ev

        # Evidence quality status
        assert f.evidence_quality_status is not None


def test_nlp_screening_on_demand_endpoint(flask_test_client, nlp_db_session, test_advocate_user, advocate_jwt_token):
    """
    Tests the POST /api/review/<review_id>/screen route for on-demand screening execution.
    """
    # 1. Ingest document
    pipeline = IngestionPipeline()
    ingest_result = pipeline.ingest_document(
        file_bytes=SYNTHETIC_CONTRACT_TEXT.encode("utf-8"),
        original_filename="synthetic_agreement.txt",
        owner_id=test_advocate_user.id,
        session=nlp_db_session,
    )
    review_svc = ReviewService(nlp_db_session)
    review = review_svc.initiate_review(ingest_result.document_id, actor_user=test_advocate_user)
    nlp_db_session.commit()

    # 2. Invoke /api/review/<review_id>/screen
    headers = {
        "Authorization": f"Bearer {advocate_jwt_token}",
        "Content-Type": "application/json",
    }
    response = flask_test_client.post(f"/api/review/{review.id}/screen", headers=headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["message"] == "Core NLP screening pipeline executed successfully."
    assert data["review_id"] == review.id
    assert data["findings_count"] >= 4
    assert len(data["findings"]) >= 4


def test_contract_upload_runs_automatic_screening(flask_test_client, test_advocate_user, advocate_jwt_token):
    """
    Tests that POST /api/review/upload automatically invokes NLP screening and produces findings.
    """
    headers = {
        "Authorization": f"Bearer {advocate_jwt_token}",
    }
    data = {
        "file": (io.BytesIO(SYNTHETIC_CONTRACT_TEXT.encode("utf-8")), "auto_screening_contract.txt")
    }

    response = flask_test_client.post(
        "/api/review/upload",
        headers=headers,
        data=data,
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    resp_json = response.get_json()
    assert "review_id" in resp_json
    assert resp_json["segments_count"] >= 4
    assert resp_json["findings_count"] >= 4

    # Retrieve review workspace data
    review_id = resp_json["review_id"]
    ws_res = flask_test_client.get(f"/api/review/{review_id}", headers={"Authorization": f"Bearer {advocate_jwt_token}"})
    assert ws_res.status_code == 200
    ws_data = ws_res.get_json()
    assert len(ws_data["findings"]) >= 4

    # Verify first finding contains full NLP output
    finding = ws_data["findings"][0]
    assert finding["finding_origin"] == "AI_GENERATED"
    assert finding["risk_label"] is not None
    assert finding["ai_confidence_score"] is not None
    assert finding["ai_observation"] is not None
    assert finding["statutory_evidence"] is not None
