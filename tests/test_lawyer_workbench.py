"""
Comprehensive Automated Test Suite for Task 033: Collaborative Lawyer Review Workbench.

Covers all 24 required verification areas:
1. Review creation and initialization.
2. Persistent review-state transitions and server-side rejection of invalid transitions.
3. Assignment authorization restricted to Supervising Lawyers.
4. Client ownership enforcement and multi-tenant isolation.
5. Assigned versus unassigned lawyer access boundaries (403 for unassigned).
6. Supervisory access and oversight.
7. Advocate verification restrictions (AdvocateStatus.VERIFIED gate).
8. Finding creation and lawyer decision recording with mandatory rationale.
9. Independent lawyer-authored findings (LAWYER_AUTHORED origin).
10. Evidence linkage to authoritative Indian statutory extracts and score disclaimers.
11. Comments and visibility scopes (INTERNAL_LAWYER_ONLY strictly hidden from client).
12. Client clarification workflow and resolution.
13. Revision creation and immutable preservation of original uploaded contracts.
14. Document-version association.
15. Explicit, audited review reopening with mandatory rationale.
16. Completion prerequisites and mandatory statutory disclaimer attachment.
17. Audit event creation and cryptographic hash chaining.
18. Server-side authorization failure handling (401/403).
19. No cross-client data leakage.
20. Compatibility with Task 030 document ingestion.
21. Compatibility with Task 031 authentication and RBAC.
22. Compatibility with Task 032 authoritative Indian legal retrieval.
23. Prevention of client self-assignment as reviewing advocate.
24. Eligible verified advocate listing with honest manual verification provenance.
"""

import os
import json
import uuid
import datetime
import pytest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.persistence.database import Base, get_session_factory
from src.persistence.models import (
    UserRecord, DocumentRecord, ExtractedTextSnapshot, SegmentRecord,
    UserRole, AccountStatus, AdvocateStatus,
    ReviewRecord, ReviewStateTransitionRecord, ClauseFindingRecord,
    ReviewCommentRecord, DocumentRevisionRecord,
    ReviewStatus, LawyerDecisionType, FindingOrigin, CommentVisibility, RevisionStatus,
    AuditEventRecord
)
from src.persistence.repository import DocumentRepository
from src.auth.token import TokenManager
from src.auth.password import PasswordManager
from src.review.service import ReviewService, MANDATORY_REVIEW_DISCLAIMER
from src.review.evidence import ClauseEvidenceRetriever, SCORE_SEMANTICS_DISCLAIMER
from src.audit.integrity import AuditVerifier
from src.audit.provenance import IntegrityStatus, EventType
from src.dashboard.app import app

# =============================================================================
# TEST FIXTURES
# =============================================================================

@pytest.fixture
def wb_db_engine():
    """Isolated in-memory SQLite database for workbench testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

@pytest.fixture
def wb_session(wb_db_engine):
    factory = sessionmaker(bind=wb_db_engine, autocommit=False, autoflush=False)
    sess = factory()
    yield sess
    sess.rollback()
    sess.close()

@pytest.fixture
def flask_client(wb_db_engine):
    app.config["TESTING"] = True
    factory = get_session_factory(wb_db_engine)
    with patch("src.persistence.database.get_engine", return_value=wb_db_engine):
        with patch("src.auth.rbac.get_db_session", side_effect=factory):
            with patch("src.review.routes.get_db_session", side_effect=factory):
                with patch("src.auth.routes.get_db_session", side_effect=factory):
                    with app.test_client() as client:
                        yield client

def make_test_user(
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
        bar_enrolment_id="D/1234/2018" if role in (UserRole.LAWYER, UserRole.SUPERVISING_LAWYER) else None,
        state_bar_council="Delhi" if role in (UserRole.LAWYER, UserRole.SUPERVISING_LAWYER) else None,
        year_of_enrolment=2018 if role in (UserRole.LAWYER, UserRole.SUPERVISING_LAWYER) else None
    )

def make_test_document(
    repo: DocumentRepository,
    owner_id: str,
    filename: str = "commercial_contract.pdf"
) -> DocumentRecord:
    doc_id = str(uuid.uuid4())
    doc = DocumentRecord(
        id=doc_id,
        file_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        original_filename=filename,
        sanitized_filename=filename,
        mime_type="application/pdf",
        document_format="PDF",
        file_size_bytes=1024,
        storage_path=f"data/contracts/{doc_id}_{filename}",
        owner_id=owner_id,
        status="SEGMENTED",
        extraction_method="PDF_PARSER",
        page_count=2,
        char_count=500
    )
    repo.session.add(doc)

    raw_text = (
        "1. Indemnity Clause: The contractor shall indemnify and hold harmless the principal against any claims.\n"
        "2. Limitation of Liability: In no event shall liability exceed the total fee paid under this agreement.\n"
        "3. Governing Law: This contract shall be governed by the laws of India and courts in New Delhi."
    )
    snap = ExtractedTextSnapshot(
        id=str(uuid.uuid4()),
        document_id=doc_id,
        raw_text=raw_text,
        char_count=len(raw_text),
        text_sha256="abc123hash"
    )
    repo.session.add(snap)

    # Add 3 segments
    seg1 = SegmentRecord(
        id=str(uuid.uuid4()),
        document_id=doc_id,
        segment_id="seg-indemnity-001",
        segment_type="CLAUSE",
        text="The contractor shall indemnify and hold harmless the principal against any claims.",
        original_start=0,
        original_end=85,
        heading="Indemnity",
        sequence=0
    )
    seg2 = SegmentRecord(
        id=str(uuid.uuid4()),
        document_id=doc_id,
        segment_id="seg-liability-002",
        segment_type="CLAUSE",
        text="In no event shall liability exceed the total fee paid under this agreement.",
        original_start=86,
        original_end=160,
        heading="Limitation of Liability",
        sequence=1
    )
    repo.session.add_all([seg1, seg2])
    repo.session.flush()
    return doc

def auth_headers(user: UserRecord) -> dict:
    tm = TokenManager()
    token = tm.generate_token(user)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# =============================================================================
# 24 REQUIRED TEST CASES
# =============================================================================

def test_01_review_creation(wb_session):
    """1. Review creation and persistent initialization."""
    repo = DocumentRepository(wb_session)
    client_u = make_test_user(repo, "client1@example.com", UserRole.CLIENT)
    doc = make_test_document(repo, client_u.id)

    service = ReviewService(wb_session)
    review = service.initiate_review(doc.id, actor_user=client_u)

    assert review.id is not None
    assert review.document_id == doc.id
    assert review.status == ReviewStatus.DOCUMENT_SUBMITTED.value
    assert review.document_version == 1
    assert len(review.transitions) == 1
    assert review.transitions[0].to_state == ReviewStatus.DOCUMENT_SUBMITTED.value

def test_02_review_state_transitions(wb_session):
    """2. Persistent review-state transitions and server-side rejection of invalid transitions."""
    repo = DocumentRepository(wb_session)
    client_u = make_test_user(repo, "client_trans@example.com", UserRole.CLIENT)
    sup_u = make_test_user(repo, "sup_trans@example.com", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)
    doc = make_test_document(repo, client_u.id)

    service = ReviewService(wb_session)
    review = service.initiate_review(doc.id, actor_user=client_u)

    # Valid transition: DOCUMENT_SUBMITTED -> AWAITING_LAWYER_ASSIGNMENT
    t1 = service.transition_review_state(review.id, ReviewStatus.AWAITING_LAWYER_ASSIGNMENT.value, actor_user=client_u, reason="Submitted for review")
    assert t1.status == ReviewStatus.AWAITING_LAWYER_ASSIGNMENT.value

    # Invalid transition: AWAITING_LAWYER_ASSIGNMENT -> REVIEW_COMPLETED directly must fail
    with pytest.raises(ValueError) as exc:
        service.transition_review_state(review.id, ReviewStatus.REVIEW_COMPLETED.value, actor_user=sup_u)
    assert "Invalid state transition" in str(exc.value)

def test_03_assignment_authorization(wb_session):
    """3. Assignment authorization restricted to Supervising Lawyers."""
    repo = DocumentRepository(wb_session)
    client_u = make_test_user(repo, "client_asgn@example.com", UserRole.CLIENT)
    lawyer_u = make_test_user(repo, "lawyer_asgn@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    sup_u = make_test_user(repo, "sup_asgn@example.com", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)
    doc = make_test_document(repo, client_u.id)

    service = ReviewService(wb_session)
    review = service.initiate_review(doc.id, actor_user=client_u)

    # Client cannot assign
    with pytest.raises(PermissionError):
        service.assign_review(review.id, lawyer_u.id, assigning_user=client_u)

    # Regular lawyer cannot assign
    with pytest.raises(PermissionError):
        service.assign_review(review.id, lawyer_u.id, assigning_user=lawyer_u)

    # Supervising lawyer can assign
    assigned = service.assign_review(review.id, lawyer_u.id, assigning_user=sup_u, rationale="Commercial contract expertise")
    assert assigned.assigned_lawyer_id == lawyer_u.id
    assert assigned.status == ReviewStatus.ASSIGNED.value

def test_04_client_ownership_enforcement(wb_session):
    """4. Client ownership enforcement and multi-tenant isolation."""
    repo = DocumentRepository(wb_session)
    client_a = make_test_user(repo, "client_a@example.com", UserRole.CLIENT)
    client_b = make_test_user(repo, "client_b@example.com", UserRole.CLIENT)
    doc_a = make_test_document(repo, client_a.id)

    service = ReviewService(wb_session)
    review_a = service.initiate_review(doc_a.id, actor_user=client_a)

    # Client B cannot access review A
    assert service.can_user_access_review(client_b, review_a) is False
    assert service.can_user_access_review(client_a, review_a) is True

def test_05_assigned_vs_unassigned_lawyer_access(wb_session, flask_client):
    """5. Assigned versus unassigned lawyer access boundaries (403 for unassigned)."""
    repo = DocumentRepository(wb_session)
    client_u = make_test_user(repo, "client_access@example.com", UserRole.CLIENT)
    lawyer_assigned = make_test_user(repo, "lawyer_assigned@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    lawyer_unassigned = make_test_user(repo, "lawyer_unassigned@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    sup_u = make_test_user(repo, "sup_access@example.com", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)
    doc = make_test_document(repo, client_u.id)

    service = ReviewService(wb_session)
    review = service.initiate_review(doc.id, actor_user=client_u)
    service.assign_review(review.id, lawyer_assigned.id, assigning_user=sup_u)
    wb_session.commit()

    # Assigned lawyer succeeds
    res_assigned = flask_client.get(f"/api/review/{review.id}", headers=auth_headers(lawyer_assigned))
    assert res_assigned.status_code == 200

    # Unassigned lawyer rejected with 403
    res_unassigned = flask_client.get(f"/api/review/{review.id}", headers=auth_headers(lawyer_unassigned))
    assert res_unassigned.status_code == 403

def test_06_supervisory_access(wb_session, flask_client):
    """6. Supervisory access and oversight."""
    repo = DocumentRepository(wb_session)
    client_u = make_test_user(repo, "client_sup@example.com", UserRole.CLIENT)
    sup_u = make_test_user(repo, "sup_full@example.com", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)
    doc = make_test_document(repo, client_u.id)

    service = ReviewService(wb_session)
    review = service.initiate_review(doc.id, actor_user=client_u)
    wb_session.commit()

    res = flask_client.get(f"/api/review/{review.id}", headers=auth_headers(sup_u))
    assert res.status_code == 200
    data = res.get_json()
    assert data["review"]["id"] == review.id

def test_07_advocate_verification_restrictions(wb_session):
    """7. Advocate verification restrictions (AdvocateStatus.VERIFIED gate)."""
    repo = DocumentRepository(wb_session)
    client_u = make_test_user(repo, "client_adv@example.com", UserRole.CLIENT)
    unverified_l = make_test_user(repo, "unverified_l@example.com", UserRole.LAWYER, AdvocateStatus.PENDING_VERIFICATION)
    verified_l = make_test_user(repo, "verified_l@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    sup_u = make_test_user(repo, "sup_adv@example.com", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)
    doc = make_test_document(repo, client_u.id)

    service = ReviewService(wb_session)
    review = service.initiate_review(doc.id, actor_user=client_u)

    # Unverified advocate cannot be assigned
    with pytest.raises(ValueError) as exc:
        service.assign_review(review.id, unverified_l.id, assigning_user=sup_u)
    assert "Verification status is 'PENDING_VERIFICATION'" in str(exc.value)

    # Verified advocate can be assigned
    service.assign_review(review.id, verified_l.id, assigning_user=sup_u)
    assert review.assigned_lawyer_id == verified_l.id

def test_08_finding_decisions_and_rationale(wb_session):
    """8. Finding creation and lawyer decision recording with mandatory rationale."""
    repo = DocumentRepository(wb_session)
    client_u = make_test_user(repo, "client_dec@example.com", UserRole.CLIENT)
    lawyer_u = make_test_user(repo, "lawyer_dec@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    sup_u = make_test_user(repo, "sup_dec@example.com", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)
    doc = make_test_document(repo, client_u.id)

    service = ReviewService(wb_session)
    review = service.initiate_review(doc.id, actor_user=client_u)
    service.assign_review(review.id, lawyer_u.id, assigning_user=sup_u)

    # Empty rationale must fail
    with pytest.raises(ValueError):
        service.record_clause_decision(
            review_id=review.id,
            segment_id="seg-indemnity-001",
            decision=LawyerDecisionType.CORRECT_AI_OBSERVATION.value,
            lawyer_rationale="",
            actor_user=lawyer_u
        )

    # Valid decision
    finding = service.record_clause_decision(
        review_id=review.id,
        segment_id="seg-indemnity-001",
        decision=LawyerDecisionType.CORRECT_AI_OBSERVATION.value,
        lawyer_rationale="Scope of indemnity must be capped per commercial standards.",
        actor_user=lawyer_u,
        lawyer_notes="Internal note: Check subclause 4.",
        is_disclosed_to_client=True
    )
    assert finding.decision == LawyerDecisionType.CORRECT_AI_OBSERVATION.value
    assert finding.is_disclosed_to_client is True
    assert review.status == ReviewStatus.IN_REVIEW.value

def test_09_independent_lawyer_authored_findings(wb_session):
    """9. Independent lawyer-authored findings (LAWYER_AUTHORED origin)."""
    repo = DocumentRepository(wb_session)
    client_u = make_test_user(repo, "client_auth@example.com", UserRole.CLIENT)
    lawyer_u = make_test_user(repo, "lawyer_auth@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    sup_u = make_test_user(repo, "sup_auth@example.com", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)
    doc = make_test_document(repo, client_u.id)

    service = ReviewService(wb_session)
    review = service.initiate_review(doc.id, actor_user=client_u)
    service.assign_review(review.id, lawyer_u.id, assigning_user=sup_u)

    finding = service.create_lawyer_authored_finding(
        review_id=review.id,
        segment_id="seg-liability-002",
        risk_label="UNREASONABLE_LIABILITY_CAP",
        lawyer_observation="Liability limitation excludes gross negligence without mutual carve-outs.",
        decision=LawyerDecisionType.ACCEPT_AI_OBSERVATION.value,
        lawyer_rationale="Recommend adding reciprocal carve-out for gross negligence.",
        actor_user=lawyer_u,
        is_disclosed_to_client=True
    )
    assert finding.finding_origin == FindingOrigin.LAWYER_AUTHORED.value
    assert finding.risk_label == "UNREASONABLE_LIABILITY_CAP"

def test_10_statutory_evidence_linkage():
    """10. Evidence linkage to authoritative Indian statutory extracts and score disclaimers."""
    retriever = ClauseEvidenceRetriever()
    res = retriever.retrieve_evidence_for_clause(
        clause_text="The contractor shall indemnify the principal for losses arising from breach of contract.",
        clause_id="test-clause-10"
    )
    assert res["status"] in ("EVIDENCE_FOUND", "ABSTAIN")
    assert "score_disclaimer" in res
    assert "heuristic lexical/BM25 relevance" in res["score_disclaimer"]
    if res["passages"]:
        p = res["passages"][0]
        assert "statute_title" in p
        assert "ranking_score_meaning" in p

def test_11_comments_and_visibility_scopes(wb_session, flask_client):
    """11. Comments and visibility scopes (INTERNAL_LAWYER_ONLY strictly hidden from client)."""
    repo = DocumentRepository(wb_session)
    client_u = make_test_user(repo, "client_comm@example.com", UserRole.CLIENT)
    lawyer_u = make_test_user(repo, "lawyer_comm@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    sup_u = make_test_user(repo, "sup_comm@example.com", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)
    doc = make_test_document(repo, client_u.id)

    service = ReviewService(wb_session)
    review = service.initiate_review(doc.id, actor_user=client_u)
    service.assign_review(review.id, lawyer_u.id, assigning_user=sup_u)

    # Lawyer posts internal note
    c_internal = service.add_comment(
        review_id=review.id,
        actor_user=lawyer_u,
        comment_text="Internal analysis: The indemnity is overly broad.",
        visibility=CommentVisibility.INTERNAL_LAWYER_ONLY.value
    )
    # Lawyer posts client-visible comment
    c_client = service.add_comment(
        review_id=review.id,
        actor_user=lawyer_u,
        comment_text="Recommendation: Please specify liability cap amount.",
        visibility=CommentVisibility.CLIENT_VISIBLE.value
    )
    wb_session.commit()

    # Client view must have c_client, but NOT c_internal
    res_client = flask_client.get(f"/api/review/{review.id}", headers=auth_headers(client_u))
    assert res_client.status_code == 200
    client_comments = res_client.get_json()["comments"]
    comment_texts = [c["comment_text"] for c in client_comments]
    assert c_client.comment_text in comment_texts
    assert c_internal.comment_text not in comment_texts

    # Client posting internal lawyer note must be rejected
    with pytest.raises(PermissionError):
        service.add_comment(
            review_id=review.id,
            actor_user=client_u,
            comment_text="Client trying to write internal note",
            visibility=CommentVisibility.INTERNAL_LAWYER_ONLY.value
        )

def test_12_client_clarification_workflow(wb_session):
    """12. Client clarification workflow and resolution."""
    repo = DocumentRepository(wb_session)
    client_u = make_test_user(repo, "client_clar@example.com", UserRole.CLIENT)
    lawyer_u = make_test_user(repo, "lawyer_clar@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    sup_u = make_test_user(repo, "sup_clar@example.com", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)
    doc = make_test_document(repo, client_u.id)

    service = ReviewService(wb_session)
    review = service.initiate_review(doc.id, actor_user=client_u)
    service.assign_review(review.id, lawyer_u.id, assigning_user=sup_u)

    # Lawyer asks clarification
    clar_req = service.add_comment(
        review_id=review.id,
        actor_user=lawyer_u,
        comment_text="Does the indemnity cover third-party intellectual property claims?",
        visibility=CommentVisibility.CLARIFICATION_REQUEST.value
    )
    assert clar_req.is_resolved is False

    # Client replies
    reply = service.add_comment(
        review_id=review.id,
        actor_user=client_u,
        comment_text="No, IP claims are governed separately under Section 7.",
        visibility=CommentVisibility.CLIENT_RESPONSE.value,
        parent_comment_id=clar_req.id
    )
    assert reply.parent_comment_id == clar_req.id

    # Lawyer resolves
    resolved = service.resolve_comment(clar_req.id, actor_user=lawyer_u)
    assert resolved.is_resolved is True

def test_13_revision_creation_and_original_preservation(wb_session):
    """13. Revision creation and immutable preservation of original uploaded contracts."""
    repo = DocumentRepository(wb_session)
    client_u = make_test_user(repo, "client_rev@example.com", UserRole.CLIENT)
    lawyer_u = make_test_user(repo, "lawyer_rev@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    sup_u = make_test_user(repo, "sup_rev@example.com", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)
    doc = make_test_document(repo, client_u.id)
    original_sha256 = doc.file_sha256

    service = ReviewService(wb_session)
    review = service.initiate_review(doc.id, actor_user=client_u)
    service.assign_review(review.id, lawyer_u.id, assigning_user=sup_u)

    # Propose revised text
    revised_text = "1. Indemnity Clause: The contractor shall indemnify the principal up to INR 5,00,000."
    rev = service.propose_document_revision(
        document_id=doc.id,
        review_id=review.id,
        actor_user=lawyer_u,
        revised_text=revised_text,
        change_reason="Add liability cap per negotiation"
    )

    assert rev.version_number == 2
    assert rev.revision_status == RevisionStatus.PROPOSED.value
    assert rev.original_file_sha256 == original_sha256
    # Original document is untouched
    assert doc.file_sha256 == original_sha256

def test_14_document_version_association(wb_session):
    """14. Document-version association for findings and revisions."""
    repo = DocumentRepository(wb_session)
    client_u = make_test_user(repo, "client_ver@example.com", UserRole.CLIENT)
    lawyer_u = make_test_user(repo, "lawyer_ver@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    sup_u = make_test_user(repo, "sup_ver@example.com", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)
    doc = make_test_document(repo, client_u.id)

    service = ReviewService(wb_session)
    review = service.initiate_review(doc.id, actor_user=client_u)
    service.assign_review(review.id, lawyer_u.id, assigning_user=sup_u)

    finding = service.record_clause_decision(
        review_id=review.id,
        segment_id="seg-indemnity-001",
        decision=LawyerDecisionType.ACCEPT_AI_OBSERVATION.value,
        lawyer_rationale="Accepted as drafted",
        actor_user=lawyer_u
    )
    assert finding.document_version == review.document_version == 1

def test_15_review_reopening(wb_session):
    """15. Explicit, audited review reopening with mandatory rationale."""
    repo = DocumentRepository(wb_session)
    client_u = make_test_user(repo, "client_reopen@example.com", UserRole.CLIENT)
    lawyer_u = make_test_user(repo, "lawyer_reopen@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    sup_u = make_test_user(repo, "sup_reopen@example.com", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)
    doc = make_test_document(repo, client_u.id)

    service = ReviewService(wb_session)
    review = service.initiate_review(doc.id, actor_user=client_u)
    service.assign_review(review.id, lawyer_u.id, assigning_user=sup_u)
    service.transition_review_state(review.id, ReviewStatus.IN_REVIEW.value, actor_user=lawyer_u)

    completed = service.complete_review(
        review_id=review.id,
        actor_user=lawyer_u,
        completion_summary="All provisions reviewed and finalized."
    )
    assert completed.status == ReviewStatus.REVIEW_COMPLETED.value

    # Reopening with empty reason fails
    with pytest.raises(ValueError):
        service.reopen_review(review.id, actor_user=lawyer_u, reason="")

    # Valid reopening
    reopened = service.reopen_review(
        review.id,
        actor_user=lawyer_u,
        reason="Client submitted supplemental schedule for review."
    )
    assert reopened.status == ReviewStatus.IN_REVIEW.value

def test_16_completion_prerequisites(wb_session):
    """16. Completion prerequisites and mandatory statutory disclaimer attachment."""
    repo = DocumentRepository(wb_session)
    client_u = make_test_user(repo, "client_comp@example.com", UserRole.CLIENT)
    lawyer_u = make_test_user(repo, "lawyer_comp@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    sup_u = make_test_user(repo, "sup_comp@example.com", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)
    doc = make_test_document(repo, client_u.id)

    service = ReviewService(wb_session)
    review = service.initiate_review(doc.id, actor_user=client_u)
    service.assign_review(review.id, lawyer_u.id, assigning_user=sup_u)
    service.transition_review_state(review.id, ReviewStatus.IN_REVIEW.value, actor_user=lawyer_u)

    # Post an unresolved clarification request
    clar = service.add_comment(
        review_id=review.id,
        actor_user=lawyer_u,
        comment_text="Need clarification on payment terms.",
        visibility=CommentVisibility.CLARIFICATION_REQUEST.value
    )

    # Completion should be blocked due to open clarification
    with pytest.raises(ValueError) as exc:
        service.complete_review(review.id, actor_user=lawyer_u, completion_summary="Completed")
    assert "unresolved client clarification" in str(exc.value)

    # Resolve clarification
    service.resolve_comment(clar.id, actor_user=lawyer_u)

    # Completion succeeds
    completed = service.complete_review(
        review_id=review.id,
        actor_user=lawyer_u,
        completion_summary="Contract reviewed with no fatal liabilities.",
        outstanding_limitations="Excluded tax assessment",
        further_client_action_required=False
    )
    assert completed.status == ReviewStatus.REVIEW_COMPLETED.value
    assert completed.disclaimer_text == MANDATORY_REVIEW_DISCLAIMER

def test_17_audit_event_creation_and_chaining(wb_session):
    """17. Audit event creation and cryptographic hash chaining."""
    repo = DocumentRepository(wb_session)
    client_u = make_test_user(repo, "client_audit@example.com", UserRole.CLIENT)
    lawyer_u = make_test_user(repo, "lawyer_audit@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    sup_u = make_test_user(repo, "sup_audit@example.com", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)
    doc = make_test_document(repo, client_u.id)

    service = ReviewService(wb_session)
    review = service.initiate_review(doc.id, actor_user=client_u)
    service.assign_review(review.id, lawyer_u.id, assigning_user=sup_u)
    service.record_clause_decision(review.id, "seg-indemnity-001", LawyerDecisionType.ACCEPT_AI_OBSERVATION.value, "Fine", actor_user=lawyer_u)

    # Verify audit store
    events = repo.get_audit_events_for_document(doc.id)
    assert len(events) >= 3

    # Check hash chaining: every event has previous_event_hash linked
    for i in range(1, len(events)):
        assert events[i].previous_event_hash == events[i - 1].event_hash

def test_18_unauthorized_access_attempts(wb_session, flask_client):
    """18. Server-side authorization failure handling (401/403)."""
    repo = DocumentRepository(wb_session)
    client_u = make_test_user(repo, "client_unauth@example.com", UserRole.CLIENT)
    doc = make_test_document(repo, client_u.id)
    service = ReviewService(wb_session)
    review = service.initiate_review(doc.id, actor_user=client_u)
    wb_session.commit()

    # 401 Unauthenticated
    res_no_auth = flask_client.get(f"/api/review/{review.id}")
    assert res_no_auth.status_code == 401

    # 403 Forbidden: Client trying to assign lawyer
    res_forbidden = flask_client.post(
        f"/api/review/{review.id}/assign",
        headers=auth_headers(client_u),
        json={"lawyer_id": "someone"}
    )
    assert res_forbidden.status_code == 403

def test_19_no_cross_client_data_leakage(wb_session, flask_client):
    """19. No cross-client data leakage."""
    repo = DocumentRepository(wb_session)
    client_1 = make_test_user(repo, "client_one@example.com", UserRole.CLIENT)
    client_2 = make_test_user(repo, "client_two@example.com", UserRole.CLIENT)
    doc_1 = make_test_document(repo, client_1.id, "client1_secret.pdf")
    doc_2 = make_test_document(repo, client_2.id, "client2_secret.pdf")

    service = ReviewService(wb_session)
    r1 = service.initiate_review(doc_1.id, actor_user=client_1)
    r2 = service.initiate_review(doc_2.id, actor_user=client_2)
    wb_session.commit()

    # Client 2 queue does not contain Client 1's document
    res_q = flask_client.get("/api/review/queue", headers=auth_headers(client_2))
    assert res_q.status_code == 200
    q_data = res_q.get_json()
    doc_ids = [item["document_id"] for item in q_data["reviews"]]
    assert doc_2.id in doc_ids
    assert doc_1.id not in doc_ids

def test_20_task030_ingestion_compatibility(wb_session):
    """20. Compatibility with Task 030 document ingestion and segmentation persistence."""
    repo = DocumentRepository(wb_session)
    client_u = make_test_user(repo, "client_ingest@example.com", UserRole.CLIENT)
    doc = make_test_document(repo, client_u.id)

    # Ingestion snapshots and segments exist
    assert len(doc.text_snapshots) == 1
    assert len(doc.segments) == 2

    service = ReviewService(wb_session)
    review = service.initiate_review(doc.id, actor_user=client_u)
    assert review.document_id == doc.id
    assert len(review.document.segments) == 2

def test_21_task031_auth_rbac_compatibility(wb_session, flask_client):
    """21. Compatibility with Task 031 authentication and RBAC."""
    repo = DocumentRepository(wb_session)
    client_u = make_test_user(repo, "client_jwt@example.com", UserRole.CLIENT)
    wb_session.commit()

    # JWT Token decode and auth endpoint check
    headers = auth_headers(client_u)
    res = flask_client.get("/api/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["email"] == "client_jwt@example.com"

def test_22_task032_retrieval_compatibility():
    """22. Compatibility with Task 032 authoritative Indian legal retrieval."""
    from src.legal_sources.routes import get_corpus_services
    reg, idx, ret, mat = get_corpus_services()
    assert reg is not None
    assert idx is not None
    assert ret is not None
    assert mat is not None

def test_23_client_cannot_self_assign_as_reviewing_lawyer(wb_session):
    """23. Prevention of client self-assignment as reviewing advocate."""
    repo = DocumentRepository(wb_session)
    # A user who happens to have lawyer credentials owns a document as a client
    lawyer_owner = make_test_user(repo, "lawyer_owner@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    sup_u = make_test_user(repo, "sup_self@example.com", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)
    doc = make_test_document(repo, lawyer_owner.id)

    service = ReviewService(wb_session)
    review = service.initiate_review(doc.id, actor_user=lawyer_owner)

    # Supervisor cannot assign document owner as reviewing lawyer for their own document
    with pytest.raises(ValueError) as exc:
        service.assign_review(review.id, lawyer_owner.id, assigning_user=sup_u)
    assert "Document owner cannot be assigned as the reviewing advocate" in str(exc.value)

def test_24_eligible_advocates_list(wb_session, flask_client):
    """24. Eligible verified advocate listing with honest manual verification provenance."""
    repo = DocumentRepository(wb_session)
    sup_u = make_test_user(repo, "sup_list@example.com", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)
    make_test_user(repo, "verified_l1@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED, "Advocate One")
    make_test_user(repo, "unverified_l2@example.com", UserRole.LAWYER, AdvocateStatus.PENDING_VERIFICATION, "Advocate Two")
    wb_session.commit()

    res = flask_client.get("/api/review/advocates/eligible", headers=auth_headers(sup_u))
    assert res.status_code == 200
    data = res.get_json()
    emails = [a["email"] for a in data["advocates"]]
    assert "verified_l1@example.com" in emails
    assert "unverified_l2@example.com" not in emails
    for adv in data["advocates"]:
        assert adv["verification_method"] == "MANUAL_SUPERVISORY_VERIFICATION"
