"""
Security test suite for Authentication, Advocate Verification, and Role-Based Access Control (Task 031).
Verifies all 23 requirements:
1. Successful registration.
2. Duplicate normalized-email rejection.
3. Successful authentication.
4. Invalid-password rejection.
5. Generic login failure behavior.
6. Passwords are not stored in plaintext.
7. Password-hash verification (Argon2id).
8. Logout and token invalidation.
9. Expired or invalid token rejection.
10. Cookie session and CSRF/header safety.
11. Unauthenticated access rejection (401).
12. Horizontal isolation: CLIENT cannot access another client's contract.
13. Vertical isolation: CLIENT cannot access lawyer operations.
14. Lawyer assignment isolation: LAWYER cannot access unassigned contracts.
15. Self-verification prevention: LAWYER cannot verify themselves.
16. Unauthorized role escalation prevention: non-admin cannot self-provision supervising lawyer.
17. Advocate verification gate: Unverified lawyers cannot perform privileged lawyer operations.
18. Revocation gate: Rejected or suspended lawyers lose privileged access.
19. State machine validation for advocate verification.
20. Security audit event generation and hash chaining.
21. Auditor privilege boundary: Auditors cannot view raw contract content.
22. Compatibility with Task 030 document ingestion.
23. Existing research artifacts and pipeline integrity preservation.
"""

import os
import io
import time
import uuid
import datetime
import tempfile
import pytest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.persistence.database import Base, get_session_factory
from src.persistence.models import (
    UserRecord, AdvocateVerificationRecord, DocumentRecord,
    UserRole, AccountStatus, AdvocateStatus
)
from src.persistence.repository import DocumentRepository
from src.auth.config import AuthConfig
from src.auth.password import PasswordManager
from src.auth.token import TokenManager
from src.auth.service import AuthService
from src.auth.rbac import AccessController
from src.audit.store import AuditStore
from src.audit.logger import AuditLogger
from src.audit.integrity import AuditVerifier
from src.audit.provenance import IntegrityStatus, EventType

from src.dashboard.app import app
from src.ingestion.pipeline import IngestionPipeline
from src.ingestion.config import IngestionConfig

# =========================================================================
# TEST FIXTURES
# =========================================================================

@pytest.fixture
def auth_db_engine():
    """Isolated in-memory SQLite database for authentication testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()

@pytest.fixture
def auth_session(auth_db_engine):
    factory = sessionmaker(bind=auth_db_engine, autocommit=False, autoflush=False)
    sess = factory()
    yield sess
    sess.rollback()
    sess.close()

@pytest.fixture
def auth_service(auth_session):
    store = AuditStore()
    logger = AuditLogger(store)
    return AuthService(session=auth_session, audit_logger=logger)

@pytest.fixture
def flask_client(auth_db_engine):
    app.config["TESTING"] = True
    with patch("src.persistence.database.get_engine", return_value=auth_db_engine):
        with patch("src.auth.rbac.get_db_session") as mock_sess:
            mock_sess.side_effect = lambda: get_session_factory(auth_db_engine)()
            with app.test_client() as client:
                yield client

# Helper to create a user directly in DB
def create_test_user(
    repo: DocumentRepository,
    email: str,
    role: UserRole,
    password: str = "Password123!",
    advocate_status: AdvocateStatus = AdvocateStatus.NOT_APPLICABLE
) -> UserRecord:
    pm = PasswordManager()
    h = pm.hash_password(password)
    return repo.create_user(
        user_id=str(uuid.uuid4()),
        email=email,
        password_hash=h,
        full_name=f"Test {role.value}",
        role=role,
        account_status=AccountStatus.ACTIVE,
        advocate_status=advocate_status,
        bar_enrolment_id="KAR/123/2020" if role == UserRole.LAWYER else None,
        state_bar_council="Karnataka" if role == UserRole.LAWYER else None,
        year_of_enrolment=2020 if role == UserRole.LAWYER else None
    )

# =========================================================================
# TESTS
# =========================================================================

def test_01_successful_registration(auth_service):
    """1. Successful registration."""
    user = auth_service.register_user(
        email="client.alpha@example.com",
        password="ValidPassword123!",
        full_name="Alpha Client Corp"
    )
    assert user.id is not None
    assert user.email == "client.alpha@example.com"
    assert user.role == UserRole.CLIENT.value
    assert user.advocate_status == AdvocateStatus.NOT_APPLICABLE.value
    assert user.account_status == AccountStatus.ACTIVE.value

def test_02_duplicate_normalized_email_rejection(auth_service):
    """2. Duplicate normalized-email rejection."""
    auth_service.register_user(
        email="test.client@example.com",
        password="Password123!",
        full_name="Original User"
    )
    # Attempt registration with mixed-case and whitespace
    with pytest.raises(ValueError) as excinfo:
        auth_service.register_user(
            email="  TEST.CLIENT@Example.Com  ",
            password="Password123!",
            full_name="Duplicate User"
        )
    assert "already exists" in str(excinfo.value)

def test_03_successful_authentication(auth_service):
    """3. Successful authentication."""
    auth_service.register_user(
        email="auth.user@example.com",
        password="MySecretPassword123!",
        full_name="Auth User"
    )
    user, token, err = auth_service.authenticate_user("AUTH.USER@example.com", "MySecretPassword123!")
    assert err is None
    assert user is not None
    assert token is not None
    assert len(token) > 20

def test_04_invalid_password_rejection(auth_service):
    """4. Invalid-password rejection."""
    auth_service.register_user(
        email="user.wrongpass@example.com",
        password="CorrectPassword123!",
        full_name="User"
    )
    user, token, err = auth_service.authenticate_user("user.wrongpass@example.com", "WrongPassword999!")
    assert user is None
    assert token is None
    assert err == "Invalid email or password."

def test_05_generic_login_failure_behavior(auth_service):
    """5. Generic login failure behavior (prevents user enumeration)."""
    # Non-existent account
    _, _, err_nonexistent = auth_service.authenticate_user("nonexistent@example.com", "AnyPassword123!")
    # Existing account, bad password
    auth_service.register_user("realuser@example.com", "GoodPassword123!", "Real User")
    _, _, err_badpass = auth_service.authenticate_user("realuser@example.com", "WrongPassword123!")
    
    # Error message must be identical
    assert err_nonexistent == err_badpass == "Invalid email or password."

def test_06_passwords_are_not_stored_in_plaintext(auth_service):
    """6. Passwords are not stored in plaintext."""
    pwd = "UltraSecretPassword123!"
    user = auth_service.register_user("secret@example.com", pwd, "Secret User")
    
    assert pwd not in user.password_hash
    assert user.password_hash.startswith("$argon2id$")

def test_07_password_hash_verification(auth_service):
    """7. Password-hash verification via Argon2id."""
    pm = PasswordManager()
    h = pm.hash_password("VerifyTestPass123!")
    assert pm.verify_password("VerifyTestPass123!", h) is True
    assert pm.verify_password("IncorrectPass123!", h) is False

def test_08_logout_and_token_invalidation(auth_service):
    """8. Logout and token invalidation."""
    auth_service.register_user("logout.user@example.com", "Password123!", "Logout User")
    user, token, _ = auth_service.authenticate_user("logout.user@example.com", "Password123!")
    
    # Token valid before logout
    payload_before = auth_service.token_manager.decode_and_validate_token(token)
    assert payload_before is not None
    
    # Logout revokes token
    revoked = auth_service.logout_user(token, user_id=user.id)
    assert revoked is True
    
    # Token rejected after logout
    payload_after = auth_service.token_manager.decode_and_validate_token(token)
    assert payload_after is None

def test_09_expired_or_invalid_token_rejection(auth_service):
    """9. Expired or invalid token rejection."""
    tm = auth_service.token_manager
    user = auth_service.register_user("expiry@example.com", "Password123!", "Expiry User")
    
    # Generate token that expired 10 minutes ago
    expired_token = tm.generate_token(user, expires_delta_minutes=-10)
    assert tm.decode_and_validate_token(expired_token) is None
    
    # Corrupted token
    assert tm.decode_and_validate_token("invalid.token.signature") is None

def test_10_cookie_session_and_csrf_safety(auth_service):
    """10. Cookie session security configurations."""
    cfg = AuthConfig(cookie_secure=True)
    assert cfg.cookie_httponly is True
    assert cfg.cookie_samesite == "Lax"
    assert cfg.cookie_secure is True

def test_11_unauthenticated_access_rejection(auth_service):
    """11. Unauthenticated access to protected operations is rejected (deny-by-default)."""
    assert AccessController.can_access_contract(None, None) is False
    assert AccessController.can_perform_lawyer_operations(None) is False
    assert AccessController.can_perform_supervisory_operations(None) is False
    assert AccessController.can_access_audit_logs(None) is False

def test_12_client_cannot_access_another_clients_contract(auth_session):
    """12. Horizontal isolation: CLIENT cannot access another client's contract."""
    repo = DocumentRepository(auth_session)
    client_a = create_test_user(repo, "client.a@example.com", UserRole.CLIENT)
    client_b = create_test_user(repo, "client.b@example.com", UserRole.CLIENT)
    
    doc_a = DocumentRecord(
        id=str(uuid.uuid4()), file_sha256="sha_a", original_filename="a.txt",
        sanitized_filename="a.txt", mime_type="text/plain", document_format="TXT",
        file_size_bytes=100, storage_path="/path/a", owner_id=client_a.id
    )
    
    # Client A can access their own document
    assert AccessController.can_access_contract(client_a, doc_a) is True
    # Client B CANNOT access Client A's document
    assert AccessController.can_access_contract(client_b, doc_a) is False

def test_13_client_cannot_access_lawyer_operations(auth_session):
    """13. Vertical isolation: CLIENT cannot access lawyer operations."""
    repo = DocumentRepository(auth_session)
    client = create_test_user(repo, "client.regular@example.com", UserRole.CLIENT)
    
    assert AccessController.can_perform_lawyer_operations(client) is False
    assert AccessController.can_perform_supervisory_operations(client) is False

def test_14_lawyer_cannot_access_unassigned_contract(auth_session):
    """14. Lawyer assignment isolation: LAWYER cannot access unassigned contract."""
    repo = DocumentRepository(auth_session)
    lawyer_1 = create_test_user(repo, "lawyer.one@example.com", UserRole.LAWYER, advocate_status=AdvocateStatus.VERIFIED)
    lawyer_2 = create_test_user(repo, "lawyer.two@example.com", UserRole.LAWYER, advocate_status=AdvocateStatus.VERIFIED)
    
    assigned_doc = DocumentRecord(
        id=str(uuid.uuid4()), file_sha256="sha_doc", original_filename="doc.txt",
        sanitized_filename="doc.txt", mime_type="text/plain", document_format="TXT",
        file_size_bytes=100, storage_path="/path/doc", assigned_lawyer_id=lawyer_1.id
    )
    
    # Assigned lawyer has access
    assert AccessController.can_access_contract(lawyer_1, assigned_doc) is True
    # Unassigned lawyer CANNOT access
    assert AccessController.can_access_contract(lawyer_2, assigned_doc) is False

def test_15_lawyer_cannot_verify_themselves(auth_service):
    """15. Self-verification prevention: Lawyer cannot verify their own application."""
    applicant = auth_service.register_user(
        email="applicant@example.com", password="Password123!", full_name="Applicant",
        role=UserRole.LAWYER, bar_enrolment_id="KAR/101/2021", state_bar_council="Karnataka", year_of_enrolment=2021
    )
    req = auth_service.submit_advocate_verification(
        applicant, "KAR/101/2021", "Karnataka", 2021
    )
    
    # Even if applicant attempts to act as reviewer on their own request
    with pytest.raises(PermissionError) as excinfo:
        auth_service.decide_advocate_verification(
            reviewer=applicant,
            request_id=req.id,
            decision=AdvocateStatus.VERIFIED,
            rationale="Attempted self-approval"
        )
    assert "Supervising Lawyer" in str(excinfo.value) or "Self-verification" in str(excinfo.value)

def test_16_unauthorized_role_escalation_rejected(auth_service):
    """16. Unauthorized role escalation is rejected."""
    # Ordinary registration cannot claim SUPERVISING_LAWYER
    with pytest.raises(PermissionError) as excinfo:
        auth_service.register_user(
            email="hacker@example.com",
            password="Password123!",
            full_name="Fake Admin",
            role=UserRole.SUPERVISING_LAWYER
        )
    assert "Self-promotion" in str(excinfo.value)

def test_17_unverified_lawyers_cannot_perform_privileged_operations(auth_session):
    """17. Unverified lawyers cannot perform privileged lawyer operations."""
    repo = DocumentRepository(auth_session)
    unverified_lawyer = create_test_user(
        repo, "pending@example.com", UserRole.LAWYER, advocate_status=AdvocateStatus.PENDING_VERIFICATION
    )
    
    assert AccessController.can_perform_lawyer_operations(unverified_lawyer) is False

def test_18_rejected_or_suspended_lawyers_lose_privileges(auth_session):
    """18. Rejected or suspended lawyers lose applicable privileges."""
    repo = DocumentRepository(auth_session)
    rejected_lawyer = create_test_user(repo, "rej@example.com", UserRole.LAWYER, advocate_status=AdvocateStatus.REJECTED)
    suspended_lawyer = create_test_user(repo, "susp@example.com", UserRole.LAWYER, advocate_status=AdvocateStatus.SUSPENDED)
    
    assert AccessController.can_perform_lawyer_operations(rejected_lawyer) is False
    assert AccessController.can_perform_lawyer_operations(suspended_lawyer) is False

def test_19_verification_state_machine_transitions(auth_service):
    """19. Verification transitions are validated."""
    partner = auth_service.repo.create_user(
        user_id=str(uuid.uuid4()), email="lead.partner@example.com",
        password_hash="dummy", full_name="Lead Partner", role=UserRole.SUPERVISING_LAWYER,
        advocate_status=AdvocateStatus.VERIFIED
    )
    lawyer = auth_service.register_user(
        email="junior@example.com", password="Password123!", full_name="Junior",
        role=UserRole.LAWYER, bar_enrolment_id="MAH/999/2022", state_bar_council="Maharashtra", year_of_enrolment=2022
    )
    req = auth_service.submit_advocate_verification(
        lawyer, "MAH/999/2022", "Maharashtra", 2022
    )
    assert req.status == AdvocateStatus.PENDING_VERIFICATION.value
    
    # Transition to VERIFIED
    decided = auth_service.decide_advocate_verification(
        reviewer=partner,
        request_id=req.id,
        decision=AdvocateStatus.VERIFIED,
        rationale="Credentials confirmed against Maharashtra State Bar Roll"
    )
    assert decided.status == AdvocateStatus.VERIFIED.value
    
    # Reload applicant
    updated_lawyer = auth_service.repo.get_user_by_id(lawyer.id)
    assert updated_lawyer.advocate_status == AdvocateStatus.VERIFIED.value

def test_20_verification_actions_produce_audit_events(auth_service):
    """20. Verification actions produce cryptographic audit events."""
    partner = auth_service.repo.create_user(
        user_id=str(uuid.uuid4()), email="audited.partner@example.com",
        password_hash="dummy", full_name="Partner", role=UserRole.SUPERVISING_LAWYER,
        advocate_status=AdvocateStatus.VERIFIED
    )
    lawyer = auth_service.register_user(
        email="audited.junior@example.com", password="Password123!", full_name="Junior",
        role=UserRole.LAWYER, bar_enrolment_id="DEL/456/2019", state_bar_council="Delhi", year_of_enrolment=2019
    )
    req = auth_service.submit_advocate_verification(lawyer, "DEL/456/2019", "Delhi", 2019)
    auth_service.decide_advocate_verification(partner, req.id, AdvocateStatus.VERIFIED, "Verified credentials")
    
    events = auth_service.audit_logger.store.get_all()
    event_types = [e.event_type.value for e in events]
    assert "USER_REGISTERED" in event_types
    assert "ADVOCATE_VERIFICATION_SUBMITTED" in event_types
    assert "ADVOCATE_VERIFICATION_DECIDED" in event_types
    
    # Verify cryptographic hash chain
    verifier = AuditVerifier()
    status, err = verifier.verify(auth_service.audit_logger.store)
    assert status == IntegrityStatus.VALID
    assert err is None

def test_21_auditor_permissions_exclude_confidential_contract_contents(auth_session):
    """21. Auditor permissions exclude confidential contract contents."""
    repo = DocumentRepository(auth_session)
    auditor = create_test_user(repo, "compliance.officer@example.com", UserRole.AUDITOR)
    doc = DocumentRecord(
        id=str(uuid.uuid4()), file_sha256="sha_audit", original_filename="confidential.pdf",
        sanitized_filename="confidential.pdf", mime_type="application/pdf", document_format="PDF",
        file_size_bytes=5000, storage_path="/path"
    )
    
    # Auditor CAN access metadata inspection
    assert AccessController.can_access_contract(auditor, doc, require_full_content=False) is True
    # Auditor CANNOT access full text/clauses
    assert AccessController.can_access_contract(auditor, doc, require_full_content=True) is False

def test_22_existing_task030_ingestion_tests_continue_to_pass(auth_db_engine):
    """22. Existing Task 030 ingestion tests continue to pass without regression."""
    config = IngestionConfig(storage_root=tempfile.mkdtemp())
    pipeline = IngestionPipeline(config=config, db_engine=auth_db_engine)
    
    sample_text = (
        "CONFIDENTIALITY AND NON-DISCLOSURE AGREEMENT\n\n"
        "1. Secrecy Obligations. The parties shall preserve all proprietary business materials.\n"
        "2. Jurisdiction. This contract is governed by Indian law."
    ).encode("utf-8")
    
    res = pipeline.ingest_document(sample_text, "nda.txt")
    assert res.status.value == "SEGMENTED"
    assert res.segment_count >= 2

def test_23_existing_research_artifacts_preserved():
    """23. Existing research artifacts remain untouched."""
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    weights_path = os.path.join(
        workspace_root, "results", "models", "ledgar_frozen_subset_fresh", "final_model", "model.safetensors"
    )
    assert os.path.exists(weights_path)
    assert os.path.getsize(weights_path) == 476_116_436
