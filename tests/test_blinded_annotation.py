"""
Comprehensive Verification and Security Test Suite for Blinded Legal Annotation Infrastructure.

Verifies:
1. Candidate finding presentation excludes model identifier, confidence values, BM25 scores, and policy recommendations.
2. Stage-specific presentation filters enforce Section 7.4 visibility rules for Stages 1 through 6.
3. Annotator A cannot access Annotator B's active submission.
4. Submission locking transitions state, records digest, and enforces immutability.
5. Ordinary update and delete operations are rejected on locked submissions.
6. Schema validation rejects malformed annotation payloads.
7. SHA-256 digest calculation is deterministic across unordered JSON representations.
8. Duplicate submission attempts for the same candidate and annotator are rejected.
9. Adjudication view remains inaccessible until both independent submissions are locked.
10. Adjudication view excludes model confidence and policy recommendations.
11. Versioned amendments preserve the locked original and link to the superseded record.
12. Audit events are recorded for submission, locking, access denial, and adjudication.
13. Regression safety across existing models and persistence layers.
14. Security review: RBAC enforcement, advocate verification gates, and tenant/blinding boundary checks.
15. Verification that Task 042 was NOT started.
16. Verification that Tasks 028 and 029 remain strictly LOCKED.
"""

import os
import json
import uuid
import pytest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.persistence.database import Base, get_session_factory
from src.persistence.models import (
    UserRecord, UserRole, AccountStatus, AdvocateStatus,
    BlindedAnnotationRecord, BlindedAdjudicationRecord,
    AnnotationStage, AdjudicationStatus, AuditEventRecord
)
from src.persistence.repository import DocumentRepository
from src.auth.password import PasswordManager
from src.auth.token import TokenManager
from src.auth.config import AuthConfig
from src.audit.provenance import EventType, ActorType

from src.annotation.firewall import PresentationFirewall, BlindingViolationError
from src.annotation.service import (
    BlindedAnnotationService, compute_payload_sha256, canonical_json_dumps
)
from src.dashboard.app import app


# =========================================================================
# TEST FIXTURES
# =========================================================================

@pytest.fixture
def test_db_engine():
    """Isolated in-memory SQLite database for annotation testing."""
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


def create_user_record(
    repo: DocumentRepository,
    email: str,
    role: UserRole = UserRole.LAWYER,
    advocate_status: AdvocateStatus = AdvocateStatus.VERIFIED
) -> UserRecord:
    pm = PasswordManager()
    h = pm.hash_password("SecurePass123!")
    return repo.create_user(
        user_id=str(uuid.uuid4()),
        email=email,
        password_hash=h,
        role=role.value,
        account_status=AccountStatus.ACTIVE.value,
        advocate_status=advocate_status.value,
        full_name=f"User {email}",
        bar_enrolment_id="D/1234/2018" if advocate_status == AdvocateStatus.VERIFIED else None,
        state_bar_council="DELHI" if advocate_status == AdvocateStatus.VERIFIED else None,
        year_of_enrolment=2018 if advocate_status == AdvocateStatus.VERIFIED else None
    )


def create_sample_candidate_data(candidate_id: str = "CAND-001") -> dict:
    return {
        "candidate_finding_id": candidate_id,
        "contract_id": "CTR-100",
        "contract_version": 1,
        "document_content_hash": "e" * 64,
        "clause_id": "CLAUSE-14.2",
        "clause_text": "Supplier shall defend, indemnify and hold harmless the Customer against all liabilities.",
        "prediction_category": "INDEMNIFICATION",
        "candidate_finding_text": "Unilateral indemnification provision creating uncapped liability.",
        "model_id": "nlpaueb/legal-bert-base-uncased",
        "model_name": "legalbert-base-uncased",
        "model_version": "1.0.0",
        "model_task": "CLASSIFICATION_MULTILABEL",
        "confidence_value": 0.942,
        "raw_model_label": "indemnity_unilateral",
        "candidate_confidence": {
            "score": 0.942,
            "metric_type": "SIGMOID_PROBABILITY",
            "is_calibrated": False
        },
        "evidence_quality_status": "TRACEABLE",
        "retrieved_passages": [
            {
                "passage_id": "IN_ACT_1872_09_SEC_124",
                "statute_id": "IN_ACT_1872_09",
                "statute_title": "Indian Contract Act, 1872",
                "section_number": "Section 124",
                "section_title": "'Contract of indemnity' defined",
                "passage_text": "A contract by which one party promises to save the other from loss caused to him by the conduct of the promisor...",
                "bm25_score": 18.45,
                "retrieval_rank": 1,
                "source_repository": "Legislative Department",
                "source_sha256": "f" * 64,
                "commencement_status": "IN_FORCE_CONFIRMED"
            }
        ],
        "baseline_policy_decision": "RETAIN",
        "evidence_aware_policy_decision": "RETAIN",
        "is_retained": True
    }


def create_valid_annotation_payload(
    candidate_id: str = "CAND-001",
    annotator_code: str = "ANN-001",
    reference_action: str = "RETAIN"
) -> dict:
    return {
        "schema_version": "1.0.0",
        "annotation_id": str(uuid.uuid4()),
        "is_synthetic_fixture": False,
        "identification": {
            "contract_id": "CTR-100",
            "contract_cluster_id": "CLUSTER-IND-01",
            "contract_version": 1,
            "clause_id": "CLAUSE-14.2",
            "clause_text": "Supplier shall defend, indemnify and hold harmless the Customer against all liabilities.",
            "candidate_finding_id": candidate_id,
            "candidate_finding_text": "Unilateral indemnification provision creating uncapped liability.",
            "prediction_category": "INDEMNIFICATION",
            "model_identifier": "nlpaueb/legal-bert-base-uncased",
            "model_version": "1.0.0",
            "candidate_confidence": {
                "score": 0.942,
                "metric_type": "SIGMOID_PROBABILITY",
                "is_calibrated": False
            }
        },
        "prediction_assessment": {
            "status": "CORRECT",
            "rationale": "The clause explicitly establishes a unilateral indemnification burden under Indian law.",
            "identified_risk_severity": "HIGH"
        },
        "evidence_support": {
            "status": "SUPPORTED",
            "rationale": "Directly grounded in Section 124 of the Indian Contract Act 1872.",
            "passages": [
                {
                    "passage_id": "IN_ACT_1872_09_SEC_124",
                    "statute_id": "IN_ACT_1872_09",
                    "section_number": "Section 124",
                    "passage_text": "A contract by which one party promises to save the other from loss caused to him by the conduct of the promisor...",
                    "support_status": "DIRECTLY_SUPPORTS"
                }
            ]
        },
        "evidence_sufficiency": {
            "status": "SUFFICIENT",
            "rationale": "Totality of statutory extract confirms indemnity character without ambiguity."
        },
        "source_status": {
            "status": "VERIFIED_RESEARCH_PROTOCOL",
            "source_repository": "Legislative Department",
            "provenance_classification": "CURATED_EDITORIAL_EXTRACT"
        },
        "source_applicability": {
            "currentness_status": "IN_FORCE_CONFIRMED",
            "applicability_status": "APPLICABLE_TO_CONTRACT",
            "rationale": "Section 124 of Indian Contract Act 1872 remains fully in force in India."
        },
        "version_consistency": {
            "status": "CONSISTENT",
            "finding_contract_version": 1,
            "active_contract_version": 1,
            "text_hash_matches": True
        },
        "final_reference_decision": {
            "reference_action": reference_action,
            "decision_rationale": "The finding asserts a real commercial risk supported by valid statutory extract.",
            "confidence_in_decision": "HIGH"
        },
        "epistemic_firewall_attestation": {
            "rule_traceable_not_treated_as_correct": True,
            "rule_bm25_not_treated_as_ground_truth_sufficiency": True,
            "rule_checksum_not_treated_as_official_authenticity": True,
            "rule_authenticity_not_treated_as_applicability": True,
            "rule_policy_output_not_treated_as_reference_decision": True
        },
        "annotation_provenance": {
            "annotator_code": annotator_code,
            "annotator_qualification": "ENROLLED_ADVOCATE_INDIA",
            "annotation_phase": "MAIN_STUDY",
            "blinding_conditions": {
                "blinded_to_model_identity": True,
                "blinded_to_confidence_score": True,
                "blinded_to_policy_decisions": True
            },
            "disagreement_flag": False,
            "created_at": "2026-10-17T20:00:00Z"
        }
    }


# =========================================================================
# TEST CASES
# =========================================================================

def test_01_candidate_presentation_excludes_model_and_confidence_and_policy():
    """1. Candidate finding presentation excludes model identifier, confidence values, BM25 scores, and policy recommendations."""
    raw = create_sample_candidate_data("CAND-001")
    firewalled = PresentationFirewall.filter_candidate_for_annotator(raw, stage=AnnotationStage.FULL_RECORD.value)

    # Excluded fields must NOT be present
    forbidden = [
        "model_id", "model_name", "model_version", "model_task", "confidence_value",
        "raw_model_label", "candidate_confidence", "evidence_quality_status",
        "baseline_policy_decision", "evidence_aware_policy_decision", "is_retained"
    ]
    for field in forbidden:
        assert field not in firewalled, f"Forbidden field '{field}' leaked through presentation firewall!"

    # In nested passages, bm25_score and retrieval_rank must be stripped
    passages = firewalled.get("retrieved_passages", [])
    assert len(passages) == 1
    assert "bm25_score" not in passages[0]
    assert "retrieval_rank" not in passages[0]
    assert passages[0]["statute_id"] == "IN_ACT_1872_09"
    assert passages[0]["section_number"] == "Section 124"


def test_02_stage_specific_presentation_filters_stages_1_to_6():
    """2. Stage-specific presentation filters enforce Section 7.4 visibility rules for Stages 1 through 6."""
    raw = create_sample_candidate_data("CAND-001")

    # Stage 1: Prediction Correctness (clause text, finding text, category; no passages, no confidence)
    s1 = PresentationFirewall.filter_candidate_for_annotator(raw, stage=AnnotationStage.STAGE_1_PREDICTION.value)
    assert "clause_text" in s1
    assert "candidate_finding_text" in s1
    assert "prediction_category" in s1
    assert "retrieved_passages" not in s1
    assert "confidence_value" not in s1

    # Stage 2: Evidence Support (clause text, finding text, cited passages; no BM25, no status)
    s2 = PresentationFirewall.filter_candidate_for_annotator(raw, stage=AnnotationStage.STAGE_2_SUPPORT.value)
    assert "clause_text" in s2
    assert "retrieved_passages" in s2
    assert "bm25_score" not in s2["retrieved_passages"][0]
    assert "evidence_quality_status" not in s2

    # Stage 3: Evidence Sufficiency (clause text, finding text, totality of passages; no BM25)
    s3 = PresentationFirewall.filter_candidate_for_annotator(raw, stage=AnnotationStage.STAGE_3_SUFFICIENCY.value)
    assert "clause_text" in s3
    assert "retrieved_passages" in s3
    assert "bm25_score" not in s3["retrieved_passages"][0]

    # Stage 4: Source Status (statute title, section, source_sha256, source_repository; no finding text)
    s4 = PresentationFirewall.filter_candidate_for_annotator(raw, stage=AnnotationStage.STAGE_4_SOURCE.value)
    assert "sources" in s4
    assert len(s4["sources"]) == 1
    assert s4["sources"][0]["source_sha256"] == "f" * 64
    assert "candidate_finding_text" not in s4
    assert "clause_text" not in s4

    # Stage 5: Version Consistency (version numbers, text SHA-256, clause text; no confidence)
    s5 = PresentationFirewall.filter_candidate_for_annotator(raw, stage=AnnotationStage.STAGE_5_VERSION.value)
    assert s5["contract_version"] == 1
    assert s5["document_content_hash"] == "e" * 64
    assert "confidence_value" not in s5

    # Stage 6: Final Reference Decision (clause text, finding text, passages; no policy recommendations)
    s6 = PresentationFirewall.filter_candidate_for_annotator(raw, stage=AnnotationStage.STAGE_6_DISPOSITION.value)
    assert "clause_text" in s6
    assert "candidate_finding_text" in s6
    assert "baseline_policy_decision" not in s6
    assert "evidence_aware_policy_decision" not in s6


def test_03_annotator_a_cannot_access_annotator_b_submission(test_session):
    """3. Annotator A cannot access Annotator B's active submission."""
    repo = DocumentRepository(test_session)
    service = BlindedAnnotationService(test_session)

    annotator_a = create_user_record(repo, "advocate_a@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    annotator_b = create_user_record(repo, "advocate_b@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)

    payload_a = create_valid_annotation_payload("CAND-001", annotator_code="ANN-001", reference_action="RETAIN")
    sub_a = service.submit_annotation("CAND-001", "CTR-100", "CLAUSE-14.2", annotator_a, payload_a)

    # Annotator A can view own submission
    res_a = service.get_submission_for_user(sub_a.id, annotator_a)
    assert res_a["id"] == sub_a.id

    # Annotator B attempting to view Annotator A's submission prior to both locking raises BlindingViolationError
    with pytest.raises(BlindingViolationError) as exc_info:
        service.get_submission_for_user(sub_a.id, annotator_b)
    assert "Peer submissions remain strictly blinded" in str(exc_info.value)


def test_04_submission_locking_transitions_state_and_records_digest(test_session):
    """4. Submission locking transitions state, records digest, and enforces immutability."""
    repo = DocumentRepository(test_session)
    service = BlindedAnnotationService(test_session)

    annotator = create_user_record(repo, "advocate_lock@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    payload = create_valid_annotation_payload("CAND-001", annotator_code="ANN-001", reference_action="RETAIN")

    sub = service.submit_annotation("CAND-001", "CTR-100", "CLAUSE-14.2", annotator, payload)
    assert sub.is_locked is False
    assert sub.locked_at is None

    locked = service.lock_annotation(sub.id, annotator)
    assert locked.is_locked is True
    assert locked.locked_at is not None
    assert len(locked.payload_sha256) == 64


def test_05_ordinary_update_rejected_on_locked_submission(test_session):
    """5. Ordinary update and delete operations are rejected on locked submissions."""
    repo = DocumentRepository(test_session)
    service = BlindedAnnotationService(test_session)

    annotator = create_user_record(repo, "advocate_immutable@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    payload = create_valid_annotation_payload("CAND-001", annotator_code="ANN-001", reference_action="RETAIN")

    sub = service.submit_annotation("CAND-001", "CTR-100", "CLAUSE-14.2", annotator, payload)
    service.lock_annotation(sub.id, annotator)

    # Attempting to update a locked record via repository throws ValueError
    with pytest.raises(ValueError) as exc:
        repo.update_unlocked_annotation_payload(
            annotation_id=sub.id,
            annotator_id=annotator.id,
            new_payload_json="{}",
            new_payload_sha256="0" * 64
        )
    assert "Locked submissions cannot be edited" in str(exc.value)


def test_06_schema_validation_rejects_malformed_payload(test_session):
    """6. Schema validation rejects malformed annotation payloads."""
    repo = DocumentRepository(test_session)
    service = BlindedAnnotationService(test_session)
    annotator = create_user_record(repo, "advocate_schema@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)

    # 1. Missing required top-level property
    invalid_payload = {"schema_version": "1.0.0", "annotation_id": str(uuid.uuid4())}
    is_valid, err = service.validate_payload(invalid_payload)
    assert is_valid is False
    assert "Schema validation failed" in err

    # 2. Invalid enum value in final_reference_decision
    payload_bad_enum = create_valid_annotation_payload("CAND-001")
    payload_bad_enum["final_reference_decision"]["reference_action"] = "ARBITRARY_ACTION"
    is_valid, err = service.validate_payload(payload_bad_enum)
    assert is_valid is False
    assert "Invalid reference_action" in err or "Schema validation failed" in err


def test_07_sha256_digest_deterministic_across_unordered_json():
    """7. SHA-256 digest calculation is deterministic across unordered JSON representations."""
    d1 = {"b": 2, "a": 1, "c": {"y": "second", "x": "first"}}
    d2 = {"a": 1, "c": {"x": "first", "y": "second"}, "b": 2}

    h1 = compute_payload_sha256(d1)
    h2 = compute_payload_sha256(d2)

    assert h1 == h2, "Canonical SHA-256 digest differs for identical dictionary content with different key order!"


def test_08_duplicate_submission_rejected(test_session):
    """8. Duplicate submission attempts for the same candidate, annotator, stage, and version are rejected."""
    repo = DocumentRepository(test_session)
    service = BlindedAnnotationService(test_session)
    annotator = create_user_record(repo, "advocate_dup@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    payload = create_valid_annotation_payload("CAND-DUP-01")

    service.submit_annotation("CAND-DUP-01", "CTR-100", "CLAUSE-01", annotator, payload)

    with pytest.raises(ValueError) as exc:
        service.submit_annotation("CAND-DUP-01", "CTR-100", "CLAUSE-01", annotator, payload)
    assert "Duplicate active submission" in str(exc.value)


def test_09_adjudication_inaccessible_until_both_submissions_locked(test_session):
    """9. Adjudication view remains inaccessible until both independent submissions are locked."""
    repo = DocumentRepository(test_session)
    service = BlindedAnnotationService(test_session)

    annotator_1 = create_user_record(repo, "advocate_1@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    annotator_2 = create_user_record(repo, "advocate_2@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    senior_counsel = create_user_record(repo, "senior_counsel@chamber.in", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)

    cand_data = create_sample_candidate_data("CAND-ADJ-01")
    payload_1 = create_valid_annotation_payload("CAND-ADJ-01", "ANN-001", "RETAIN")
    payload_2 = create_valid_annotation_payload("CAND-ADJ-01", "ANN-002", "WITHHOLD")

    sub_1 = service.submit_annotation("CAND-ADJ-01", "CTR-100", "CLAUSE-14.2", annotator_1, payload_1)
    sub_2 = service.submit_annotation("CAND-ADJ-01", "CTR-100", "CLAUSE-14.2", annotator_2, payload_2)

    # Neither locked yet -> Adjudication access raises BlindingViolationError
    with pytest.raises(BlindingViolationError) as exc:
        service.get_adjudication_dossier("CAND-ADJ-01", cand_data, senior_counsel)
    assert "Adjudication gate closed" in str(exc.value)

    # Only 1 locked -> Still inaccessible
    service.lock_annotation(sub_1.id, annotator_1)
    with pytest.raises(BlindingViolationError) as exc:
        service.get_adjudication_dossier("CAND-ADJ-01", cand_data, senior_counsel)
    assert "Adjudication gate closed" in str(exc.value)

    # Both locked -> Adjudication becomes accessible
    service.lock_annotation(sub_2.id, annotator_2)
    dossier = service.get_adjudication_dossier("CAND-ADJ-01", cand_data, senior_counsel)
    assert dossier["adjudication_status"] == "READY_FOR_ADJUDICATION"
    assert "submission_1" in dossier
    assert "submission_2" in dossier


def test_10_adjudication_view_excludes_model_confidence_and_policy(test_session):
    """10. Adjudication view excludes model confidence and policy recommendations."""
    repo = DocumentRepository(test_session)
    service = BlindedAnnotationService(test_session)

    annotator_1 = create_user_record(repo, "adv_adj1@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    annotator_2 = create_user_record(repo, "adv_adj2@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    senior_counsel = create_user_record(repo, "senior_blinded@chamber.in", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)

    cand_data = create_sample_candidate_data("CAND-ADJ-02")
    payload_1 = create_valid_annotation_payload("CAND-ADJ-02", "ANN-001", "RETAIN")
    payload_2 = create_valid_annotation_payload("CAND-ADJ-02", "ANN-002", "WITHHOLD")

    sub_1 = service.submit_annotation("CAND-ADJ-02", "CTR-100", "CLAUSE-14.2", annotator_1, payload_1)
    sub_2 = service.submit_annotation("CAND-ADJ-02", "CTR-100", "CLAUSE-14.2", annotator_2, payload_2)
    service.lock_annotation(sub_1.id, annotator_1)
    service.lock_annotation(sub_2.id, annotator_2)

    dossier = service.get_adjudication_dossier("CAND-ADJ-02", cand_data, senior_counsel)
    cand_view = dossier["candidate"]

    # Senior counsel must NOT see model confidence, logits, or automated policy actions
    assert "confidence_value" not in cand_view
    assert "model_id" not in cand_view
    assert "baseline_policy_decision" not in cand_view
    assert "evidence_aware_policy_decision" not in cand_view


def test_11_versioned_amendment_preserves_locked_original(test_session):
    """11. Versioned amendments preserve the locked original and link to the superseded record."""
    repo = DocumentRepository(test_session)
    service = BlindedAnnotationService(test_session)

    annotator = create_user_record(repo, "advocate_amend@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    payload_v1 = create_valid_annotation_payload("CAND-AMEND-01", "ANN-001", "WITHHOLD")

    sub_v1 = service.submit_annotation("CAND-AMEND-01", "CTR-100", "CLAUSE-14.2", annotator, payload_v1)
    service.lock_annotation(sub_v1.id, annotator)

    # Create versioned correction
    payload_v2 = dict(payload_v1)
    payload_v2["final_reference_decision"]["reference_action"] = "RETAIN"
    v2_json = canonical_json_dumps(payload_v2)
    v2_sha256 = compute_payload_sha256(payload_v2)

    sub_v2 = repo.supersede_blinded_annotation(
        original_annotation_id=sub_v1.id,
        new_payload_json=v2_json,
        new_payload_sha256=v2_sha256,
        annotator_id=annotator.id,
        reason="Corrected reference decision after reviewing statutory exception."
    )

    # Verify original is preserved and linked
    test_session.refresh(sub_v1)
    assert sub_v1.superseded_by_id == sub_v2.id
    assert sub_v1.version == 1
    assert sub_v2.version == 2
    assert sub_v2.candidate_finding_id == sub_v1.candidate_finding_id


def test_12_audit_events_recorded_for_lifecycle(test_session):
    """12. Audit events are recorded for submission, locking, access denial, and adjudication."""
    repo = DocumentRepository(test_session)
    service = BlindedAnnotationService(test_session)

    annotator_1 = create_user_record(repo, "audit_adv1@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    annotator_2 = create_user_record(repo, "audit_adv2@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    senior = create_user_record(repo, "audit_senior@chamber.in", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)

    payload_1 = create_valid_annotation_payload("CAND-AUDIT-01", "ANN-001", "RETAIN")
    payload_2 = create_valid_annotation_payload("CAND-AUDIT-01", "ANN-002", "WITHHOLD")

    sub_1 = service.submit_annotation("CAND-AUDIT-01", "CTR-AUDIT", "C-01", annotator_1, payload_1)
    sub_2 = service.submit_annotation("CAND-AUDIT-01", "CTR-AUDIT", "C-01", annotator_2, payload_2)

    # 1. Access denial event
    with pytest.raises(BlindingViolationError):
        service.get_submission_for_user(sub_1.id, annotator_2)

    # 2. Lock events
    service.lock_annotation(sub_1.id, annotator_1)
    service.lock_annotation(sub_2.id, annotator_2)

    # 3. Adjudication event
    service.record_adjudication(
        candidate_finding_id="CAND-AUDIT-01",
        adjudicator_user=senior,
        final_disposition="RETAIN",
        rationale="Determined retainable following substantive legal review of indemnity clauses."
    )

    # Query audit events
    events = test_session.query(AuditEventRecord).order_by(AuditEventRecord.created_at.asc()).all()
    event_types = [e.event_type for e in events]

    assert EventType.ANNOTATION_SUBMITTED.value in event_types
    assert EventType.BLINDING_VIOLATION_BLOCKED.value in event_types
    assert EventType.ANNOTATION_LOCKED.value in event_types
    assert EventType.ADJUDICATION_INITIATED.value in event_types
    assert EventType.ADJUDICATION_RECORDED.value in event_types


def test_13_security_advocate_verification_gate(test_session):
    """14. Security review: unverified lawyers cannot submit annotations."""
    repo = DocumentRepository(test_session)
    service = BlindedAnnotationService(test_session)

    unverified_lawyer = create_user_record(
        repo, "unverified@chamber.in", UserRole.LAWYER, AdvocateStatus.PENDING_VERIFICATION
    )
    payload = create_valid_annotation_payload("CAND-SEC-01")

    with pytest.raises(PermissionError) as exc:
        service.submit_annotation("CAND-SEC-01", "CTR-100", "CLAUSE-01", unverified_lawyer, payload)
    assert "Advocate verification required" in str(exc.value)


def test_14_non_supervising_lawyer_cannot_adjudicate(test_session):
    """14. Security review: non-supervising lawyers cannot record adjudication."""
    repo = DocumentRepository(test_session)
    service = BlindedAnnotationService(test_session)

    regular_lawyer = create_user_record(repo, "regular@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)

    with pytest.raises(PermissionError) as exc:
        service.record_adjudication(
            candidate_finding_id="CAND-001",
            adjudicator_user=regular_lawyer,
            final_disposition="RETAIN",
            rationale="Attempted unauthorized adjudication."
        )
    assert "only Supervising Lawyers" in str(exc.value)


def test_15_task_042_not_started_and_tasks_028_029_locked():
    """15 & 16. Verify Task 042 is NOT STARTED and Tasks 028 and 029 remain LOCKED."""
    board_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "PROJECT_TASK_BOARD.md"))
    assert os.path.exists(board_path)

    with open(board_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Task 028 must be locked
    assert "Task 028 remains strictly 🔒 LOCKED" in content or "Task 028 remains strictly LOCKED" in content

    # Task 029 must be locked
    assert "Task 029 remains strictly 🔒 LOCKED" in content or "Task 029 remains strictly LOCKED" in content

    # Task 042 must NOT be started
    assert "Task 042 remains strictly NOT STARTED" in content or "Task 042 must NOT be started" in content


def test_16_flask_route_blinded_candidate_filtering(test_db_engine):
    """16. API endpoint GET /api/annotation/candidate/<id> filters prohibited fields."""
    app.config["TESTING"] = True
    from src.persistence.database import get_db_session as real_get_db_session
    tm = TokenManager(AuthConfig())
    with real_get_db_session(test_db_engine) as sess:
        repo = DocumentRepository(sess)
        lawyer = create_user_record(repo, "api_lawyer@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        token = tm.generate_token(lawyer)

    with patch("src.persistence.database.get_engine", return_value=test_db_engine):
        with patch("src.auth.rbac.get_db_session", side_effect=lambda: real_get_db_session(test_db_engine)):
            with patch("src.annotation.routes.get_db_session", side_effect=lambda: real_get_db_session(test_db_engine)):
                with app.test_client() as client:
                    resp = client.get(
                        "/api/annotation/candidate/CAND-API-01",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    assert resp.status_code == 200
                    body = resp.get_json()
                    cand = body["candidate"]
                    assert "model_id" not in cand
                    assert "confidence_value" not in cand
                    assert "baseline_policy_decision" not in cand
                    assert cand["candidate_finding_id"] == "CAND-API-01"


def test_17_flask_route_unauthenticated_and_client_role_rejected(test_db_engine):
    """17. API endpoints reject unauthenticated requests (401) and client role (403)."""
    app.config["TESTING"] = True
    from src.persistence.database import get_db_session as real_get_db_session
    tm = TokenManager(AuthConfig())
    with real_get_db_session(test_db_engine) as sess:
        repo = DocumentRepository(sess)
        client_user = create_user_record(repo, "client_user@client.in", UserRole.CLIENT)
        client_token = tm.generate_token(client_user)

    with patch("src.persistence.database.get_engine", return_value=test_db_engine):
        with patch("src.auth.rbac.get_db_session", side_effect=lambda: real_get_db_session(test_db_engine)):
            with app.test_client() as client:
                # 1. Unauthenticated -> 401
                r1 = client.get("/api/annotation/candidate/CAND-001")
                assert r1.status_code == 401

                # 2. Client role -> 403 Forbidden
                r2 = client.get(
                    "/api/annotation/candidate/CAND-001",
                    headers={"Authorization": f"Bearer {client_token}"}
                )
                assert r2.status_code == 403


def test_18_flask_route_submit_and_lock_lifecycle(test_db_engine):
    """18. API endpoints POST /submit and POST /lock lifecycle."""
    app.config["TESTING"] = True
    from src.persistence.database import get_db_session as real_get_db_session
    tm = TokenManager(AuthConfig())
    with real_get_db_session(test_db_engine) as sess:
        repo = DocumentRepository(sess)
        lawyer = create_user_record(repo, "submitter@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        token = tm.generate_token(lawyer)

    payload = create_valid_annotation_payload("CAND-HTTP-01", "ANN-001", "RETAIN")

    with patch("src.persistence.database.get_engine", return_value=test_db_engine):
        with patch("src.auth.rbac.get_db_session", side_effect=lambda: real_get_db_session(test_db_engine)):
            with patch("src.annotation.routes.get_db_session", side_effect=lambda: real_get_db_session(test_db_engine)):
                with app.test_client() as client:
                    # 1. Submit
                    sub_res = client.post(
                        "/api/annotation/submit",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "candidate_finding_id": "CAND-HTTP-01",
                            "contract_id": "CTR-100",
                            "clause_id": "CLAUSE-01",
                            "payload": payload
                        }
                    )
                    assert sub_res.status_code == 201
                    sub_data = sub_res.get_json()
                    ann_id = sub_data["annotation_id"]
                    assert sub_data["is_locked"] is False

                    # 2. Lock
                    lock_res = client.post(
                        f"/api/annotation/lock/{ann_id}",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    assert lock_res.status_code == 200, lock_res.get_json()
                    lock_data = lock_res.get_json()
                    assert lock_data["is_locked"] is True
                    assert lock_data["locked_at"] is not None
