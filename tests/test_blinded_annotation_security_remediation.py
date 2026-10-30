"""
Targeted Verification Test Suite for Blinded Annotation Security Remediation.

Covers remediation of:
- SEC-01: Server-side metadata injection, client model metadata discard, missing candidate rejection.
- SEC-02: Role authorization on submission retrieval, client role rejection, service-layer enforcement.
- SEC-03: Adjudication dossier sanitization, removal of raw payload_json, allowlist projection, malformed JSON handling.
- SEC-04: Canonical stage definition, stage query parameter validation, rejection of invalid stages with HTTP 400.
- SEC-05: Scope verification and follow-up documentation.
"""

import os
import json
import uuid
import pytest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.persistence.database import Base
from src.persistence.models import (
    UserRecord, UserRole, AccountStatus, AdvocateStatus,
    BlindedAnnotationRecord, AnnotationStage, AdjudicationStatus
)
from src.persistence.repository import DocumentRepository
from src.auth.password import PasswordManager
from src.auth.token import TokenManager
from src.auth.config import AuthConfig

from src.annotation.firewall import PresentationFirewall, BlindingViolationError
from src.annotation.service import (
    BlindedAnnotationService, compute_payload_sha256, canonical_json_dumps
)
from src.annotation.candidate_registry import CandidateRegistry
from src.dashboard.app import app


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


def create_user(
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


def create_evaluative_payload(reference_action: str = "RETAIN", annotator_code: str = "ANN-001") -> dict:
    """Creates evaluative payload without identification (client-submitted format)."""
    return {
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
# SEC-01 TESTS: Server-Side Metadata Injection & Client Forgery Prevention
# =========================================================================

def test_sec01_client_cannot_inject_model_identity_or_confidence(test_session):
    """SEC-01: Server discards client-forged model identifiers and confidence scores, injecting authoritative metadata."""
    repo = DocumentRepository(test_session)
    service = BlindedAnnotationService(test_session)
    annotator = create_user(repo, "advocate_sec01@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)

    # Client maliciously attempts to supply forged model identity, version, and confidence
    payload = create_evaluative_payload("RETAIN")
    payload["identification"] = {
        "model_identifier": "forged-adversarial-model-v99",
        "model_version": "99.9.9",
        "candidate_confidence": {
            "score": 0.0001,
            "metric_type": "FORGED_SCORE",
            "is_calibrated": True
        },
        "contract_id": "EVIL-CONTRACT-999",
        "clause_id": "EVIL-CLAUSE-999"
    }

    sub = service.submit_annotation(
        candidate_finding_id="CAND-001",
        contract_id="EVIL-CONTRACT-999",
        clause_id="EVIL-CLAUSE-999",
        annotator_user=annotator,
        payload=payload
    )

    # Stored payload must contain AUTHORITATIVE metadata from CandidateRegistry, NOT the forged values
    stored_payload = json.loads(sub.payload_json)
    ident = stored_payload["identification"]
    assert ident["model_identifier"] == "nlpaueb/legal-bert-base-uncased"
    assert ident["model_identifier"] != "forged-adversarial-model-v99"
    assert ident["model_version"] == "1.0.0"
    assert ident["model_version"] != "99.9.9"
    assert ident["candidate_confidence"]["score"] == 0.884
    assert ident["candidate_confidence"]["score"] != 0.0001
    assert ident["contract_id"] == "CTR-100"
    assert ident["clause_id"] == "CLAUSE-14.2"
    assert sub.contract_id == "CTR-100"
    assert sub.clause_id == "CLAUSE-14.2"


def test_sec01_missing_candidate_metadata_causes_explicit_rejection(test_session):
    """SEC-01: Submissions for unresolvable/unverified candidates are strictly rejected without fabricating metadata."""
    repo = DocumentRepository(test_session)
    service = BlindedAnnotationService(test_session)
    annotator = create_user(repo, "advocate_missing@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)

    payload = create_evaluative_payload("RETAIN")

    with pytest.raises(ValueError) as exc:
        service.submit_annotation(
            candidate_finding_id="NON_EXISTENT_CANDIDATE_XYZ_9999",
            contract_id="CTR-999",
            clause_id="CLAUSE-999",
            annotator_user=annotator,
            payload=payload
        )
    assert "cannot be resolved from trusted candidate source" in str(exc.value)
    assert "Submissions for unverified candidate findings are strictly rejected" in str(exc.value)


def test_sec01_flask_route_rejects_missing_candidate_with_400(test_db_engine):
    """SEC-01: API POST /submit returns 400 when candidate cannot be authoritatively resolved."""
    app.config["TESTING"] = True
    from src.persistence.database import get_db_session as real_get_db_session
    tm = TokenManager(AuthConfig())

    with real_get_db_session(test_db_engine) as sess:
        repo = DocumentRepository(sess)
        lawyer = create_user(repo, "api_sec01@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        token = tm.generate_token(lawyer)

    payload = create_evaluative_payload("RETAIN")

    with patch("src.persistence.database.get_engine", return_value=test_db_engine):
        with patch("src.auth.rbac.get_db_session", side_effect=lambda: real_get_db_session(test_db_engine)):
            with patch("src.annotation.routes.get_db_session", side_effect=lambda: real_get_db_session(test_db_engine)):
                with app.test_client() as client:
                    resp = client.post(
                        "/api/annotation/submit",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "candidate_finding_id": "UNRESOLVABLE_CANDIDATE_404",
                            "payload": payload
                        }
                    )
                    assert resp.status_code == 400
                    body = resp.get_json()
                    assert "cannot be resolved from trusted candidate source" in body["error"]


# =========================================================================
# SEC-02 TESTS: Role Authorization & Submission Retrieval Access Control
# =========================================================================

def test_sec02_client_role_cannot_retrieve_internal_annotation_submission(test_db_engine):
    """SEC-02: API GET /api/annotation/submission/<id> strictly rejects CLIENT role callers with HTTP 403."""
    app.config["TESTING"] = True
    from src.persistence.database import get_db_session as real_get_db_session
    tm = TokenManager(AuthConfig())

    with real_get_db_session(test_db_engine) as sess:
        repo = DocumentRepository(sess)
        lawyer = create_user(repo, "lawyer_sub@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        client_user = create_user(repo, "client_intruder@client.in", UserRole.CLIENT)
        service = BlindedAnnotationService(sess)
        payload = create_evaluative_payload("RETAIN")
        sub = service.submit_annotation("CAND-001", "CTR-100", "CLAUSE-14.2", lawyer, payload)
        sub_id = sub.id
        client_token = tm.generate_token(client_user)

    with patch("src.persistence.database.get_engine", return_value=test_db_engine):
        with patch("src.auth.rbac.get_db_session", side_effect=lambda: real_get_db_session(test_db_engine)):
            with patch("src.annotation.routes.get_db_session", side_effect=lambda: real_get_db_session(test_db_engine)):
                with app.test_client() as client:
                    resp = client.get(
                        f"/api/annotation/submission/{sub_id}",
                        headers={"Authorization": f"Bearer {client_token}"}
                    )
                    assert resp.status_code == 403
                    body = resp.get_json()
                    assert "error" in body


def test_sec02_service_layer_strictly_rejects_client_role(test_session):
    """SEC-02: Service layer enforces role boundaries and strictly rejects CLIENT callers."""
    repo = DocumentRepository(test_session)
    service = BlindedAnnotationService(test_session)

    lawyer = create_user(repo, "lawyer_sec02@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    client_user = create_user(repo, "client_service@client.in", UserRole.CLIENT)

    payload = create_evaluative_payload("RETAIN")
    sub = service.submit_annotation("CAND-001", "CTR-100", "CLAUSE-14.2", lawyer, payload)

    with pytest.raises(PermissionError) as exc:
        service.get_submission_for_user(sub.id, client_user)
    assert "Clients are strictly prohibited from inspecting internal annotation submissions" in str(exc.value)


def test_sec02_unverified_lawyer_cannot_retrieve_submission(test_session):
    """SEC-02: Service layer strictly requires advocate verification for LAWYER role."""
    repo = DocumentRepository(test_session)
    service = BlindedAnnotationService(test_session)

    lawyer = create_user(repo, "auth_lawyer@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    unverified = create_user(repo, "unverified_reader@chamber.in", UserRole.LAWYER, AdvocateStatus.PENDING_VERIFICATION)

    payload = create_evaluative_payload("RETAIN")
    sub = service.submit_annotation("CAND-001", "CTR-100", "CLAUSE-14.2", lawyer, payload)

    with pytest.raises(PermissionError) as exc:
        service.get_submission_for_user(sub.id, unverified)
    assert "Enrolled advocate verification required" in str(exc.value)


# =========================================================================
# SEC-03 TESTS: Adjudication Dossier Sanitization & Payload JSON Removal
# =========================================================================

def test_sec03_adjudication_dossier_excludes_raw_payload_json_and_prohibited_fields(test_session):
    """SEC-03: Dossier parses payload_json, uses strict allowlists, and strips raw payload_json and prohibited fields."""
    repo = DocumentRepository(test_session)
    service = BlindedAnnotationService(test_session)

    ann1 = create_user(repo, "ann1_sec03@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    ann2 = create_user(repo, "ann2_sec03@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
    senior = create_user(repo, "senior_sec03@chamber.in", UserRole.SUPERVISING_LAWYER, AdvocateStatus.VERIFIED)

    cand_data = CandidateRegistry.resolve("CAND-ADJ-01")

    # Construct submissions
    p1 = create_evaluative_payload("RETAIN")
    p2 = create_evaluative_payload("WITHHOLD")

    sub1 = service.submit_annotation("CAND-ADJ-01", "CTR-100", "CLAUSE-14.2", ann1, p1)
    sub2 = service.submit_annotation("CAND-ADJ-01", "CTR-100", "CLAUSE-14.2", ann2, p2)

    service.lock_annotation(sub1.id, ann1)
    service.lock_annotation(sub2.id, ann2)

    dossier = service.get_adjudication_dossier("CAND-ADJ-01", cand_data, senior)

    # 1. Candidate must not leak model confidence or policy
    cand_view = dossier["candidate"]
    assert "confidence_value" not in cand_view
    assert "model_id" not in cand_view
    assert "baseline_policy_decision" not in cand_view

    # 2. Submissions must NOT contain raw payload_json
    sub1_view = dossier["submission_1"]
    sub2_view = dossier["submission_2"]
    assert "payload_json" not in sub1_view
    assert "payload_json" not in sub2_view

    # 3. Submissions must contain evaluative_payload with human judgments
    assert "evaluative_payload" in sub1_view
    assert "evaluative_payload" in sub2_view

    eval1 = sub1_view["evaluative_payload"]
    assert "prediction_assessment" in eval1
    assert "final_reference_decision" in eval1
    assert eval1["final_reference_decision"]["reference_action"] == "RETAIN"

    # 4. Evaluative payload must NOT contain identification or prohibited fields
    assert "identification" not in eval1
    assert "model_identifier" not in eval1
    assert "candidate_confidence" not in eval1
    assert "confidence_value" not in eval1
    assert "bm25_score" not in eval1


def test_sec03_malformed_json_does_not_bypass_firewall():
    """SEC-03: Malformed JSON strings safely evaluate to empty dict without crashing or leaking raw text."""
    bad_payload = "{'malformed': json, unclosed string..."
    sanitized = PresentationFirewall.sanitize_evaluative_payload(bad_payload)
    assert sanitized == {}

    # None and empty inputs also produce empty dict
    assert PresentationFirewall.sanitize_evaluative_payload(None) == {}
    assert PresentationFirewall.sanitize_evaluative_payload("") == {}


def test_sec03_malicious_prohibited_fields_in_payload_are_stripped():
    """SEC-03: Malicious injection of prohibited keys into sub-dictionaries is strictly stripped."""
    sneaky_payload = {
        "prediction_assessment": {
            "status": "CORRECT",
            "rationale": "Legitimate legal assessment of indemnity clause.",
            "identified_risk_severity": "HIGH",
            "model_id": "MALICIOUS_MODEL_INJECTION",
            "confidence_value": 0.999,
            "raw_logit": 12.5
        },
        "identification": {
            "model_identifier": "SHOULD_BE_PURGED"
        },
        "baseline_policy_decision": "RETAIN"
    }

    sanitized = PresentationFirewall.sanitize_evaluative_payload(sneaky_payload)

    # Top-level prohibited / non-allowlisted keys must be gone
    assert "identification" not in sanitized
    assert "baseline_policy_decision" not in sanitized

    # Sub-dictionary prohibited keys must be stripped
    pred = sanitized["prediction_assessment"]
    assert "status" in pred
    assert "rationale" in pred
    assert "identified_risk_severity" in pred
    assert "model_id" not in pred
    assert "confidence_value" not in pred
    assert "raw_logit" not in pred


# =========================================================================
# SEC-04 TESTS: Stage Validation & Rejection of Invalid Stages
# =========================================================================

def test_sec04_invalid_stage_query_param_returns_400(test_db_engine):
    """SEC-04: API endpoint GET /api/annotation/candidate/<id>?stage=INVALID returns HTTP 400."""
    app.config["TESTING"] = True
    from src.persistence.database import get_db_session as real_get_db_session
    tm = TokenManager(AuthConfig())

    with real_get_db_session(test_db_engine) as sess:
        repo = DocumentRepository(sess)
        lawyer = create_user(repo, "stage_lawyer@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        token = tm.generate_token(lawyer)

    with patch("src.persistence.database.get_engine", return_value=test_db_engine):
        with patch("src.auth.rbac.get_db_session", side_effect=lambda: real_get_db_session(test_db_engine)):
            with patch("src.annotation.routes.get_db_session", side_effect=lambda: real_get_db_session(test_db_engine)):
                with app.test_client() as client:
                    resp = client.get(
                        "/api/annotation/candidate/CAND-001?stage=STAGE_BOGUS_999",
                        headers={"Authorization": f"Bearer {token}"}
                    )
                    assert resp.status_code == 400
                    body = resp.get_json()
                    assert "Invalid stage 'STAGE_BOGUS_999'" in body["error"]


def test_sec04_invalid_stage_in_submit_returns_400(test_db_engine):
    """SEC-04: API endpoint POST /api/annotation/submit with invalid stage returns HTTP 400."""
    app.config["TESTING"] = True
    from src.persistence.database import get_db_session as real_get_db_session
    tm = TokenManager(AuthConfig())

    with real_get_db_session(test_db_engine) as sess:
        repo = DocumentRepository(sess)
        lawyer = create_user(repo, "submit_stage_lawyer@chamber.in", UserRole.LAWYER, AdvocateStatus.VERIFIED)
        token = tm.generate_token(lawyer)

    payload = create_evaluative_payload("RETAIN")

    with patch("src.persistence.database.get_engine", return_value=test_db_engine):
        with patch("src.auth.rbac.get_db_session", side_effect=lambda: real_get_db_session(test_db_engine)):
            with patch("src.annotation.routes.get_db_session", side_effect=lambda: real_get_db_session(test_db_engine)):
                with app.test_client() as client:
                    resp = client.post(
                        "/api/annotation/submit",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "candidate_finding_id": "CAND-001",
                            "stage": "INVALID_STAGE_XYZ",
                            "payload": payload
                        }
                    )
                    assert resp.status_code == 400
                    body = resp.get_json()
                    assert "Invalid stage 'INVALID_STAGE_XYZ'" in body["error"]


def test_sec04_presentation_firewall_raises_valueerror_on_unrecognized_stage():
    """SEC-04: PresentationFirewall.filter_candidate_for_annotator raises ValueError on unrecognized stage."""
    raw = CandidateRegistry.resolve("CAND-001")

    with pytest.raises(ValueError) as exc:
        PresentationFirewall.filter_candidate_for_annotator(raw, stage="UNRECOGNIZED_ARBITRARY_STAGE")
    assert "Invalid or unrecognized annotation stage" in str(exc.value)


def test_sec04_all_canonical_stages_supported_without_error():
    """SEC-04: All canonical AnnotationStage enum values are recognized and filtered properly."""
    raw = CandidateRegistry.resolve("CAND-001")

    for stage_enum in AnnotationStage:
        res = PresentationFirewall.filter_candidate_for_annotator(raw, stage=stage_enum.value)
        assert isinstance(res, dict)
        assert len(res) > 0
        assert "confidence_value" not in res
        assert "model_id" not in res
