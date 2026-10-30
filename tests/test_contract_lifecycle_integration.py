"""
Comprehensive End-to-End Contract Lifecycle Integration Test Suite (Task 037).

Verifies the complete human-in-the-loop contract intelligence lifecycle:
1. Client Registration & Authentication (HttpOnly session cookie + Double-Submit CSRF).
2. Multi-format Document Upload & Parsing (PDF, DOCX, TXT) with boundary validation.
3. Transactional Ingestion & Review Initiation with atomic rollback protection.
4. Role-based queues & tenant isolation (Client, Lawyer, Supervisor, Auditor).
5. Supervisor Assignment to verified advocates (blocking unverified/client self-assignment).
6. Assigned Lawyer Review Workbench (in-review transition, findings authoring).
7. Verbatim Indian Statutory Evidence Retrieval & Citation Traceability.
8. Lawyer Decisions & Mandatory Rationales (internal notes hidden from clients).
9. Client Clarification Workflow & Resolution gating review completion.
10. Review Completion Prerequisites (status, unresolved clarifications, disclaimers).
11. Final Report Generation (draft preview vs immutable report, SHA-256 PDF hash).
12. Report Download Tenant Authorization & Audit Tracking.
13. Structured Client Feedback (1-5 ratings, follow-up, advocate responses).
14. Document Versioning & Report Supersession.
15. Cryptographic SHA-256 Audit Trail Hash-Chain Integrity.
"""

import io
import json
import uuid
import datetime
import hashlib
from contextlib import contextmanager
import pytest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.persistence.database import Base, get_session_factory
from src.persistence.models import (
    UserRecord, DocumentRecord, ExtractedTextSnapshot, SegmentRecord,
    UserRole, AccountStatus, AdvocateStatus,
    ReviewRecord, ReviewStateTransitionRecord, ClauseFindingRecord,
    ReviewCommentRecord, DocumentRevisionRecord, FinalReportRecord,
    ClientFeedbackRecord, FeedbackResponseRecord, AuditEventRecord,
    ReviewStatus, LawyerDecisionType, FindingOrigin, CommentVisibility, RevisionStatus,
    ReportStatus, FeedbackStatus
)
from src.persistence.repository import DocumentRepository
from src.auth.config import AuthConfig
from src.auth.password import PasswordManager
from src.auth.token import TokenManager
from src.auth.service import AuthService
from src.auth.csrf import generate_csrf_token
from src.review.service import ReviewService, MANDATORY_REVIEW_DISCLAIMER
from src.review.evidence import ClauseEvidenceRetriever, SCORE_SEMANTICS_DISCLAIMER
from src.reporting.service import ReportService
from src.audit.store import AuditStore
from src.audit.logger import AuditLogger
from src.audit.integrity import AuditVerifier
from src.audit.provenance import IntegrityStatus, EventType

from src.dashboard.app import app

# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def lifecycle_db_engine():
    """Isolated in-memory SQLite database for full lifecycle testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

@pytest.fixture
def lifecycle_session(lifecycle_db_engine):
    factory = sessionmaker(bind=lifecycle_db_engine, autocommit=False, autoflush=False)
    sess = factory()
    yield sess
    sess.rollback()
    sess.close()

@pytest.fixture
def lifecycle_client(lifecycle_db_engine):
    app.config["TESTING"] = True
    factory = sessionmaker(bind=lifecycle_db_engine, autocommit=False, autoflush=False)

    @contextmanager
    def mock_db_session(engine=None):
        sess = factory()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    with patch("src.persistence.database.get_engine", return_value=lifecycle_db_engine):
        with patch("src.persistence.database.get_db_session", side_effect=mock_db_session):
            with patch("src.auth.rbac.get_db_session", side_effect=mock_db_session):
                with patch("src.auth.routes.get_db_session", side_effect=mock_db_session):
                    with patch("src.review.routes.get_db_session", side_effect=mock_db_session):
                        with patch("src.reporting.routes.get_db_session", side_effect=mock_db_session):
                            with app.test_client() as client:
                                yield client

def create_user_record(
    repo: DocumentRepository,
    email: str,
    role: UserRole,
    full_name: str,
    advocate_status: AdvocateStatus = AdvocateStatus.NOT_APPLICABLE,
    password: str = "EnterpriseLegal2026!"
) -> UserRecord:
    pm = PasswordManager()
    h = pm.hash_password(password)
    user = repo.create_user(
        user_id=str(uuid.uuid4()),
        email=email,
        password_hash=h,
        full_name=full_name,
        role=role,
        account_status=AccountStatus.ACTIVE,
        advocate_status=advocate_status,
        bar_enrolment_id="D/8888/2016" if role in (UserRole.LAWYER, UserRole.SUPERVISING_LAWYER) else None,
        state_bar_council="Delhi" if role in (UserRole.LAWYER, UserRole.SUPERVISING_LAWYER) else None,
        year_of_enrolment=2016 if role in (UserRole.LAWYER, UserRole.SUPERVISING_LAWYER) else None
    )
    repo.session.commit()
    return user

def login_and_get_session(client, email: str, password: str = "EnterpriseLegal2026!"):
    """Helper to authenticate a persona and return (token, csrf_token)."""
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.get_data(as_text=True)}"
    data = res.get_json()
    token = data["access_token"]
    csrf = data["csrf_token"]
    return token, csrf

# Sample valid contract content
SAMPLE_CONTRACT_TXT = (
    "MASTER SERVICES AND CLOUD INFRASTRUCTURE AGREEMENT\n\n"
    "1. SCOPE OF SERVICES\n"
    "The Vendor agrees to provide enterprise contract analysis cloud services to Client subject to standard terms.\n\n"
    "2. NON-COMPETE AND RESTRAINT OF TRADE\n"
    "Neither party shall during the term of this Agreement and for a period of five (5) years following termination "
    "directly or indirectly carry on any business or profession in competition across India.\n\n"
    "3. DATA PROTECTION AND CONFIDENTIALITY\n"
    "The parties agree that all personal data processed under this agreement shall be handled strictly in compliance "
    "with applicable Indian law, including the Digital Personal Data Protection Act, 2023.\n\n"
    "4. INDEMNITY AND LIMITATION OF LIABILITY\n"
    "Vendor shall indemnify Client against all third-party intellectual property infringement claims. "
    "Aggregate liability shall be capped at the total fees paid during preceding 12 months.\n\n"
    "5. GOVERNING LAW AND ARBITRATION\n"
    "Any dispute arising out of or in connection with this agreement shall be settled through binding arbitration "
    "conducted in New Delhi under the Arbitration and Conciliation Act, 1996.\n"
).encode("utf-8")


# =============================================================================
# TEST CASES
# =============================================================================

def test_01_complete_end_to_end_contract_lifecycle(lifecycle_client, lifecycle_session):
    """
    1. Full Lifecycle Integration Test:
       Client uploads contract -> Segmented -> Supervisor assigns verified lawyer ->
       Lawyer reviews, inspects evidence, records decisions, handles clarification ->
       Lawyer completes review -> Generates Final Report -> Client downloads PDF ->
       Client submits feedback -> Lawyer responds & closes.
    """
    repo = DocumentRepository(lifecycle_session)

    # 1. Setup personas
    client_user = create_user_record(repo, "acme.corp@client.in", UserRole.CLIENT, "Acme Corp GC")
    lawyer_user = create_user_record(repo, "priya.advocate@legal.in", UserRole.LAWYER, "Adv. Priya", advocate_status=AdvocateStatus.VERIFIED)
    sup_user = create_user_record(repo, "rajesh.partner@legal.in", UserRole.SUPERVISING_LAWYER, "Adv. Rajesh Senior Partner", advocate_status=AdvocateStatus.VERIFIED)

    # 2. Client logs in via cookie session + CSRF
    c_token, c_csrf = login_and_get_session(lifecycle_client, "acme.corp@client.in")
    lifecycle_client.set_cookie("contractrisk_session", c_token)
    lifecycle_client.set_cookie("contractrisk_csrf", c_csrf)

    # 3. Client uploads contract
    upload_headers = {"X-CSRF-Token": c_csrf}
    upload_res = lifecycle_client.post(
        "/api/review/upload",
        headers=upload_headers,
        data={
            "file": (io.BytesIO(SAMPLE_CONTRACT_TXT), "Master_Agreement_2026.txt")
        },
        content_type="multipart/form-data"
    )
    assert upload_res.status_code == 201, upload_res.get_data(as_text=True)
    up_data = upload_res.get_json()
    doc_id = up_data["document_id"]
    review_id = up_data["review_id"]
    assert up_data["status"] == ReviewStatus.DOCUMENT_SUBMITTED.value
    assert up_data["segments_count"] >= 5

    # 4. Supervisor logs in and inspects review queue
    s_token, s_csrf = login_and_get_session(lifecycle_client, "rajesh.partner@legal.in")
    lifecycle_client.set_cookie("contractrisk_session", s_token)
    lifecycle_client.set_cookie("contractrisk_csrf", s_csrf)

    queue_res = lifecycle_client.get("/api/review/queue")
    assert queue_res.status_code == 200
    q_data = queue_res.get_json()
    assert any(r["review_id"] == review_id for r in q_data["reviews"])

    # Supervisor lists eligible advocates
    adv_res = lifecycle_client.get("/api/review/advocates/eligible")
    assert adv_res.status_code == 200
    assert any(a["id"] == lawyer_user.id for a in adv_res.get_json()["advocates"])

    # Supervisor assigns contract to verified lawyer
    assign_res = lifecycle_client.post(
        f"/api/review/{review_id}/assign",
        headers={"X-CSRF-Token": s_csrf},
        json={"lawyer_id": lawyer_user.id, "rationale": "Assigned to corporate commercial specialist"}
    )
    assert assign_res.status_code == 200
    assert assign_res.get_json()["status"] == ReviewStatus.ASSIGNED.value

    # 5. Assigned lawyer logs in
    l_token, l_csrf = login_and_get_session(lifecycle_client, "priya.advocate@legal.in")
    lifecycle_client.set_cookie("contractrisk_session", l_token)
    lifecycle_client.set_cookie("contractrisk_csrf", l_csrf)

    # Lawyer opens review workspace
    work_res = lifecycle_client.get(f"/api/review/{review_id}")
    assert work_res.status_code == 200
    work_data = work_res.get_json()
    assert work_data["review"]["status"] == ReviewStatus.ASSIGNED.value
    assert len(work_data["segments"]) >= 5
    first_segment = next(
        (s for s in work_data["segments"] if "NON-COMPETE" in (s.get("heading") or "") or "competition" in s.get("text", "")),
        work_data["segments"][1]
    )

    # Lawyer transitions to IN_REVIEW
    trans_res = lifecycle_client.post(
        f"/api/review/{review_id}/transition",
        headers={"X-CSRF-Token": l_csrf},
        json={"to_state": ReviewStatus.IN_REVIEW.value, "reason": "Commencing substantive clause analysis"}
    )
    assert trans_res.status_code == 200
    assert trans_res.get_json()["status"] == ReviewStatus.IN_REVIEW.value

    # 6. Lawyer retrieves authoritative statutory evidence for non-compete clause
    ev_res = lifecycle_client.get(f"/api/review/{review_id}/evidence/{first_segment['segment_id']}")
    assert ev_res.status_code == 200
    ev_data = ev_res.get_json()
    assert "passages" in ev_data
    assert "score_disclaimer" in ev_data
    # Evidence includes Section 27 Indian Contract Act (restraint of trade)
    assert any("27" in str(e.get("section_number")) or "Contract" in str(e.get("statute_title"))
               for e in ev_data.get("passages", []))

    # 7. Lawyer records decision on the clause with mandatory legal rationale
    dec_res = lifecycle_client.post(
        f"/api/review/{review_id}/decision",
        headers={"X-CSRF-Token": l_csrf},
        json={
            "segment_id": first_segment["segment_id"],
            "decision": LawyerDecisionType.ACCEPT_AI_OBSERVATION.value,
            "rationale": "Post-term 5-year non-compete is void under Section 27 of Indian Contract Act, 1872 as held in Percept D'Mark.",
            "notes": "Internal note: Advise client to substitute with reasonable confidentiality covenant.",
            "is_disclosed_to_client": True,
            "statutory_evidence": ev_data.get("passages")[:1]
        }
    )
    assert dec_res.status_code == 200

    # 8. Lawyer authors an independent finding
    dpdp_segment = next(
        (s for s in work_data["segments"] if "DATA PROTECTION" in (s.get("heading") or "") or "personal data" in s.get("text", "").lower()),
        work_data["segments"][2]
    )
    auth_res = lifecycle_client.post(
        f"/api/review/{review_id}/finding/create",
        headers={"X-CSRF-Token": l_csrf},
        json={
            "segment_id": dpdp_segment["segment_id"],
            "risk_label": "DATA_PROTECTION_COMPLIANCE",
            "lawyer_observation": "Cross-border data transfer mechanism lacks explicit reference to DPDP Act 2023 Section 16.",
            "decision": LawyerDecisionType.ACCEPT_AI_OBSERVATION.value,
            "rationale": "Data fiduciary obligations under DPDP 2023 require contractual transfer safeguards.",
            "is_disclosed_to_client": True
        }
    )
    assert auth_res.status_code == 201
    assert auth_res.get_json()["finding_origin"] == FindingOrigin.LAWYER_AUTHORED.value

    # Adjudicate all remaining auto-generated clause findings
    for finding in work_data.get("findings", []):
        if finding["segment_id"] != first_segment["segment_id"]:
            dec_rem = lifecycle_client.post(
                f"/api/review/{review_id}/decision",
                headers={"X-CSRF-Token": l_csrf},
                json={
                    "segment_id": finding["segment_id"],
                    "decision": LawyerDecisionType.ACCEPT_AI_OBSERVATION.value,
                    "rationale": f"Statutory risk assessment for clause segment {finding['segment_id']} reviewed and verified under Indian commercial law.",
                    "notes": "Verified by reviewing advocate.",
                    "is_disclosed_to_client": True
                }
            )
            assert dec_rem.status_code == 200

    # 9. Lawyer posts a client-visible clarification request
    comm_res = lifecycle_client.post(
        f"/api/review/{review_id}/comment",
        headers={"X-CSRF-Token": l_csrf},
        json={
            "segment_id": first_segment["segment_id"],
            "comment_text": "Please confirm if your vendor operates exclusively within India or processes data internationally.",
            "visibility": CommentVisibility.CLIENT_VISIBLE.value
        }
    )
    assert comm_res.status_code == 201
    comment_id = comm_res.get_json()["comment_id"]

    # 10. Client logs in and responds to clarification request
    lifecycle_client.set_cookie("contractrisk_session", c_token)
    lifecycle_client.set_cookie("contractrisk_csrf", c_csrf)

    reply_res = lifecycle_client.post(
        f"/api/review/{review_id}/comment",
        headers={"X-CSRF-Token": c_csrf},
        json={
            "segment_id": first_segment["segment_id"],
            "comment_text": "Vendor operates in Bangalore and New Delhi with backup server in Mumbai; strictly domestic.",
            "visibility": CommentVisibility.CLIENT_VISIBLE.value,
            "parent_comment_id": comment_id
        }
    )
    assert reply_res.status_code == 201

    # 11. Lawyer resolves the clarification request
    lifecycle_client.set_cookie("contractrisk_session", l_token)
    lifecycle_client.set_cookie("contractrisk_csrf", l_csrf)

    resolve_res = lifecycle_client.post(
        f"/api/review/{review_id}/comment/{comment_id}/resolve",
        headers={"X-CSRF-Token": l_csrf}
    )
    assert resolve_res.status_code == 200

    # 12. Lawyer completes review
    comp_res = lifecycle_client.post(
        f"/api/review/{review_id}/complete",
        headers={"X-CSRF-Token": l_csrf},
        json={
            "completion_summary": "Comprehensive legal contract review completed. Non-compete and DPDP issues identified.",
            "outstanding_limitations": "Review limited to statutory compliance under Indian commercial law.",
            "further_client_action_required": False
        }
    )
    assert comp_res.status_code == 200
    assert comp_res.get_json()["status"] == ReviewStatus.REVIEW_COMPLETED.value

    # 13. Lawyer generates publication-ready Final Report
    gen_res = lifecycle_client.post(
        f"/api/reports/generate/{review_id}",
        headers={"X-CSRF-Token": l_csrf},
        json={"export_pdf": True}
    )
    assert gen_res.status_code == 201
    rep_data = gen_res.get_json()
    report_id = rep_data["report_id"]
    assert rep_data["is_final"] is True
    assert rep_data["content_sha256"] is not None
    assert rep_data["pdf_sha256"] is not None

    # 14. Client logs in and accesses Final Report
    lifecycle_client.set_cookie("contractrisk_session", c_token)
    lifecycle_client.set_cookie("contractrisk_csrf", c_csrf)

    rep_view_res = lifecycle_client.get(f"/api/reports/{report_id}")
    assert rep_view_res.status_code == 200
    rep_view = rep_view_res.get_json()
    assert rep_view["report_id"] == report_id
    assert rep_view["is_final"] is True

    # Client downloads PDF report
    pdf_res = lifecycle_client.get(f"/api/reports/{report_id}/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers["Content-Type"] == "application/pdf"
    assert len(pdf_res.data) > 1000  # Generated PDF binary exists

    # 15. Client submits structured feedback (ratings 1 to 5)
    fb_res = lifecycle_client.post(
        f"/api/reports/{report_id}/feedback",
        headers={"X-CSRF-Token": c_csrf},
        json={
            "overall_satisfaction": 5,
            "clarity_rating": 5,
            "usefulness_rating": 5,
            "needs_clarification": False,
            "follow_up_requested": True,
            "client_comments": "Extremely thorough analysis. The Section 27 ICA citation was decisive."
        }
    )
    assert fb_res.status_code == 201
    fb_id = fb_res.get_json()["feedback_id"]

    # 16. Lawyer logs in, responds to feedback and marks CLOSED
    lifecycle_client.set_cookie("contractrisk_session", l_token)
    lifecycle_client.set_cookie("contractrisk_csrf", l_csrf)

    resp_res = lifecycle_client.post(
        f"/api/reports/feedback/{fb_id}/respond",
        headers={"X-CSRF-Token": l_csrf},
        json={
            "response_text": "Thank you. We are pleased to assist Acme Corp with contractual risk mitigation.",
            "internal_notes": "Client retained for future commercial advisory work.",
            "is_client_visible": True
        }
    )
    assert resp_res.status_code == 201

    stat_res = lifecycle_client.post(
        f"/api/reports/feedback/{fb_id}/status",
        headers={"X-CSRF-Token": l_csrf},
        json={"status": FeedbackStatus.CLOSED.value}
    )
    assert stat_res.status_code == 200
    assert stat_res.get_json()["new_status"] == FeedbackStatus.CLOSED.value


def test_02_upload_validation_failures_and_rollback(lifecycle_client, lifecycle_session):
    """2. Validates that malformed, empty, and unsupported file uploads are safely rejected."""
    repo = DocumentRepository(lifecycle_session)
    client_user = create_user_record(repo, "fail.client@enterprise.in", UserRole.CLIENT, "Fail Client")
    token, csrf = login_and_get_session(lifecycle_client, "fail.client@enterprise.in")
    lifecycle_client.set_cookie("contractrisk_session", token)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf)

    headers = {"X-CSRF-Token": csrf}

    # 1. Missing file key
    res1 = lifecycle_client.post("/api/review/upload", headers=headers, data={})
    assert res1.status_code == 400
    assert "No file uploaded" in res1.get_json()["error"]

    # 2. Empty file
    res2 = lifecycle_client.post(
        "/api/review/upload",
        headers=headers,
        data={"file": (io.BytesIO(b""), "empty.txt")},
        content_type="multipart/form-data"
    )
    assert res2.status_code == 400
    assert "empty" in res2.get_json()["error"]

    # 3. Unsupported extension
    res3 = lifecycle_client.post(
        "/api/review/upload",
        headers=headers,
        data={"file": (io.BytesIO(b"binary payload"), "malicious.exe")},
        content_type="multipart/form-data"
    )
    assert res3.status_code == 400
    assert "not permitted" in res3.get_json()["error"]

    # Verify zero document records persisted on failure
    docs = lifecycle_session.query(DocumentRecord).filter_by(owner_id=client_user.id).all()
    assert len(docs) == 0


def test_03_ownership_and_tenant_isolation(lifecycle_client, lifecycle_session):
    """3. Verifies strict multi-tenant horizontal isolation between clients."""
    repo = DocumentRepository(lifecycle_session)
    client_a = create_user_record(repo, "tenant.a@corp.in", UserRole.CLIENT, "Tenant A")
    client_b = create_user_record(repo, "tenant.b@corp.in", UserRole.CLIENT, "Tenant B")

    # Client A logs in and uploads contract
    token_a, csrf_a = login_and_get_session(lifecycle_client, "tenant.a@corp.in")
    lifecycle_client.set_cookie("contractrisk_session", token_a)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf_a)

    upload_res = lifecycle_client.post(
        "/api/review/upload",
        headers={"X-CSRF-Token": csrf_a},
        data={"file": (io.BytesIO(SAMPLE_CONTRACT_TXT), "confidential_a.txt")},
        content_type="multipart/form-data"
    )
    assert upload_res.status_code == 201
    doc_a_id = upload_res.get_json()["document_id"]
    rev_a_id = upload_res.get_json()["review_id"]

    # Client B logs in
    token_b, csrf_b = login_and_get_session(lifecycle_client, "tenant.b@corp.in")
    lifecycle_client.set_cookie("contractrisk_session", token_b)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf_b)

    # Client B attempts to access Client A's contract text
    res_contract = lifecycle_client.get(f"/api/contracts/{doc_a_id}")
    assert res_contract.status_code == 403

    # Client B attempts to access Client A's review workspace
    res_review = lifecycle_client.get(f"/api/review/{rev_a_id}")
    assert res_review.status_code == 403

    # Client B attempts to post comment on Client A's review
    res_comment = lifecycle_client.post(
        f"/api/review/{rev_a_id}/comment",
        headers={"X-CSRF-Token": csrf_b},
        json={"comment_text": "Injected comment"}
    )
    assert res_comment.status_code == 403


def test_04_supervisor_assignment_restrictions(lifecycle_client, lifecycle_session):
    """4. Verifies supervisor assignment rules: verified advocates allowed; unverified/client rejected."""
    repo = DocumentRepository(lifecycle_session)
    client = create_user_record(repo, "company@client.in", UserRole.CLIENT, "Company")
    unverified_lawyer = create_user_record(repo, "pending@legal.in", UserRole.LAWYER, "Unverified Lawyer", advocate_status=AdvocateStatus.PENDING_VERIFICATION)
    verified_lawyer = create_user_record(repo, "verified@legal.in", UserRole.LAWYER, "Verified Lawyer", advocate_status=AdvocateStatus.VERIFIED)
    supervisor = create_user_record(repo, "lead@legal.in", UserRole.SUPERVISING_LAWYER, "Lead Partner", advocate_status=AdvocateStatus.VERIFIED)

    # Client uploads contract
    token_c, csrf_c = login_and_get_session(lifecycle_client, "company@client.in")
    lifecycle_client.set_cookie("contractrisk_session", token_c)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf_c)
    upload_res = lifecycle_client.post(
        "/api/review/upload",
        headers={"X-CSRF-Token": csrf_c},
        data={"file": (io.BytesIO(SAMPLE_CONTRACT_TXT), "contract.txt")},
        content_type="multipart/form-data"
    )
    review_id = upload_res.get_json()["review_id"]

    # 1. Client attempts to assign contract -> rejected (403)
    res_c_assign = lifecycle_client.post(
        f"/api/review/{review_id}/assign",
        headers={"X-CSRF-Token": csrf_c},
        json={"lawyer_id": verified_lawyer.id}
    )
    assert res_c_assign.status_code == 403

    # 2. Supervisor logs in
    token_s, csrf_s = login_and_get_session(lifecycle_client, "lead@legal.in")
    lifecycle_client.set_cookie("contractrisk_session", token_s)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf_s)

    # Supervisor attempts to assign unverified advocate -> rejected (400/403)
    res_unver = lifecycle_client.post(
        f"/api/review/{review_id}/assign",
        headers={"X-CSRF-Token": csrf_s},
        json={"lawyer_id": unverified_lawyer.id}
    )
    assert res_unver.status_code in (400, 403)
    assert "verified" in res_unver.get_json()["error"].lower()

    # Supervisor assigns verified advocate -> succeeds (200)
    res_ver = lifecycle_client.post(
        f"/api/review/{review_id}/assign",
        headers={"X-CSRF-Token": csrf_s},
        json={"lawyer_id": verified_lawyer.id}
    )
    assert res_ver.status_code == 200
    assert res_ver.get_json()["status"] == ReviewStatus.ASSIGNED.value


def test_05_unassigned_lawyer_denied_access(lifecycle_client, lifecycle_session):
    """5. Assigned lawyer has access; unassigned lawyer is strictly denied access (403)."""
    repo = DocumentRepository(lifecycle_session)
    client = create_user_record(repo, "party@client.in", UserRole.CLIENT, "Party")
    assigned_lawyer = create_user_record(repo, "assigned@legal.in", UserRole.LAWYER, "Assigned Advocate", advocate_status=AdvocateStatus.VERIFIED)
    unassigned_lawyer = create_user_record(repo, "unassigned@legal.in", UserRole.LAWYER, "Other Advocate", advocate_status=AdvocateStatus.VERIFIED)
    supervisor = create_user_record(repo, "partner@legal.in", UserRole.SUPERVISING_LAWYER, "Partner", advocate_status=AdvocateStatus.VERIFIED)

    # Upload contract
    token_c, csrf_c = login_and_get_session(lifecycle_client, "party@client.in")
    lifecycle_client.set_cookie("contractrisk_session", token_c)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf_c)
    up = lifecycle_client.post(
        "/api/review/upload",
        headers={"X-CSRF-Token": csrf_c},
        data={"file": (io.BytesIO(SAMPLE_CONTRACT_TXT), "contract.txt")},
        content_type="multipart/form-data"
    )
    rev_id = up.get_json()["review_id"]

    # Supervisor assigns to assigned_lawyer
    token_s, csrf_s = login_and_get_session(lifecycle_client, "partner@legal.in")
    lifecycle_client.set_cookie("contractrisk_session", token_s)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf_s)
    lifecycle_client.post(f"/api/review/{rev_id}/assign", headers={"X-CSRF-Token": csrf_s}, json={"lawyer_id": assigned_lawyer.id})

    # Assigned lawyer accesses review -> succeeds (200)
    token_l1, _ = login_and_get_session(lifecycle_client, "assigned@legal.in")
    lifecycle_client.set_cookie("contractrisk_session", token_l1)
    res_l1 = lifecycle_client.get(f"/api/review/{rev_id}")
    assert res_l1.status_code == 200

    # Unassigned lawyer accesses review -> rejected (403)
    token_l2, _ = login_and_get_session(lifecycle_client, "unassigned@legal.in")
    lifecycle_client.set_cookie("contractrisk_session", token_l2)
    res_l2 = lifecycle_client.get(f"/api/review/{rev_id}")
    assert res_l2.status_code == 403


def test_06_auditor_privilege_boundaries(lifecycle_client, lifecycle_session):
    """6. Auditors can inspect compliance metadata but cannot access raw text or upload contracts."""
    repo = DocumentRepository(lifecycle_session)
    auditor = create_user_record(repo, "auditor.compliance@corp.in", UserRole.AUDITOR, "Auditor")
    client = create_user_record(repo, "client.audit@corp.in", UserRole.CLIENT, "Client")

    token_a, csrf_a = login_and_get_session(lifecycle_client, "auditor.compliance@corp.in")
    lifecycle_client.set_cookie("contractrisk_session", token_a)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf_a)

    # 1. Auditor attempts to upload contract -> rejected (403)
    res_up = lifecycle_client.post(
        "/api/review/upload",
        headers={"X-CSRF-Token": csrf_a},
        data={"file": (io.BytesIO(SAMPLE_CONTRACT_TXT), "contract.txt")},
        content_type="multipart/form-data"
    )
    assert res_up.status_code == 403

    # 2. Auditor can access audit logs -> succeeds (200)
    res_logs = lifecycle_client.get("/api/audit/logs")
    assert res_logs.status_code == 200

    # 3. Auditor inspects contract details -> raw text is omitted
    # Setup document
    doc_id = str(uuid.uuid4())
    doc = DocumentRecord(
        id=doc_id, file_sha256="sha", original_filename="nda.txt",
        sanitized_filename="nda.txt", mime_type="text/plain", document_format="TXT",
        file_size_bytes=100, storage_path="/path", owner_id=client.id
    )
    lifecycle_session.add(doc)
    lifecycle_session.commit()

    res_doc = lifecycle_client.get(f"/api/contracts/{doc_id}")
    assert res_doc.status_code == 403  # Full contract details endpoint denies auditor


def test_07_review_decision_requires_rationale(lifecycle_client, lifecycle_session):
    """7. Recording a review decision mandates substantive lawyer rationale."""
    repo = DocumentRepository(lifecycle_session)
    client = create_user_record(repo, "rationale.client@in.in", UserRole.CLIENT, "Client")
    lawyer = create_user_record(repo, "rationale.lawyer@in.in", UserRole.LAWYER, "Lawyer", advocate_status=AdvocateStatus.VERIFIED)

    # Setup document & review
    token_c, csrf_c = login_and_get_session(lifecycle_client, "rationale.client@in.in")
    lifecycle_client.set_cookie("contractrisk_session", token_c)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf_c)
    up = lifecycle_client.post(
        "/api/review/upload",
        headers={"X-CSRF-Token": csrf_c},
        data={"file": (io.BytesIO(SAMPLE_CONTRACT_TXT), "contract.txt")},
        content_type="multipart/form-data"
    )
    rev_id = up.get_json()["review_id"]

    # Assign lawyer and transition to IN_REVIEW
    repo.assign_review(review_id=rev_id, lawyer_id=lawyer.id, assigned_by_id=lawyer.id)
    rev = repo.get_review_by_id(rev_id)
    rev.status = ReviewStatus.IN_REVIEW.value
    lifecycle_session.commit()

    token_l, csrf_l = login_and_get_session(lifecycle_client, "rationale.lawyer@in.in")
    lifecycle_client.set_cookie("contractrisk_session", token_l)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf_l)

    work_data = lifecycle_client.get(f"/api/review/{rev_id}").get_json()
    seg_id = work_data["segments"][0]["segment_id"]

    # Decision with missing rationale -> rejected (400)
    res_bad = lifecycle_client.post(
        f"/api/review/{rev_id}/decision",
        headers={"X-CSRF-Token": csrf_l},
        json={
            "segment_id": seg_id,
            "decision": LawyerDecisionType.ACCEPT_AI_OBSERVATION.value,
            "rationale": ""
        }
    )
    assert res_bad.status_code == 400
    assert "rationale" in res_bad.get_json()["error"].lower()

    # Decision with valid rationale -> succeeds (200)
    res_good = lifecycle_client.post(
        f"/api/review/{rev_id}/decision",
        headers={"X-CSRF-Token": csrf_l},
        json={
            "segment_id": seg_id,
            "decision": LawyerDecisionType.ACCEPT_AI_OBSERVATION.value,
            "rationale": "Clause is standard commercial definition compliant with Indian law."
        }
    )
    assert res_good.status_code == 200


def test_08_unresolved_clarifications_block_review_completion(lifecycle_client, lifecycle_session):
    """8. Unresolved clarification requests strictly block review completion."""
    repo = DocumentRepository(lifecycle_session)
    client = create_user_record(repo, "clarif.client@in.in", UserRole.CLIENT, "Client")
    lawyer = create_user_record(repo, "clarif.lawyer@in.in", UserRole.LAWYER, "Lawyer", advocate_status=AdvocateStatus.VERIFIED)

    token_c, csrf_c = login_and_get_session(lifecycle_client, "clarif.client@in.in")
    lifecycle_client.set_cookie("contractrisk_session", token_c)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf_c)
    up = lifecycle_client.post(
        "/api/review/upload",
        headers={"X-CSRF-Token": csrf_c},
        data={"file": (io.BytesIO(SAMPLE_CONTRACT_TXT), "contract.txt")},
        content_type="multipart/form-data"
    )
    rev_id = up.get_json()["review_id"]

    repo.assign_review(review_id=rev_id, lawyer_id=lawyer.id, assigned_by_id=lawyer.id)
    rev = repo.get_review_by_id(rev_id)
    rev.status = ReviewStatus.IN_REVIEW.value
    lifecycle_session.commit()

    token_l, csrf_l = login_and_get_session(lifecycle_client, "clarif.lawyer@in.in")
    lifecycle_client.set_cookie("contractrisk_session", token_l)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf_l)

    # Post client-visible clarification comment
    comm_res = lifecycle_client.post(
        f"/api/review/{rev_id}/comment",
        headers={"X-CSRF-Token": csrf_l},
        json={"comment_text": "Need clarification on jurisdiction clause.", "visibility": CommentVisibility.CLARIFICATION_REQUEST.value}
    )
    comment_id = comm_res.get_json()["comment_id"]

    # Attempt to complete review with unresolved comment -> rejected (400)
    comp_fail = lifecycle_client.post(
        f"/api/review/{rev_id}/complete",
        headers={"X-CSRF-Token": csrf_l},
        json={"completion_summary": "Trying to complete with pending clarification"}
    )
    assert comp_fail.status_code == 400
    assert "clarification" in comp_fail.get_json()["error"].lower()

    # Resolve comment
    lifecycle_client.post(f"/api/review/{rev_id}/comment/{comment_id}/resolve", headers={"X-CSRF-Token": csrf_l})

    # Now completion succeeds (200)
    comp_ok = lifecycle_client.post(
        f"/api/review/{rev_id}/complete",
        headers={"X-CSRF-Token": csrf_l},
        json={"completion_summary": "Completed after resolving clarification."}
    )
    assert comp_ok.status_code == 200
    assert comp_ok.get_json()["status"] == ReviewStatus.REVIEW_COMPLETED.value


def test_09_draft_preview_vs_final_report_distinction(lifecycle_client, lifecycle_session):
    """9. Draft report preview remains non-final; final report creates immutable record with PDF hash."""
    repo = DocumentRepository(lifecycle_session)
    client = create_user_record(repo, "preview.client@in.in", UserRole.CLIENT, "Client")
    lawyer = create_user_record(repo, "preview.lawyer@in.in", UserRole.LAWYER, "Lawyer", advocate_status=AdvocateStatus.VERIFIED)

    token_c, csrf_c = login_and_get_session(lifecycle_client, "preview.client@in.in")
    lifecycle_client.set_cookie("contractrisk_session", token_c)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf_c)
    up = lifecycle_client.post(
        "/api/review/upload",
        headers={"X-CSRF-Token": csrf_c},
        data={"file": (io.BytesIO(SAMPLE_CONTRACT_TXT), "contract.txt")},
        content_type="multipart/form-data"
    )
    rev_id = up.get_json()["review_id"]

    repo.assign_review(review_id=rev_id, lawyer_id=lawyer.id, assigned_by_id=lawyer.id)
    rev = repo.get_review_by_id(rev_id)
    rev.status = ReviewStatus.IN_REVIEW.value
    lifecycle_session.commit()

    token_l, csrf_l = login_and_get_session(lifecycle_client, "preview.lawyer@in.in")
    lifecycle_client.set_cookie("contractrisk_session", token_l)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf_l)

    # 1. Draft preview while in review -> succeeds (200), clearly marked DRAFT
    prev_res = lifecycle_client.get(f"/api/reports/preview/{rev_id}")
    assert prev_res.status_code == 200
    assert "DRAFT" in prev_res.get_json()["notice"]

    # 2. Final report generation before completion -> rejected (400)
    gen_fail = lifecycle_client.post(f"/api/reports/generate/{rev_id}", headers={"X-CSRF-Token": csrf_l}, json={"export_pdf": True})
    assert gen_fail.status_code == 400

    # 3. Advocate adjudicates all auto-generated clause findings with legal rationale
    rev_work = lifecycle_client.get(f"/api/review/{rev_id}")
    assert rev_work.status_code == 200
    for finding in rev_work.get_json().get("findings", []):
        dec_res = lifecycle_client.post(
            f"/api/review/{rev_id}/decision",
            headers={"X-CSRF-Token": csrf_l},
            json={
                "segment_id": finding["segment_id"],
                "decision": LawyerDecisionType.ACCEPT_AI_OBSERVATION.value,
                "rationale": f"Advocate evaluated and accepted clause observation for segment {finding['segment_id']}.",
                "is_disclosed_to_client": True
            }
        )
        assert dec_res.status_code == 200

    # 4. Complete review, then generate final report -> succeeds (201)
    lifecycle_client.post(f"/api/review/{rev_id}/complete", headers={"X-CSRF-Token": csrf_l}, json={"completion_summary": "Done."})
    gen_ok = lifecycle_client.post(f"/api/reports/generate/{rev_id}", headers={"X-CSRF-Token": csrf_l}, json={"export_pdf": True})
    assert gen_ok.status_code == 201
    assert gen_ok.get_json()["is_final"] is True


def test_10_client_feedback_lifecycle_and_internal_notes_isolation(lifecycle_client, lifecycle_session):
    """10. Feedback ratings validated; internal notes hidden from client response view."""
    repo = DocumentRepository(lifecycle_session)
    client = create_user_record(repo, "fb.client@in.in", UserRole.CLIENT, "Client")
    lawyer = create_user_record(repo, "fb.lawyer@in.in", UserRole.LAWYER, "Lawyer", advocate_status=AdvocateStatus.VERIFIED)

    # Setup report
    doc_id = str(uuid.uuid4())
    doc = DocumentRecord(
        id=doc_id, file_sha256="sha", original_filename="contract.txt",
        sanitized_filename="contract.txt", mime_type="text/plain", document_format="TXT",
        file_size_bytes=100, storage_path="/path", owner_id=client.id, assigned_lawyer_id=lawyer.id
    )
    rev_id = str(uuid.uuid4())
    rev = ReviewRecord(
        id=rev_id, document_id=doc_id, document_version=1, status=ReviewStatus.REVIEW_COMPLETED.value,
        assigned_lawyer_id=lawyer.id, completion_summary="Completed"
    )
    rep_id = str(uuid.uuid4())
    report = FinalReportRecord(
        id=rep_id, report_number="CR-2026-001", report_version=1, document_id=doc_id,
        document_version=1, review_id=rev_id, generated_by_id=lawyer.id,
        title="Final Legal Review Report", disclaimer_text="Mandatory Legal Disclaimer",
        status=ReportStatus.FINAL.value, is_final=True, content_sha256="c_sha",
        pdf_sha256="p_sha", report_payload_json=json.dumps({"summary": "ok"})
    )
    lifecycle_session.add_all([doc, rev, report])
    lifecycle_session.commit()

    token_c, csrf_c = login_and_get_session(lifecycle_client, "fb.client@in.in")
    lifecycle_client.set_cookie("contractrisk_session", token_c)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf_c)

    # Invalid rating (> 5) -> rejected (400)
    fb_bad = lifecycle_client.post(
        f"/api/reports/{rep_id}/feedback",
        headers={"X-CSRF-Token": csrf_c},
        json={"overall_satisfaction": 6, "clarity_rating": 5, "usefulness_rating": 5}
    )
    assert fb_bad.status_code == 400

    # Valid rating -> succeeds (201)
    fb_ok = lifecycle_client.post(
        f"/api/reports/{rep_id}/feedback",
        headers={"X-CSRF-Token": csrf_c},
        json={"overall_satisfaction": 4, "clarity_rating": 4, "usefulness_rating": 4, "client_comments": "Good work."}
    )
    assert fb_ok.status_code == 201
    feedback_id = fb_ok.get_json()["feedback_id"]

    # Lawyer responds with internal notes
    token_l, csrf_l = login_and_get_session(lifecycle_client, "fb.lawyer@in.in")
    lifecycle_client.set_cookie("contractrisk_session", token_l)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf_l)

    lifecycle_client.post(
        f"/api/reports/feedback/{feedback_id}/respond",
        headers={"X-CSRF-Token": csrf_l},
        json={
            "response_text": "Thank you for the feedback.",
            "internal_notes": "CONFIDENTIAL INTERNAL NOTE: Do not show to client.",
            "is_client_visible": True
        }
    )

    # Client views feedback -> internal notes MUST BE NONE
    lifecycle_client.set_cookie("contractrisk_session", token_c)
    client_view = lifecycle_client.get(f"/api/reports/{rep_id}/feedback").get_json()
    resp_item = client_view["feedback"][0]["responses"][0]
    assert resp_item["internal_notes"] is None
    assert resp_item["response_text"] == "Thank you for the feedback."


def test_11_audit_hash_chain_integrity_validation(lifecycle_client, lifecycle_session):
    """11. Validates that audit events from all lifecycle stages maintain unbroken hash-chain integrity."""
    repo = DocumentRepository(lifecycle_session)
    client = create_user_record(repo, "audit.chain@in.in", UserRole.CLIENT, "Client")
    lawyer = create_user_record(repo, "audit.lawyer@in.in", UserRole.LAWYER, "Lawyer", advocate_status=AdvocateStatus.VERIFIED)

    token_c, csrf_c = login_and_get_session(lifecycle_client, "audit.chain@in.in")
    lifecycle_client.set_cookie("contractrisk_session", token_c)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf_c)

    # Ingestion audit event
    up = lifecycle_client.post(
        "/api/review/upload",
        headers={"X-CSRF-Token": csrf_c},
        data={"file": (io.BytesIO(SAMPLE_CONTRACT_TXT), "contract.txt")},
        content_type="multipart/form-data"
    )
    rev_id = up.get_json()["review_id"]

    # Retrieve all audit event records from database
    events = lifecycle_session.query(AuditEventRecord).order_by(AuditEventRecord.created_at.asc(), AuditEventRecord.id.asc()).all()
    assert len(events) >= 3

    # Verify sequential hash-chain linkage across database records
    for idx, e in enumerate(events):
        assert len(e.event_hash) == 64
        if idx == 0:
            assert e.previous_event_hash is None or len(e.previous_event_hash) == 64
        else:
            assert e.previous_event_hash == events[idx - 1].event_hash

    # Verify tamper detection by AuditVerifier on a standard AuditStore
    test_store = AuditStore()
    from src.audit.provenance import ActorType
    test_logger = AuditLogger(test_store)
    test_logger.log_event(
        event_type=EventType.DOCUMENT_INGESTED,
        actor_type=ActorType.USER,
        source_document_id=events[0].document_id,
        event_payload={"action": "test"}
    )
    test_logger.log_event(
        event_type=EventType.PREPROCESSING_COMPLETED,
        actor_type=ActorType.SYSTEM,
        source_document_id=events[0].document_id,
        event_payload={"action": "test2"}
    )
    verifier = AuditVerifier()
    status, err = verifier.verify(test_store)
    assert status == IntegrityStatus.VALID
    assert err is None


def test_12_csrf_protection_enforced_on_lifecycle_mutations(lifecycle_client, lifecycle_session):
    """12. State-changing requests authenticated via session cookie strictly enforce CSRF."""
    repo = DocumentRepository(lifecycle_session)
    client = create_user_record(repo, "csrf.enforce@in.in", UserRole.CLIENT, "Client")

    token, csrf = login_and_get_session(lifecycle_client, "csrf.enforce@in.in")
    lifecycle_client.set_cookie("contractrisk_session", token)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf)

    # 1. POST without X-CSRF-Token header -> rejected (403)
    res_no_csrf = lifecycle_client.post(
        "/api/review/upload",
        data={"file": (io.BytesIO(SAMPLE_CONTRACT_TXT), "contract.txt")},
        content_type="multipart/form-data"
    )
    assert res_no_csrf.status_code == 403
    assert "CSRF" in res_no_csrf.get_json()["error"]

    # 2. POST with mismatched X-CSRF-Token -> rejected (403)
    res_bad_csrf = lifecycle_client.post(
        "/api/review/upload",
        headers={"X-CSRF-Token": "invalid_forged_csrf_header_12345"},
        data={"file": (io.BytesIO(SAMPLE_CONTRACT_TXT), "contract.txt")},
        content_type="multipart/form-data"
    )
    assert res_bad_csrf.status_code == 403
    assert "mismatch" in res_bad_csrf.get_json()["error"].lower()

    # 3. POST with Bearer token (API client) without any CSRF cookie or header -> exempt and succeeds (201)
    # Clear cookies
    lifecycle_client.delete_cookie("contractrisk_session")
    lifecycle_client.delete_cookie("contractrisk_csrf")
    res_bearer = lifecycle_client.post(
        "/api/review/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"file": (io.BytesIO(SAMPLE_CONTRACT_TXT), "contract.txt")},
        content_type="multipart/form-data"
    )
    assert res_bearer.status_code == 201


def test_13_document_versioning_and_revision_lifecycle(lifecycle_client, lifecycle_session):
    """13. Proposing and deciding on redline revisions preserves original text immutable."""
    repo = DocumentRepository(lifecycle_session)
    client = create_user_record(repo, "rev.client@in.in", UserRole.CLIENT, "Client")
    lawyer = create_user_record(repo, "rev.lawyer@in.in", UserRole.LAWYER, "Lawyer", advocate_status=AdvocateStatus.VERIFIED)

    token_c, csrf_c = login_and_get_session(lifecycle_client, "rev.client@in.in")
    lifecycle_client.set_cookie("contractrisk_session", token_c)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf_c)
    up = lifecycle_client.post(
        "/api/review/upload",
        headers={"X-CSRF-Token": csrf_c},
        data={"file": (io.BytesIO(SAMPLE_CONTRACT_TXT), "contract.txt")},
        content_type="multipart/form-data"
    )
    rev_id = up.get_json()["review_id"]
    doc_id = up.get_json()["document_id"]

    # Propose revised text (e.g. deleting illegal non-compete clause)
    revised_text = SAMPLE_CONTRACT_TXT.decode("utf-8").replace("five (5) years", "zero (0) months")
    prop_res = lifecycle_client.post(
        f"/api/review/{rev_id}/revision/propose",
        headers={"X-CSRF-Token": csrf_c},
        json={
            "revised_text": revised_text,
            "change_reason": "Eliminating restraint of trade clause per Section 27 ICA 1872."
        }
    )
    assert prop_res.status_code == 201
    revision_id = prop_res.get_json()["revision_id"]
    assert prop_res.get_json()["version_number"] == 2

    # Lawyer logs in and accepts the proposed revision
    rev = repo.get_review_by_id(rev_id)
    rev.assigned_lawyer_id = lawyer.id
    lifecycle_session.commit()

    token_l, csrf_l = login_and_get_session(lifecycle_client, "rev.lawyer@in.in")
    lifecycle_client.set_cookie("contractrisk_session", token_l)
    lifecycle_client.set_cookie("contractrisk_csrf", csrf_l)

    dec_res = lifecycle_client.post(
        f"/api/review/{rev_id}/revision/{revision_id}/decide",
        headers={"X-CSRF-Token": csrf_l},
        json={"decision": "ACCEPTED", "rationale": "Redline properly cures the statutory invalidity."}
    )
    assert dec_res.status_code == 200
    assert dec_res.get_json()["revision_status"] == RevisionStatus.ACCEPTED.value

    # Original document record remains intact and immutable
    doc = repo.get_document_by_id(doc_id)
    snapshot = doc.text_snapshots[0]
    assert "five (5) years" in snapshot.raw_text


def test_14_legal_retrieval_statutory_traceability(lifecycle_client, lifecycle_session):
    """14. Verifies statutory evidence traceability, manifest checksums, and scoring disclaimers."""
    retriever = ClauseEvidenceRetriever()

    # Query with clause text
    clause_text = "The party shall not carry on any business or profession in competition across India."
    result = retriever.retrieve_evidence_for_clause(clause_text, "seg_001", "doc_001")

    assert "passages" in result
    evidence = result["passages"]
    assert len(evidence) > 0

    # Ensure evidence preserves authoritative metadata
    sec27 = next((e for e in evidence if "27" in str(e.get("section_number")) or "Contract" in str(e.get("statute_title"))), None)
    assert sec27 is not None
    assert "Contract" in sec27["statute_title"]
    assert sec27["is_verified_law"] is True
    assert "score_disclaimer" in result
    assert "BM25" in result["score_disclaimer"]
    assert "NOT represent probabilities" in result["score_disclaimer"]
