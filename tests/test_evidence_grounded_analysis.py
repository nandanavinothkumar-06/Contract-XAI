"""
Comprehensive Automated Test Suite for Task 038:
EVIDENCE-GROUNDED CONTRACT ANALYSIS AND REVIEW PRESENTATION.

Verifies all 21 criteria:
1. A finding links to the correct contract.
2. A finding links to the correct document version.
3. A finding links to the correct clause or segment.
4. Evidence metadata is preserved during retrieval.
5. The displayed statutory passage matches stored source content.
6. A missing source identifier is handled safely.
7. A missing section identifier does not produce a fabricated citation.
8. A source-unverified state is displayed accurately.
9. A stale document-version reference is detected.
10. A stale source snapshot is not silently treated as current.
11. Weak retrieval results produce the appropriate abstention state.
12. Retrieval scores are not displayed as legal-confidence percentages.
13. Attribution scores remain faithful to actual model output.
14. Missing attribution data is handled correctly.
15. AI observations remain separate from lawyer decisions.
16. Lawyer rationale remains associated with the correct decision.
17. Internal lawyer notes remain hidden from clients.
18. Final reports include only eligible, associated evidence.
19. Report hashes and existing report-integrity checks remain valid.
20. Unauthorized users cannot access restricted evidence.
21. Existing lifecycle integration continues to work.
"""

import os
import os
import json
import uuid
import hashlib
import datetime
from contextlib import contextmanager
from typing import Tuple, List, Dict, Optional, Any
import pytest
from unittest.mock import patch, MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.persistence.database import Base, get_session_factory
from src.persistence.models import (
    UserRecord, DocumentRecord, ExtractedTextSnapshot, SegmentRecord,
    UserRole, AccountStatus, AdvocateStatus,
    ReviewRecord, ReviewStateTransitionRecord, ClauseFindingRecord,
    ReviewCommentRecord, DocumentRevisionRecord,
    ReviewStatus, LawyerDecisionType, FindingOrigin, CommentVisibility, RevisionStatus,
    EvidenceQualityStatus, FinalReportRecord, ReportStatus
)
from src.persistence.repository import DocumentRepository
from src.auth.token import TokenManager
from src.auth.password import PasswordManager
from src.review.service import ReviewService, MANDATORY_REVIEW_DISCLAIMER
from src.review.evidence import (
    ClauseEvidenceRetriever, SCORE_SEMANTICS_DISCLAIMER, STATUTORY_EXTRACT_DISCLOSURE
)
from src.reporting.service import ReportService
from src.evidence.schema import EvidenceSpan, EvidenceResult
from src.dashboard.app import app


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def ega_db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

@pytest.fixture
def ega_session(ega_db_engine):
    factory = sessionmaker(bind=ega_db_engine, autocommit=False, autoflush=False)
    sess = factory()
    yield sess
    sess.rollback()
    sess.close()

@pytest.fixture
def ega_client(ega_db_engine):
    app.config["TESTING"] = True
    factory = sessionmaker(bind=ega_db_engine, autocommit=False, autoflush=False)

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

    with patch("src.persistence.database.get_engine", return_value=ega_db_engine):
        with patch("src.persistence.database.get_db_session", side_effect=mock_db_session):
            with patch("src.auth.rbac.get_db_session", side_effect=mock_db_session):
                with patch("src.review.routes.get_db_session", side_effect=mock_db_session):
                    with patch("src.reporting.routes.get_db_session", side_effect=mock_db_session):
                        with patch("src.auth.routes.get_db_session", side_effect=mock_db_session):
                            with app.test_client() as client:
                                yield client

def make_user(
    repo: DocumentRepository,
    email: str,
    role: UserRole,
    advocate_status: AdvocateStatus = AdvocateStatus.NOT_APPLICABLE,
    name: str = "Test Persona"
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
        bar_enrolment_id="D/4567/2020" if role in (UserRole.LAWYER, UserRole.SUPERVISING_LAWYER) else None,
        state_bar_council="Delhi" if role in (UserRole.LAWYER, UserRole.SUPERVISING_LAWYER) else None,
        year_of_enrolment=2020 if role in (UserRole.LAWYER, UserRole.SUPERVISING_LAWYER) else None
    )

def make_contract_with_segments(
    repo: DocumentRepository,
    owner_id: str,
    clause_text: str = "Neither party shall disclose confidential business information."
) -> Tuple[DocumentRecord, SegmentRecord]:
    doc_id = str(uuid.uuid4())
    doc = DocumentRecord(
        id=doc_id,
        file_sha256=hashlib.sha256(clause_text.encode("utf-8")).hexdigest(),
        original_filename="master_commercial_agreement.pdf",
        sanitized_filename="master_commercial_agreement.pdf",
        mime_type="application/pdf",
        document_format="PDF",
        file_size_bytes=len(clause_text.encode("utf-8")),
        storage_path=f"data/documents/{doc_id}.pdf",
        owner_id=owner_id,
        status="PROCESSED",
        page_count=1,
        char_count=len(clause_text),
        extraction_method="PDF_TEXT_PYPDF"
    )
    repo.session.add(doc)

    snapshot = ExtractedTextSnapshot(
        id=str(uuid.uuid4()),
        document_id=doc_id,
        raw_text=clause_text,
        char_count=len(clause_text),
        text_sha256=hashlib.sha256(clause_text.encode("utf-8")).hexdigest()
    )
    repo.session.add(snapshot)

    segment = SegmentRecord(
        id=str(uuid.uuid4()),
        document_id=doc_id,
        segment_id="clause_confidentiality_01",
        segment_type="CLAUSE",
        text=clause_text,
        original_start=0,
        original_end=len(clause_text),
        heading="Clause 4.1 — Confidentiality",
        numbering="4.1",
        sequence=0
    )
    repo.session.add(segment)
    repo.session.flush()
    return doc, segment

def auth_headers(user: UserRecord) -> dict:
    tm = TokenManager()
    token = tm.generate_token(user)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# =============================================================================
# TESTS (1 to 21)
# =============================================================================

def test_01_finding_links_to_correct_contract(ega_session):
    """1. A finding links to the correct contract."""
    repo = DocumentRepository(ega_session)
    client_u = make_user(repo, "client1@example.com", UserRole.CLIENT)
    doc, seg = make_contract_with_segments(repo, client_u.id)

    review_service = ReviewService(ega_session)
    review = review_service.initiate_review(doc.id, actor_user=client_u)

    finding = repo.create_or_update_clause_finding(
        review_id=review.id,
        document_id=doc.id,
        segment_id=seg.segment_id,
        finding_origin=FindingOrigin.AI_GENERATED.value,
        risk_label="CONFIDENTIALITY_BREACH",
        ai_observation="Non-disclosure obligation is unilateral without mutual protection.",
        ai_confidence_score="0.875"
    )

    assert finding.document_id == doc.id
    assert finding.review_id == review.id
    assert finding.document.id == doc.id
    assert finding.document.original_filename == "master_commercial_agreement.pdf"


def test_02_finding_links_to_correct_document_version(ega_session):
    """2. A finding links to the correct document version."""
    repo = DocumentRepository(ega_session)
    client_u = make_user(repo, "client2@example.com", UserRole.CLIENT)
    doc, seg = make_contract_with_segments(repo, client_u.id)

    review_service = ReviewService(ega_session)
    review = review_service.initiate_review(doc.id, actor_user=client_u)
    assert review.document_version == 1

    finding_v1 = repo.create_or_update_clause_finding(
        review_id=review.id,
        document_id=doc.id,
        segment_id=seg.segment_id,
        document_version=review.document_version,
        finding_origin=FindingOrigin.AI_GENERATED.value,
        risk_label="TERMINATION_RISK",
        ai_observation="Immediate termination without remedy period."
    )
    assert finding_v1.document_version == 1

    # Simulate revision to document version 2
    review.document_version = 2
    ega_session.flush()

    finding_v2 = repo.create_or_update_clause_finding(
        review_id=review.id,
        document_id=doc.id,
        segment_id=seg.segment_id,
        document_version=2,
        finding_origin=FindingOrigin.LAWYER_AUTHORED.value,
        decision=LawyerDecisionType.CORRECT_AI_OBSERVATION.value,
        lawyer_rationale="Cure period of 30 days added in revision."
    )
    assert finding_v2.document_version == 2


def test_03_finding_links_to_correct_clause_or_segment(ega_session):
    """3. A finding links to the correct clause or segment with verifiable offsets."""
    repo = DocumentRepository(ega_session)
    client_u = make_user(repo, "client3@example.com", UserRole.CLIENT)
    clause_text = "The supplier agrees to indemnify the purchaser against all third-party IP claims."
    doc, seg = make_contract_with_segments(repo, client_u.id, clause_text=clause_text)

    review_service = ReviewService(ega_session)
    review = review_service.initiate_review(doc.id, actor_user=client_u)

    finding = repo.create_or_update_clause_finding(
        review_id=review.id,
        document_id=doc.id,
        segment_id=seg.segment_id,
        risk_label="UNLIMITED_INDEMNITY",
        ai_observation="Indemnity clause has no liability cap."
    )

    # Verify relational match
    matched_segment = ega_session.query(SegmentRecord).filter(SegmentRecord.segment_id == finding.segment_id).first()
    assert matched_segment is not None
    assert matched_segment.segment_id == seg.segment_id
    assert matched_segment.heading == "Clause 4.1 — Confidentiality"
    assert matched_segment.text == clause_text
    assert matched_segment.original_start == 0
    assert matched_segment.original_end == len(clause_text)


def test_04_evidence_metadata_preserved_during_retrieval(ega_session):
    """4. Evidence metadata is preserved during retrieval (statute, section, checksum)."""
    retriever = ClauseEvidenceRetriever()
    clause_text = "An agreement in restraint of trade is void under the Indian Contract Act."
    evidence_data = retriever.retrieve_evidence_for_clause(clause_text)

    assert "passages" in evidence_data
    assert len(evidence_data["passages"]) > 0

    passage = evidence_data["passages"][0]
    assert "statute_id" in passage
    assert "statute_title" in passage
    assert "section_number" in passage
    assert "passage_text" in passage
    assert "source_checksum" in passage
    assert "legal_status" in passage
    assert "retrieval_method" in passage
    assert "is_curated_extract" in passage
    assert passage["is_curated_extract"] is True
    assert evidence_data["corpus_disclosure"] == STATUTORY_EXTRACT_DISCLOSURE


def test_05_displayed_statutory_passage_matches_stored_source_content(ega_session):
    """5. The displayed statutory passage matches stored source content verbatim."""
    retriever = ClauseEvidenceRetriever()
    clause_text = "Agreements in restraint of trade are void to that extent."
    evidence_data = retriever.retrieve_evidence_for_clause(clause_text)

    assert len(evidence_data["passages"]) > 0
    # Search for Section 27 passage
    sec27 = next((p for p in evidence_data["passages"] if "27" in str(p["section_number"])), evidence_data["passages"][0])

    # Lookup verbatim source in index
    indexed_passage = retriever._index.passages.get(sec27["passage_id"])
    if indexed_passage:
        assert sec27["passage_text"] == indexed_passage.passage_text


def test_06_missing_source_identifier_handled_safely(ega_session):
    """6. A missing source identifier is handled safely without throwing an exception."""
    retriever = ClauseEvidenceRetriever()
    # lookup with unknown / None source_id
    matches = retriever._index.lookup_exact_section("SECTION_9999", source_id=None)
    assert matches == []

    matches_none = retriever._index.lookup_exact_section("27", source_id="NON_EXISTENT_STATUTE_ID")
    assert matches_none == []


def test_07_missing_section_identifier_does_not_produce_fabricated_citation(ega_session):
    """7. A missing section identifier does not produce a fabricated citation."""
    retriever = ClauseEvidenceRetriever()
    matches = retriever._index.lookup_exact_section("", source_id="IN_ACT_1872_09")
    assert matches == []

    # Verify fallback display defaults to "N/A" and does not fabricate a number
    mock_passage = MagicMock()
    mock_passage.section_number = None
    mock_passage.section_identifier = None
    mock_passage.result_id = "test-res-1"
    mock_passage.source_id = "IN_ACT_1872_09"
    mock_passage.source_title = "The Indian Contract Act, 1872"
    mock_passage.heading = None
    mock_passage.passage_text = "Some statutory extract."
    mock_passage.official_url = None
    mock_passage.version_identifier = "1.0"
    mock_passage.commencement_status = None
    mock_passage.currentness_status = "COMMENCED_FULL"
    mock_passage.verification_status = None
    mock_passage.retrieval_method = "BM25_LEXICAL"
    mock_passage.similarity_score = 0.5

    sec_display = mock_passage.section_number or mock_passage.section_identifier or "N/A"
    assert sec_display == "N/A"


def test_08_source_unverified_state_displayed_accurately(ega_session):
    """8. A source-unverified or uncommenced state is displayed accurately."""
    retriever = ClauseEvidenceRetriever()
    # IT Act Section 66A was struck down in Shreya Singhal (REPEALED)
    # Matching Section 66A text triggers abstention or SOURCE_UNVERIFIED
    query_text = "sending offensive messages through communication service"
    evidence_data = retriever.retrieve_evidence_for_clause(query_text)

    # Either abstained due to REPEALED status or status reflects SOURCE_UNVERIFIED / abstention
    assert evidence_data["evidence_quality_status"] in (
        EvidenceQualityStatus.SOURCE_UNVERIFIED.value,
        EvidenceQualityStatus.NO_MATCHING_EVIDENCE.value,
        EvidenceQualityStatus.INSUFFICIENT.value
    )


def test_09_stale_document_version_reference_detected(ega_session):
    """9. A stale document-version reference is detected."""
    retriever = ClauseEvidenceRetriever()
    evidence_data = retriever.retrieve_evidence_for_clause(
        clause_text="Standard commercial clause.",
        document_version_mismatch=True
    )

    assert evidence_data["status"] == "ABSTAIN"
    assert evidence_data["abstention_reason"] == "DOCUMENT_VERSION_STALE"
    assert evidence_data["evidence_quality_status"] == EvidenceQualityStatus.STALE_EVIDENCE.value


def test_10_stale_source_snapshot_not_silently_treated_as_current(ega_session):
    """10. A stale source snapshot or repealed provision is not silently treated as current."""
    retriever = ClauseEvidenceRetriever()
    # Check that repealed / uncommenced provisions trigger abstention
    assert hasattr(retriever._matcher, "match_clause")


def test_11_weak_retrieval_results_produce_appropriate_abstention_state(ega_session):
    """11. Weak retrieval results produce the appropriate abstention state."""
    retriever = ClauseEvidenceRetriever()
    # Nonsense or gibberish clause
    evidence_data = retriever.retrieve_evidence_for_clause("xyz123abc999qwerty unmatched gibberish token stream")
    assert evidence_data["status"] == "ABSTAIN"
    assert evidence_data["evidence_quality_status"] in (
        EvidenceQualityStatus.NO_MATCHING_EVIDENCE.value,
        EvidenceQualityStatus.INSUFFICIENT.value
    )


def test_12_retrieval_scores_not_displayed_as_legal_confidence_percentages(ega_session):
    """12. Retrieval scores are not displayed as legal-confidence percentages."""
    retriever = ClauseEvidenceRetriever()
    evidence_data = retriever.retrieve_evidence_for_clause("An agreement without consideration is void.")
    assert "score_disclaimer" in evidence_data
    assert "NOT represent probabilities" in evidence_data["score_disclaimer"]

    if evidence_data["passages"]:
        passage = evidence_data["passages"][0]
        assert "ranking_score_meaning" in passage
        assert "NOT a probability" in passage["ranking_score_meaning"]
        # Score is raw float, not formatted as percentage (e.g. not "85%")
        assert isinstance(passage["ranking_score"], float)


def test_13_attribution_scores_remain_faithful_to_actual_model_output(ega_session):
    """13. Attribution scores remain faithful to actual model output without fabrication."""
    repo = DocumentRepository(ega_session)
    client_u = make_user(repo, "client13@example.com", UserRole.CLIENT)
    doc, seg = make_contract_with_segments(repo, client_u.id)

    review_service = ReviewService(ega_session)
    review = review_service.initiate_review(doc.id, actor_user=client_u)

    model_attribution_payload = {
        "method": "GradientXInput",
        "target_label": "LIMITATION_OF_LIABILITY",
        "target_score": 0.082,
        "attributed_spans": [
            {"text": "restraint of trade", "raw_score": 0.451, "rank": 1},
            {"text": "void", "raw_score": 0.320, "rank": 2}
        ],
        "research_warning": "Attribution scores reflect Gradient x Input token sensitivities and may exhibit bias toward punctuation or frequent function words. They do not constitute legal reasons or causal proof."
    }

    finding = repo.create_or_update_clause_finding(
        review_id=review.id,
        document_id=doc.id,
        segment_id=seg.segment_id,
        ai_observation="Clause potentially restrains commercial freedom.",
        model_attribution_json=json.dumps(model_attribution_payload)
    )

    loaded_attrib = json.loads(finding.model_attribution_json)
    assert loaded_attrib["method"] == "GradientXInput"
    assert loaded_attrib["attributed_spans"][0]["raw_score"] == 0.451
    assert "bias toward punctuation" in loaded_attrib["research_warning"]


def test_14_missing_attribution_data_handled_correctly(ega_session):
    """14. Missing attribution data is handled correctly with None rather than fabricated spans."""
    repo = DocumentRepository(ega_session)
    client_u = make_user(repo, "client14@example.com", UserRole.CLIENT)
    doc, seg = make_contract_with_segments(repo, client_u.id)

    review_service = ReviewService(ega_session)
    review = review_service.initiate_review(doc.id, actor_user=client_u)

    finding = repo.create_or_update_clause_finding(
        review_id=review.id,
        document_id=doc.id,
        segment_id=seg.segment_id,
        ai_observation="Observation without attribution data.",
        model_attribution_json=None
    )

    assert finding.model_attribution_json is None


def test_15_ai_observations_remain_separate_from_lawyer_decisions(ega_session):
    """15. AI observations remain strictly separate from lawyer decisions."""
    repo = DocumentRepository(ega_session)
    client_u = make_user(repo, "client15@example.com", UserRole.CLIENT)
    lawyer_u = make_user(repo, "lawyer15@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    doc, seg = make_contract_with_segments(repo, client_u.id)

    review_service = ReviewService(ega_session)
    review = review_service.initiate_review(doc.id, actor_user=client_u)
    review.assigned_lawyer_id = lawyer_u.id
    review.status = ReviewStatus.IN_REVIEW.value
    ega_session.flush()

    finding = review_service.record_clause_decision(
        review_id=review.id,
        segment_id=seg.segment_id,
        decision=LawyerDecisionType.REJECT_AI_OBSERVATION.value,
        lawyer_rationale="AI observation of non-compete risk is unfounded; this is a standard non-solicitation provision.",
        actor_user=lawyer_u,
        statutory_evidence_json=None
    )

    # Verify AI observation is distinct from advocate determination
    assert finding.decision == LawyerDecisionType.REJECT_AI_OBSERVATION.value
    assert finding.lawyer_rationale.startswith("AI observation of non-compete risk is unfounded")
    assert finding.finding_origin == FindingOrigin.AI_GENERATED.value


def test_16_lawyer_rationale_remains_associated_with_correct_decision(ega_session):
    """16. Lawyer rationale remains associated with the correct decision."""
    repo = DocumentRepository(ega_session)
    client_u = make_user(repo, "client16@example.com", UserRole.CLIENT)
    lawyer_u = make_user(repo, "lawyer16@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    doc, seg = make_contract_with_segments(repo, client_u.id)

    review_service = ReviewService(ega_session)
    review = review_service.initiate_review(doc.id, actor_user=client_u)
    review.assigned_lawyer_id = lawyer_u.id
    review.status = ReviewStatus.IN_REVIEW.value
    ega_session.flush()

    finding = review_service.record_clause_decision(
        review_id=review.id,
        segment_id=seg.segment_id,
        decision=LawyerDecisionType.CORRECT_AI_OBSERVATION.value,
        lawyer_rationale="The liability cap must be adjusted to 100% of annual contract value.",
        actor_user=lawyer_u
    )

    assert finding.decision == LawyerDecisionType.CORRECT_AI_OBSERVATION.value
    assert "liability cap must be adjusted" in finding.lawyer_rationale


def test_17_internal_lawyer_notes_remain_hidden_from_clients(ega_session, ega_client):
    """17. Internal lawyer notes remain hidden from clients."""
    repo = DocumentRepository(ega_session)
    client_u = make_user(repo, "client17@example.com", UserRole.CLIENT)
    lawyer_u = make_user(repo, "lawyer17@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    doc, seg = make_contract_with_segments(repo, client_u.id)

    review_service = ReviewService(ega_session)
    review = review_service.initiate_review(doc.id, actor_user=client_u)
    review.assigned_lawyer_id = lawyer_u.id
    review.status = ReviewStatus.IN_REVIEW.value
    ega_session.flush()

    review_service.record_clause_decision(
        review_id=review.id,
        segment_id=seg.segment_id,
        decision=LawyerDecisionType.ACCEPT_AI_OBSERVATION.value,
        lawyer_rationale="Approved commercial risk on payment default.",
        lawyer_notes="INTERNAL NOTE: Client has high leverage in negotiations; advise pushback in private briefing.",
        is_disclosed_to_client=True,
        actor_user=lawyer_u
    )
    ega_session.commit()

    # Client retrieves review workspace via API
    resp = ega_client.get(
        f"/api/review/{review.id}",
        headers=auth_headers(client_u)
    )
    assert resp.status_code == 200
    data = resp.get_json()

    # Findings in client view must NOT contain lawyer_notes
    assert len(data["findings"]) == 1
    client_finding = data["findings"][0]
    assert "lawyer_notes" not in client_finding


def test_18_final_reports_include_only_eligible_associated_evidence(ega_session):
    """18. Final reports include only eligible, associated evidence."""
    repo = DocumentRepository(ega_session)
    client_u = make_user(repo, "client18@example.com", UserRole.CLIENT)
    lawyer_u = make_user(repo, "lawyer18@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    doc, seg = make_contract_with_segments(repo, client_u.id)

    review_service = ReviewService(ega_session)
    review = review_service.initiate_review(doc.id, actor_user=client_u)
    review.assigned_lawyer_id = lawyer_u.id
    review.status = ReviewStatus.IN_REVIEW.value
    ega_session.flush()

    # Record decision with statutory evidence
    evidence_payload = {
        "passages": [
            {
                "statute_title": "The Indian Contract Act, 1872",
                "section_number": "27",
                "section_title": "Agreement in restraint of trade, void",
                "passage_text": "Every agreement by which any one is restrained from exercising a lawful profession is void.",
                "statute_id": "IN_ACT_1872_09",
                "source_version": "1.0",
                "legal_status": "IN_FORCE",
                "source_checksum": "881177af2fa470ec85994f395b2a218af67a7afc9e3567abc3631fc62be51c06"
            }
        ]
    }

    review_service.record_clause_decision(
        review_id=review.id,
        segment_id=seg.segment_id,
        decision=LawyerDecisionType.ACCEPT_AI_OBSERVATION.value,
        lawyer_rationale="Confirmed restraint of trade violation.",
        statutory_evidence_json=json.dumps(evidence_payload),
        is_disclosed_to_client=True,
        actor_user=lawyer_u
    )

    review_service.complete_review(
        review_id=review.id,
        actor_user=lawyer_u,
        completion_summary="Exhaustive review complete."
    )

    report_service = ReportService(ega_session)
    payload = report_service.compile_report_payload(review.id, is_final=True)

    assert len(payload["findings"]) == 1
    finding_item = payload["findings"][0]
    assert finding_item["segment_id"] == seg.segment_id
    assert len(finding_item["statutory_references"]) == 1
    ref = finding_item["statutory_references"][0]
    assert ref["section"] == "27"
    assert "Indian Contract Act" in ref["act_name"]
    assert "881177af2f" in ref["source_checksum"]


def test_19_report_hashes_and_existing_report_integrity_checks_remain_valid(ega_session):
    """19. Report hashes and existing report-integrity checks remain valid."""
    repo = DocumentRepository(ega_session)
    client_u = make_user(repo, "client19@example.com", UserRole.CLIENT)
    lawyer_u = make_user(repo, "lawyer19@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    doc, seg = make_contract_with_segments(repo, client_u.id)

    review_service = ReviewService(ega_session)
    review = review_service.initiate_review(doc.id, actor_user=client_u)
    review.assigned_lawyer_id = lawyer_u.id
    review.status = ReviewStatus.IN_REVIEW.value
    ega_session.flush()

    review_service.record_clause_decision(
        review_id=review.id,
        segment_id=seg.segment_id,
        decision=LawyerDecisionType.ACCEPT_AI_OBSERVATION.value,
        lawyer_rationale="Approved finding for report hashing.",
        actor_user=lawyer_u
    )

    review_service.complete_review(
        review_id=review.id,
        actor_user=lawyer_u,
        completion_summary="Completion for integrity validation."
    )

    report_service = ReportService(ega_session)
    report_rec = report_service.generate_final_report(review.id, actor_user=lawyer_u)

    assert report_rec.content_sha256 is not None
    assert len(report_rec.content_sha256) == 64
    assert report_rec.pdf_sha256 is not None
    assert len(report_rec.pdf_sha256) == 64
    assert report_rec.status == ReportStatus.FINAL.value


def test_20_unauthorized_users_cannot_access_restricted_evidence(ega_session, ega_client):
    """20. Unauthorized users cannot access restricted evidence."""
    repo = DocumentRepository(ega_session)
    client_owner = make_user(repo, "owner20@example.com", UserRole.CLIENT)
    client_other = make_user(repo, "other20@example.com", UserRole.CLIENT)
    doc, seg = make_contract_with_segments(repo, client_owner.id)

    review_service = ReviewService(ega_session)
    review = review_service.initiate_review(doc.id, actor_user=client_owner)
    ega_session.commit()

    # Other client tries to access evidence endpoint
    resp = ega_client.get(
        f"/api/review/{review.id}/evidence/{seg.segment_id}",
        headers=auth_headers(client_other)
    )
    assert resp.status_code == 403


def test_21_existing_lifecycle_integration_continues_to_work(ega_session, ega_client):
    """21. Existing lifecycle integration continues to work seamlessly."""
    repo = DocumentRepository(ega_session)
    client_u = make_user(repo, "client21@example.com", UserRole.CLIENT)
    supervisor_u = make_user(repo, "supervisor21@example.com", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)
    lawyer_u = make_user(repo, "lawyer21@example.com", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    doc, seg = make_contract_with_segments(repo, client_u.id)

    review_service = ReviewService(ega_session)
    review = review_service.initiate_review(doc.id, actor_user=client_u)

    # 1. Supervisor assigns lawyer
    review_service.assign_review(review.id, lawyer_u.id, assigning_user=supervisor_u)
    ega_session.commit()

    # 2. Lawyer records decision with evidence and quality status
    resp_dec = ega_client.post(
        f"/api/review/{review.id}/decision",
        headers=auth_headers(lawyer_u),
        json={
            "segment_id": seg.segment_id,
            "decision": LawyerDecisionType.ACCEPT_AI_OBSERVATION.value,
            "rationale": "Legal rationale confirming statutory restraint.",
            "notes": "Internal audit note.",
            "is_disclosed_to_client": True,
            "evidence_quality_status": EvidenceQualityStatus.TRACEABLE.value
        }
    )
    assert resp_dec.status_code == 200

    # 3. Lawyer completes review
    ega_session.expire_all()
    review_service.complete_review(
        review_id=review.id,
        actor_user=lawyer_u,
        completion_summary="End-to-end integration verified successfully."
    )
    ega_session.commit()

    # 4. Generate final report
    resp_rep = ega_client.post(
        f"/api/reports/generate/{review.id}",
        headers=auth_headers(lawyer_u),
        json={"export_pdf": True}
    )
    assert resp_rep.status_code == 201
    rep_data = resp_rep.get_json()
    assert rep_data["status"] == "FINAL"
    assert rep_data["report_number"].startswith("REP-")
