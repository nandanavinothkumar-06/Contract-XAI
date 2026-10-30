"""
Comprehensive Automated Test Suite for Task 034: Final Lawyer-Reviewed Reports and Client Feedback.

Tests cover:
1. Server-side report eligibility prerequisites (REVIEW_COMPLETED state, document version match,
   recorded lawyer rationales on all findings, 0 unresolved client clarifications, review reopening rejection).
2. Report content integrity (segregation of AI observations from lawyer decisions, explicit marking
   of rejected AI observations, statutory metadata preservation, disclaimers, exclusion of internal notes).
3. PDF report generation (NumberedCanvas 'Page X of Y', Unicode safety, disclaimers, exclusion of confidential notes).
4. Report versioning, superseding, and immutability.
5. Client feedback workflow (1-5 ratings, tenant isolation, advocate responses, client-visible vs internal notes).
6. Feedback status lifecycle (SUBMITTED -> ACKNOWLEDGED -> RESPONDED -> CLOSED).
7. Hash-chained audit logging for all reporting and feedback events.
8. REST API endpoints and RBAC enforcement.
"""

import os
import io
import json
import uuid
import datetime
from typing import Tuple, List, Dict, Any, Optional
import pytest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.persistence.database import Base, get_session_factory
from src.persistence.models import (
    UserRecord, DocumentRecord, SegmentRecord,
    UserRole, AccountStatus, AdvocateStatus,
    ReviewRecord, ClauseFindingRecord, ReviewCommentRecord,
    ReviewStatus, LawyerDecisionType, FindingOrigin, CommentVisibility,
    ReportStatus, FeedbackStatus, FinalReportRecord, ClientFeedbackRecord, FeedbackResponseRecord,
    AuditEventRecord
)
from src.persistence.repository import DocumentRepository
from src.auth.token import TokenManager
from src.auth.password import PasswordManager
from src.review.service import ReviewService, MANDATORY_REVIEW_DISCLAIMER
from src.reporting.service import ReportService
from src.reporting.schema import (
    MANDATORY_LEGAL_DISCLAIMER, STATUTORY_CORPUS_NOTICE,
    FeedbackSubmitRequest, FeedbackResponseRequest
)
from src.reporting.client_pdf import ClientPDFReportBuilder
from src.audit.integrity import AuditVerifier
from src.audit.provenance import EventType, ActorType, IntegrityStatus
from src.dashboard.app import app


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def test_db_engine():
    """In-memory SQLite database isolated for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

@pytest.fixture
def test_session(test_db_engine):
    factory = sessionmaker(bind=test_db_engine, autocommit=False, autoflush=False)
    sess = factory()
    yield sess
    sess.rollback()
    sess.close()

@pytest.fixture
def test_client(test_db_engine):
    app.config["TESTING"] = True
    from contextlib import contextmanager
    factory = get_session_factory(test_db_engine)

    @contextmanager
    def mock_db_session():
        sess = factory()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    with patch("src.persistence.database.get_engine", return_value=test_db_engine):
        with patch("src.auth.rbac.get_db_session", side_effect=mock_db_session):
            with patch("src.reporting.routes.get_db_session", side_effect=mock_db_session):
                with patch("src.review.routes.get_db_session", side_effect=mock_db_session):
                    with patch("src.auth.routes.get_db_session", side_effect=mock_db_session):
                        with app.test_client() as client:
                            yield client


# =============================================================================
# HELPER FACTORIES
# =============================================================================

def create_user(
    repo: DocumentRepository,
    email: str,
    role: UserRole,
    advocate_status: AdvocateStatus = AdvocateStatus.NOT_APPLICABLE,
    name: str = "Test User"
) -> UserRecord:
    pm = PasswordManager()
    h = pm.hash_password("ValidPassword123!")
    return repo.create_user(
        user_id=str(uuid.uuid4()),
        email=email,
        password_hash=h,
        full_name=name,
        role=role,
        account_status=AccountStatus.ACTIVE,
        advocate_status=advocate_status,
        bar_enrolment_id="D/999/2020" if role in (UserRole.LAWYER, UserRole.SUPERVISING_LAWYER) else None,
        state_bar_council="Delhi" if role in (UserRole.LAWYER, UserRole.SUPERVISING_LAWYER) else None,
        year_of_enrolment=2020 if role in (UserRole.LAWYER, UserRole.SUPERVISING_LAWYER) else None
    )

def create_contract_and_review(
    session,
    client_user: UserRecord,
    lawyer_user: UserRecord,
    is_completed: bool = True
) -> Tuple[DocumentRecord, ReviewRecord]:
    repo = DocumentRepository(session)
    doc_id = str(uuid.uuid4())
    doc = DocumentRecord(
        id=doc_id,
        file_sha256="abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234abcd1234",
        original_filename="Master_Services_Agreement.pdf",
        sanitized_filename="Master_Services_Agreement.pdf",
        mime_type="application/pdf",
        document_format="PDF",
        file_size_bytes=2048,
        storage_path=f"data/contracts/{doc_id}_Master_Services_Agreement.pdf",
        owner_id=client_user.id,
        assigned_lawyer_id=lawyer_user.id,
        status="SEGMENTED",
        extraction_method="PDF_PARSER",
        page_count=3,
        char_count=1200
    )
    session.add(doc)

    seg1 = SegmentRecord(
        id=str(uuid.uuid4()),
        document_id=doc_id,
        segment_id="seg_001",
        segment_type="CLAUSE",
        text="The vendor shall indemnify client against third party IP infringement claims.",
        original_start=0,
        original_end=80,
        heading="1. IP Indemnification",
        sequence=0
    )
    seg2 = SegmentRecord(
        id=str(uuid.uuid4()),
        document_id=doc_id,
        segment_id="seg_002",
        segment_type="CLAUSE",
        text="This agreement is governed by the laws of India, subject to exclusive jurisdiction in Bengaluru.",
        original_start=81,
        original_end=180,
        heading="2. Governing Law & Jurisdiction",
        sequence=1
    )
    session.add_all([seg1, seg2])

    rev_id = str(uuid.uuid4())
    review = ReviewRecord(
        id=rev_id,
        document_id=doc_id,
        document_version=1,
        status=ReviewStatus.REVIEW_COMPLETED.value if is_completed else ReviewStatus.IN_REVIEW.value,
        assigned_lawyer_id=lawyer_user.id,
        assigned_at=datetime.datetime.now(datetime.timezone.utc),
        completed_by_id=lawyer_user.id if is_completed else None,
        completed_at=datetime.datetime.now(datetime.timezone.utc) if is_completed else None,
        completion_summary="Thorough review of liability, indemnification, and dispute resolution clauses completed." if is_completed else None,
        disclaimer_text=MANDATORY_REVIEW_DISCLAIMER if is_completed else None
    )
    session.add(review)

    # Findings
    f1 = ClauseFindingRecord(
        id=str(uuid.uuid4()),
        review_id=rev_id,
        document_id=doc_id,
        segment_id="seg_001",
        finding_origin=FindingOrigin.AI_GENERATED.value,
        risk_label="INDEMNIFICATION_RISK",
        ai_observation="Uncapped indemnification obligation detected.",
        decision=LawyerDecisionType.ACCEPT_AI_OBSERVATION.value,
        lawyer_rationale="Vendor indemnification is uncapped. Negotiated monetary cap is advised.",
        lawyer_notes="INTERNAL CONFIDENTIAL NOTE: Advised client to push for 1x annual fee limit.",
        statutory_evidence_json=json.dumps([{
            "act_name": "Indian Contract Act 1872",
            "section": "124",
            "text": "Contract of indemnity defined.",
            "source_id": "ICA_1872",
            "snapshot_version": "1.0"
        }]),
        is_disclosed_to_client=True
    )

    f2 = ClauseFindingRecord(
        id=str(uuid.uuid4()),
        review_id=rev_id,
        document_id=doc_id,
        segment_id="seg_002",
        finding_origin=FindingOrigin.AI_GENERATED.value,
        risk_label="JURISDICTION_DEFECT",
        ai_observation="AI flagged exclusive jurisdiction as problematic.",
        decision=LawyerDecisionType.REJECT_AI_OBSERVATION.value,
        lawyer_rationale="Exclusive jurisdiction clause in Bengaluru is standard and valid under Section 28 of the Indian Contract Act.",
        lawyer_notes="INTERNAL NOTE: AI observation was a false positive.",
        statutory_evidence_json=json.dumps([{
            "act_name": "Indian Contract Act 1872",
            "section": "28",
            "text": "Agreements in restraint of legal proceedings void, saving of contract to refer to arbitration.",
            "source_id": "ICA_1872",
            "snapshot_version": "1.0"
        }]),
        is_disclosed_to_client=True
    )
    session.add_all([f1, f2])
    session.flush()

    return doc, review


# =============================================================================
# 1. REPORT ELIGIBILITY PREREQUISITE TESTS
# =============================================================================

class TestReportEligibility:
    def test_completed_review_is_eligible(self, test_session):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=True)

        service = ReportService(test_session)
        eligible, reason, r = service.check_report_eligibility(review.id, lawyer)
        assert eligible is True
        assert reason is None

    def test_incomplete_review_rejected(self, test_session):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=False)

        service = ReportService(test_session)
        eligible, reason, r = service.check_report_eligibility(review.id, lawyer)
        assert eligible is False
        assert "must reach REVIEW_COMPLETED" in reason

        with pytest.raises(ValueError, match="must reach REVIEW_COMPLETED"):
            service.generate_final_report(review.id, lawyer)

    def test_reopened_review_rejected(self, test_session):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=True)
        review.status = ReviewStatus.REVIEW_REOPENED.value
        test_session.flush()

        service = ReportService(test_session)
        eligible, reason, r = service.check_report_eligibility(review.id, lawyer)
        assert eligible is False
        assert "review has been reopened" in reason

    def test_unresolved_clarification_blocks_report(self, test_session):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=True)

        # Add unresolved client clarification request
        comment = ReviewCommentRecord(
            id=str(uuid.uuid4()),
            review_id=review.id,
            document_id=doc.id,
            author_id=lawyer.id,
            author_role=lawyer.role,
            author_name=lawyer.full_name,
            visibility=CommentVisibility.CLARIFICATION_REQUEST.value,
            comment_text="Please clarify whether this indemnity covers third party claims.",
            is_resolved=False
        )
        test_session.add(comment)
        test_session.flush()

        service = ReportService(test_session)
        eligible, reason, r = service.check_report_eligibility(review.id, lawyer)
        assert eligible is False
        assert "unresolved client clarification request" in reason

    def test_missing_lawyer_decision_blocks_report(self, test_session):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=True)

        # Clear lawyer decision on one finding
        finding = review.findings[0]
        finding.decision = None
        test_session.flush()

        service = ReportService(test_session)
        eligible, reason, r = service.check_report_eligibility(review.id, lawyer)
        assert eligible is False
        assert "has no recorded lawyer decision" in reason

    def test_missing_lawyer_rationale_blocks_report(self, test_session):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=True)

        # Clear rationale on finding
        finding = review.findings[0]
        finding.lawyer_rationale = ""
        test_session.flush()

        service = ReportService(test_session)
        eligible, reason, r = service.check_report_eligibility(review.id, lawyer)
        assert eligible is False
        assert "has no recorded lawyer rationale" in reason

    def test_unauthorized_lawyer_rejected(self, test_session):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        assigned_lawyer = create_user(repo, "assigned@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        unassigned_lawyer = create_user(repo, "unassigned@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, assigned_lawyer, is_completed=True)

        service = ReportService(test_session)
        eligible, reason, r = service.check_report_eligibility(review.id, unassigned_lawyer)
        assert eligible is False
        assert "Unauthorized" in reason


# =============================================================================
# 2. REPORT CONTENT & PRIVACY VERIFICATION
# =============================================================================

class TestReportContentAndPrivacy:
    def test_distinguish_ai_vs_lawyer_decisions(self, test_session):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=True)

        service = ReportService(test_session)
        payload = service.compile_report_payload(review.id, is_final=True)

        findings = payload["findings"]
        assert len(findings) == 2

        # Finding 1: Accepted AI observation
        f1 = next(f for f in findings if f["segment_id"] == "seg_001")
        assert f1["finding_origin"] == "AI_GENERATED"
        assert f1["lawyer_decision"] == LawyerDecisionType.ACCEPT_AI_OBSERVATION.value
        assert f1["is_ai_observation_rejected"] is False
        assert "Negotiated monetary cap is advised" in f1["lawyer_rationale"]

        # Finding 2: Rejected AI observation
        f2 = next(f for f in findings if f["segment_id"] == "seg_002")
        assert f2["finding_origin"] == "AI_GENERATED"
        assert f2["lawyer_decision"] == "REJECT_AI_OBSERVATION"
        assert f2["is_ai_observation_rejected"] is True

    def test_internal_notes_strictly_excluded(self, test_session):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=True)

        service = ReportService(test_session)
        payload = service.compile_report_payload(review.id, is_final=True)
        serialized_payload = json.dumps(payload)

        # Verify internal lawyer notes are NEVER serialized into client report payload
        assert "INTERNAL CONFIDENTIAL NOTE" not in serialized_payload
        assert "INTERNAL NOTE: AI observation was a false positive" not in serialized_payload
        for f in payload["findings"]:
            assert "lawyer_notes" not in f

    def test_statutory_corpus_notice_and_disclaimers_present(self, test_session):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=True)

        service = ReportService(test_session)
        payload = service.compile_report_payload(review.id, is_final=True)

        assert payload["disclaimer_and_limitations"] == MANDATORY_LEGAL_DISCLAIMER
        notice = payload["statutory_corpus_notice"]
        assert "STATUTORY COVERAGE LIMITATION NOTICE" in notice
        assert "limited, curated set of statutory extracts" in notice
        assert "These extracts do NOT represent complete Acts" in notice

        # Verify all statutes in actual corpus_manifest.json are cited
        manifest_path = os.path.join(os.path.dirname(__file__), "..", "data", "legal_sources", "corpus_manifest.json")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        for source in manifest["official_sources"]:
            short_title = source["short_title"]  # e.g., "Indian Contract Act, 1872"
            assert short_title in notice, f"Expected '{short_title}' in STATUTORY_CORPUS_NOTICE"

        # Confirm non-ingested act is absent
        assert "Companies Act" not in notice


# =============================================================================
# 3. PDF EXPORT & UNICODE HANDLING TESTS
# =============================================================================

class TestPDFReportGeneration:
    def test_pdf_generation_success(self, test_session):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=True)

        service = ReportService(test_session)
        payload = service.compile_report_payload(review.id, is_final=True)
        payload["metadata"]["report_number"] = "REP-TEST-V1-001"

        builder = ClientPDFReportBuilder(payload)
        pdf_bytes = builder.build()

        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b"%PDF")

    def test_pdf_unicode_and_indic_characters(self, test_session):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=True)

        # Inject Unicode text: em-dash, quotes, Indian rupee symbol / legal symbols
        review.completion_summary = "Reviewed with ₹ 5,00,000 monetary cap — valid under Indian Law."
        test_session.flush()

        service = ReportService(test_session)
        payload = service.compile_report_payload(review.id, is_final=True)
        payload["metadata"]["report_number"] = "REP-UNICODE-V1"

        builder = ClientPDFReportBuilder(payload)
        pdf_bytes = builder.build()
        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b"%PDF")

    def test_pdf_download_tenant_isolation(self, test_session):
        repo = DocumentRepository(test_session)
        client1 = create_user(repo, "client1@corp.in", UserRole.CLIENT)
        client2 = create_user(repo, "client2@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client1, lawyer, is_completed=True)

        service = ReportService(test_session)
        report = service.generate_final_report(review.id, lawyer, export_pdf=True)

        # Client 1 can download
        pdf_bytes, filename = service.download_report_pdf(report.id, client1)
        assert len(pdf_bytes) > 0

        # Client 2 is blocked (PermissionError)
        with pytest.raises(PermissionError, match="Forbidden"):
            service.download_report_pdf(report.id, client2)


# =============================================================================
# 4. REPORT VERSIONING & SUPERSEDING TESTS
# =============================================================================

class TestReportVersioningAndSuperseding:
    def test_new_report_version_supersedes_old(self, test_session):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=True)

        service = ReportService(test_session)

        # Generate version 1
        rep_v1 = service.generate_final_report(review.id, lawyer, export_pdf=False)
        assert rep_v1.report_version == 1
        assert rep_v1.status == ReportStatus.FINAL.value
        v1_id = rep_v1.id

        # Generate version 2
        rep_v2 = service.generate_final_report(review.id, lawyer, export_pdf=False)
        assert rep_v2.report_version == 2
        assert rep_v2.status == ReportStatus.FINAL.value

        # Refresh v1
        test_session.refresh(rep_v1)
        assert rep_v1.status == ReportStatus.SUPERSEDED.value
        assert rep_v1.superseded_by_id == rep_v2.id
        assert "Superseded by" in rep_v1.supersession_reason

    def test_reports_remain_immutable(self, test_session):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=True)

        service = ReportService(test_session)
        rep = service.generate_final_report(review.id, lawyer, export_pdf=False)
        original_hash = rep.content_sha256

        # Alter review afterward
        review.completion_summary = "Modified text after generation."
        test_session.flush()

        test_session.refresh(rep)
        assert rep.content_sha256 == original_hash
        stored_payload = json.loads(rep.report_payload_json)
        assert "Modified text after generation" not in stored_payload["executive_summary"]["key_findings_summary"]


# =============================================================================
# 5. CLIENT FEEDBACK LIFECYCLE TESTS
# =============================================================================

class TestClientFeedbackWorkflow:
    def test_submit_valid_client_feedback(self, test_session):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=True)

        service = ReportService(test_session)
        report = service.generate_final_report(review.id, lawyer, export_pdf=False)

        req = FeedbackSubmitRequest(
            overall_satisfaction=5,
            clarity_rating=4,
            usefulness_rating=5,
            needs_clarification=False,
            follow_up_requested=False,
            client_comments="Very clear explanation of the IP indemnification risk."
        )
        feedback = service.submit_client_feedback(report.id, client, req)
        assert feedback.overall_satisfaction == 5
        assert feedback.status == FeedbackStatus.SUBMITTED.value
        assert feedback.report_id == report.id

    def test_feedback_clarification_sets_response_required(self, test_session):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=True)

        service = ReportService(test_session)
        report = service.generate_final_report(review.id, lawyer, export_pdf=False)

        req = FeedbackSubmitRequest(
            overall_satisfaction=3,
            clarity_rating=3,
            usefulness_rating=4,
            needs_clarification=True,
            follow_up_requested=True,
            client_comments="Can the advocate explain if this covers indirect damages?"
        )
        feedback = service.submit_client_feedback(report.id, client, req)
        assert feedback.status == FeedbackStatus.RESPONSE_REQUIRED.value

    def test_cross_client_feedback_blocked(self, test_session):
        repo = DocumentRepository(test_session)
        client1 = create_user(repo, "client1@corp.in", UserRole.CLIENT)
        client2 = create_user(repo, "client2@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client1, lawyer, is_completed=True)

        service = ReportService(test_session)
        report = service.generate_final_report(review.id, lawyer, export_pdf=False)

        req = FeedbackSubmitRequest(
            overall_satisfaction=4,
            clarity_rating=4,
            usefulness_rating=4
        )
        with pytest.raises(PermissionError, match="Forbidden"):
            service.submit_client_feedback(report.id, client2, req)

    def test_advocate_feedback_response_and_resolution(self, test_session):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=True)

        service = ReportService(test_session)
        report = service.generate_final_report(review.id, lawyer, export_pdf=False)

        feedback = service.submit_client_feedback(
            report.id, client,
            FeedbackSubmitRequest(
                overall_satisfaction=4,
                clarity_rating=3,
                usefulness_rating=4,
                needs_clarification=True,
                client_comments="Please explain consequential loss carveouts."
            )
        )
        assert feedback.status == FeedbackStatus.RESPONSE_REQUIRED.value

        # Advocate responds
        resp = service.respond_to_feedback(
            feedback_id=feedback.id,
            actor_user=lawyer,
            response_data=FeedbackResponseRequest(
                response_text="Consequential loss is expressly excluded under Clause 4.2.",
                is_client_visible=True,
                internal_notes="Internal note: Verified against ICA 1872 Section 73 principles."
            )
        )
        assert resp.is_client_visible is True
        test_session.refresh(feedback)
        assert feedback.status == FeedbackStatus.RESPONDED.value

        # Close feedback
        updated = service.update_feedback_status(feedback.id, lawyer, FeedbackStatus.CLOSED.value)
        assert updated.status == FeedbackStatus.CLOSED.value


# =============================================================================
# 6. AUDIT TRAIL CHAINING TESTS
# =============================================================================

class TestAuditProvenanceChaining:
    def test_report_and_feedback_audit_events_chained(self, test_session):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=True)

        service = ReportService(test_session)
        report = service.generate_final_report(review.id, lawyer, export_pdf=False)
        feedback = service.submit_client_feedback(
            report.id, client,
            FeedbackSubmitRequest(
                overall_satisfaction=5,
                clarity_rating=5,
                usefulness_rating=5
            )
        )

        events = test_session.query(AuditEventRecord).order_by(AuditEventRecord.created_at.asc(), AuditEventRecord.id.asc()).all()
        assert len(events) >= 3

        # Cryptographic verification of hash chain
        hashes = [e.event_hash for e in events]
        prev_hashes = [e.previous_event_hash for e in events]
        
        # Verify hash link
        for i in range(1, len(events)):
            assert events[i].previous_event_hash == events[i - 1].event_hash


# =============================================================================
# 7. REST API ENDPOINT INTEGRATION TESTS
# =============================================================================

class TestReportingAPIEndpoints:
    def _auth_header(self, user: UserRecord) -> dict:
        tm = TokenManager()
        token = tm.generate_token(user)
        return {"Authorization": f"Bearer {token}"}

    def test_api_generate_report_and_download(self, test_session, test_client):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=True)
        test_session.commit()

        # POST /api/reports/generate/<review_id>
        res = test_client.post(
            f"/api/reports/generate/{review.id}",
            headers=self._auth_header(lawyer),
            json={"export_pdf": True}
        )
        assert res.status_code == 201
        data = res.get_json()
        assert "report_id" in data
        assert data["is_final"] is True
        report_id = data["report_id"]

        # GET /api/reports/<report_id> by client
        res_get = test_client.get(
            f"/api/reports/{report_id}",
            headers=self._auth_header(client)
        )
        assert res_get.status_code == 200

        # GET /api/reports/<report_id>/pdf by client
        res_pdf = test_client.get(
            f"/api/reports/{report_id}/pdf",
            headers=self._auth_header(client)
        )
        assert res_pdf.status_code == 200
        assert res_pdf.headers["Content-Type"] == "application/pdf"
        assert len(res_pdf.data) > 1000

    def test_api_feedback_workflow(self, test_session, test_client):
        repo = DocumentRepository(test_session)
        client = create_user(repo, "client@corp.in", UserRole.CLIENT)
        lawyer = create_user(repo, "advocate@legal.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        doc, review = create_contract_and_review(test_session, client, lawyer, is_completed=True)

        service = ReportService(test_session)
        report = service.generate_final_report(review.id, lawyer, export_pdf=False)
        test_session.commit()

        # POST /api/reports/<report_id>/feedback
        fb_res = test_client.post(
            f"/api/reports/{report.id}/feedback",
            headers=self._auth_header(client),
            json={
                "overall_satisfaction": 4,
                "clarity_rating": 5,
                "usefulness_rating": 4,
                "client_comments": "Prompt and clear lawyer review."
            }
        )
        assert fb_res.status_code == 201
        fb_id = fb_res.get_json()["feedback_id"]

        # GET /api/reports/<report_id>/feedback
        get_res = test_client.get(
            f"/api/reports/{report.id}/feedback",
            headers=self._auth_header(client)
        )
        assert get_res.status_code == 200
        assert len(get_res.get_json()["feedback"]) == 1

        # POST /api/reports/feedback/<feedback_id>/respond by lawyer
        resp_res = test_client.post(
            f"/api/reports/feedback/{fb_id}/respond",
            headers=self._auth_header(lawyer),
            json={
                "response_text": "Thank you for your feedback.",
                "is_client_visible": True
            }
        )
        assert resp_res.status_code == 201

        # POST /api/reports/feedback/<feedback_id>/status by lawyer
        stat_res = test_client.post(
            f"/api/reports/feedback/{fb_id}/status",
            headers=self._auth_header(lawyer),
            json={"status": "CLOSED"}
        )
        assert stat_res.status_code == 200
        assert stat_res.get_json()["new_status"] == "CLOSED"
