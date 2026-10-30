import os
import io
import json
import uuid
import pytest
from src.dashboard.app import app
from src.persistence.database import get_db_session
from src.persistence.models import UserRecord, UserRole, AccountStatus, AdvocateStatus
from src.auth.password import PasswordManager
from src.auth.token import TokenManager

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def auth_tokens():
    """Generates valid JWT tokens for test client and advocate."""
    pwd_mgr = PasswordManager()
    token_mgr = TokenManager()

    with get_db_session() as session:
        # Create test client
        client_user = session.query(UserRecord).filter_by(email="client_ui_test@example.com").first()
        if not client_user:
            client_user = UserRecord(
                id="user-client-ui-001",
                email="client_ui_test@example.com",
                password_hash=pwd_mgr.hash_password("Pass12345!"),
                role=UserRole.CLIENT.value,
                account_status=AccountStatus.ACTIVE.value,
                advocate_status=AdvocateStatus.NOT_APPLICABLE.value,
                full_name="Test Enterprise Client"
            )
            session.add(client_user)

        # Create test advocate
        lawyer_user = session.query(UserRecord).filter_by(email="lawyer_ui_test@example.com").first()
        if not lawyer_user:
            lawyer_user = UserRecord(
                id="user-lawyer-ui-002",
                email="lawyer_ui_test@example.com",
                password_hash=pwd_mgr.hash_password("Pass12345!"),
                role=UserRole.LAWYER.value,
                account_status=AccountStatus.ACTIVE.value,
                advocate_status=AdvocateStatus.VERIFIED.value,
                full_name="Adv. Tester"
            )
            session.add(lawyer_user)
        # Create test auditor
        auditor_user = session.query(UserRecord).filter_by(email="auditor_ui_test@example.com").first()
        if not auditor_user:
            auditor_user = UserRecord(
                id="user-auditor-ui-003",
                email="auditor_ui_test@example.com",
                password_hash=pwd_mgr.hash_password("Pass12345!"),
                role=UserRole.AUDITOR.value,
                account_status=AccountStatus.ACTIVE.value,
                advocate_status=AdvocateStatus.NOT_APPLICABLE.value,
                full_name="Compliance Auditor"
            )
            session.add(auditor_user)

        # Create test supervisor
        supervisor_user = session.query(UserRecord).filter_by(email="supervisor_ui_test@example.com").first()
        if not supervisor_user:
            supervisor_user = UserRecord(
                id="user-supervisor-ui-004",
                email="supervisor_ui_test@example.com",
                password_hash=pwd_mgr.hash_password("Pass12345!"),
                role=UserRole.SUPERVISING_LAWYER.value,
                account_status=AccountStatus.ACTIVE.value,
                advocate_status=AdvocateStatus.VERIFIED.value,
                full_name="Senior Managing Partner"
            )
            session.add(supervisor_user)

        session.commit()

        client_token = token_mgr.generate_token(client_user)
        lawyer_token = token_mgr.generate_token(lawyer_user)
        auditor_token = token_mgr.generate_token(auditor_user)
        supervisor_token = token_mgr.generate_token(supervisor_user)
        return {
            "client_token": client_token,
            "lawyer_token": lawyer_token,
            "auditor_token": auditor_token,
            "supervisor_token": supervisor_token,
            "client_id": "user-client-ui-001",
            "lawyer_id": "user-lawyer-ui-002",
            "auditor_id": "user-auditor-ui-003",
            "supervisor_id": "user-supervisor-ui-004"
        }

def test_static_brand_assets_serving(client):
    """Verifies that all legal SVG brand assets and stylesheets serve with HTTP 200."""
    # Logo SVG
    res_logo = client.get("/static/img/logo.svg")
    assert res_logo.status_code == 200
    assert "image/svg+xml" in res_logo.headers.get("Content-Type", "")
    logo_svg = res_logo.get_data(as_text=True)
    assert "<svg" in logo_svg
    assert "CONTRACTRISK-XAI" in logo_svg
    assert "#142B4A" in logo_svg

    # Favicon SVG
    res_fav = client.get("/static/img/favicon.svg")
    assert res_fav.status_code == 200
    assert "<svg" in res_fav.get_data(as_text=True)

    # Legal Hero SVG
    res_hero = client.get("/static/img/legal_hero.svg")
    assert res_hero.status_code == 200
    assert "<svg" in res_hero.get_data(as_text=True)

    # Empty State SVG
    res_empty = client.get("/static/img/empty_contracts.svg")
    assert res_empty.status_code == 200
    assert "<svg" in res_empty.get_data(as_text=True)

    # Design System CSS
    res_css = client.get("/static/css/design_system.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.headers.get("Content-Type", "")
    css_text = res_css.get_data(as_text=True)
    assert "--navy-primary: #142B4A" in css_text
    assert "--gold-accent: #C6A15B" in css_text
    assert "@media (max-width: 768px)" in css_text

    # Dashboard JavaScript
    res_js = client.get("/static/js/dashboard.js")
    assert res_js.status_code == 200
    js_text = res_js.get_data(as_text=True)
    assert "switchTab" in js_text
    assert "loadWorkbenchQueue" in js_text
    assert "handleContractUpload" in js_text

def test_html_shell_and_legal_branding(client):
    """Verifies modernized shell, semantic markup, and brand tagline."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # Brand Title and Tagline
    assert "CONTRACTRISK-XAI" in html
    assert "Intelligent Contract Analysis. Human-Guided Legal Review." in html

    # Assets Linked
    assert "/static/img/favicon.svg" in html
    assert "/static/css/design_system.css" in html
    assert "/static/js/dashboard.js" in html

    # Semantic Landmark Roles
    assert '<header class="app-header" role="banner">' in html
    assert '<main class="app-main" role="main">' in html
    assert '<footer class="app-footer" role="contentinfo">' in html
    assert '<nav class="nav-tabs" role="tablist"' in html

    # Disclaimers and Test Strings Preserved
    assert "NOT a validated legal decision-maker" in html
    assert "12,699" in html
    assert "58,947" in html

def test_role_switcher_and_login_modal(client):
    """Verifies that the login dialog contains accessible two-column layout and role switchers."""
    res = client.get("/")
    html = res.get_data(as_text=True)

    # Modal structure
    assert 'id="login-modal"' in html
    assert 'modal-2col' in html
    assert 'role="dialog"' in html
    assert 'aria-modal="true"' in html

    # Role quick buttons
    assert "Advocate" in html
    assert "Client" in html
    assert "Supervisor" in html
    assert "Auditor" in html

    # Form labels & fields
    assert 'for="auth-email"' in html
    assert 'for="auth-password"' in html

def test_lawyer_workbench_interface_components(client):
    """Verifies presence of lawyer review workbench, evidence panel, and mandatory rationale."""
    res = client.get("/")
    html = res.get_data(as_text=True)

    assert 'id="tab-lawyer-workbench"' in html
    assert 'id="workbench-queue-list"' in html
    assert 'id="wb-clause-list"' in html
    assert 'id="wb-evidence-panel"' in html
    assert 'id="wb-decision-type"' in html
    assert 'Substantive Lawyer Rationale' in html
    assert 'required-star' in html
    assert 'Strictly Confidential' in html
    assert 'Generate Final Client Report' in html

def test_client_workspace_components_and_plain_language_labels(client):
    """Verifies client contract workspace, upload modal, reports, and 1-5 feedback."""
    res = client.get("/")
    html = res.get_data(as_text=True)

    assert 'id="tab-client-workspace"' in html
    assert 'id="client-contract-list"' in html
    assert 'Upload New Contract' in html
    assert 'Submit Report Feedback &amp; Follow-up Request' in html
    assert 'Overall Satisfaction (1-5)' in html
    assert 'Report Clarity (1-5)' in html
    assert 'Findings Usefulness (1-5)' in html
    assert 'Need Further Clarification' in html
    assert 'Request Advocate Follow-up' in html

    # Plain language labels in JS/HTML
    res_js = client.get("/static/js/dashboard.js")
    js = res_js.get_data(as_text=True)
    assert "Waiting for a lawyer" in js
    assert "Lawyer assigned" in js
    assert "Your contract is being reviewed" in js
    assert "Additional information or changes requested" in js
    assert "Review completed" in js

def test_contract_upload_endpoint_integration(client, auth_tokens):
    """Verifies the backend upload route /api/review/upload ingests and starts review."""
    # 1. Unauthenticated fails
    res_unauth = client.post("/api/review/upload", data={"title": "Test Agreement"})
    assert res_unauth.status_code == 401

    # 2. Authenticated Client Upload
    contract_bytes = (
        b"ENTERPRISE CLOUD SERVICES AGREEMENT\n\n"
        b"1. SCOPE AND DELIVERABLES\n"
        b"The Provider shall deliver cloud contract risk analysis services to the Customer.\n\n"
        b"2. ARBITRATION AND GOVERNING LAW\n"
        b"All disputes shall be referred to arbitration in accordance with the Arbitration and Conciliation Act, 1996 in New Delhi.\n"
    )
    headers = {"Authorization": f"Bearer {auth_tokens['client_token']}"}
    data = {
        "title": "Cloud Master Services 2026",
        "file": (io.BytesIO(contract_bytes), "cloud_agreement.txt")
    }

    res_upload = client.post(
        "/api/review/upload",
        headers=headers,
        data=data,
        content_type="multipart/form-data"
    )
    assert res_upload.status_code == 201
    payload = res_upload.get_json()
    assert payload["status"] in ["DOCUMENT_SUBMITTED", "SUCCESS"]
    assert "document_id" in payload
    assert "review_id" in payload
    assert payload["segments_count"] >= 1

    # 3. Invalid file type rejected
    bad_data = {
        "title": "Bad File",
        "file": (io.BytesIO(b"binary data"), "contract.exe")
    }
    res_bad = client.post(
        "/api/review/upload",
        headers=headers,
        data=bad_data,
        content_type="multipart/form-data"
    )
    assert res_bad.status_code == 400


def test_auditor_upload_forbidden(client, auth_tokens):
    """Verifies that an Auditor attempting to upload a contract is rejected with 403 Forbidden."""
    headers = {"Authorization": f"Bearer {auth_tokens['auditor_token']}"}
    data = {
        "title": "Auditor Upload Attempt",
        "file": (io.BytesIO(b"Sample contract text for auditing purposes."), "audit_contract.txt")
    }
    res = client.post(
        "/api/review/upload",
        headers=headers,
        data=data,
        content_type="multipart/form-data"
    )
    assert res.status_code == 403
    payload = res.get_json()
    assert "Forbidden" in payload.get("error", "") or "authorized" in payload.get("error", "").lower()


def test_upload_validation_edge_cases(client, auth_tokens):
    """Verifies upload validation: missing file, empty filename, 0-byte file, oversized file."""
    headers = {"Authorization": f"Bearer {auth_tokens['client_token']}"}

    # 1. Missing file part entirely
    res_no_file = client.post("/api/review/upload", headers=headers, data={"title": "No File"})
    assert res_no_file.status_code == 400
    assert "file" in res_no_file.get_json()["error"].lower()

    # 2. Empty filename
    res_empty_fn = client.post(
        "/api/review/upload",
        headers=headers,
        data={"file": (io.BytesIO(b"Valid content"), "")},
        content_type="multipart/form-data"
    )
    assert res_empty_fn.status_code == 400
    assert "Empty filename" in res_empty_fn.get_json()["error"]

    # 3. 0-byte empty file
    res_zero_bytes = client.post(
        "/api/review/upload",
        headers=headers,
        data={"file": (io.BytesIO(b""), "empty.txt")},
        content_type="multipart/form-data"
    )
    assert res_zero_bytes.status_code == 400
    assert "Uploaded file is empty" in res_zero_bytes.get_json()["error"]

    # 4. Oversized file (exceeds IngestionConfig().max_file_size_bytes)
    from src.ingestion.config import IngestionConfig
    max_size = IngestionConfig().max_file_size_bytes
    oversized_data = b"X" * (max_size + 1024)
    res_oversized = client.post(
        "/api/review/upload",
        headers=headers,
        data={"file": (io.BytesIO(oversized_data), "too_large.txt")},
        content_type="multipart/form-data"
    )
    assert res_oversized.status_code == 400
    assert "exceeds" in res_oversized.get_json()["error"].lower() or "limit" in res_oversized.get_json()["error"].lower()


def test_client_role_tampering_rejected_by_backend(client, auth_tokens):
    """Verifies that changing frontend role state has zero authority; backend RBAC rejects unauthorized requests."""
    client_headers = {"Authorization": f"Bearer {auth_tokens['client_token']}"}

    # Client attempts to access supervisor advocate listing
    res_advocates = client.get("/api/review/advocates/eligible", headers=client_headers)
    assert res_advocates.status_code == 403

    # Client attempts to reassign lawyer
    res_assign = client.post(
        "/api/review/rev-nonexistent/assign",
        headers=client_headers,
        json={"lawyer_id": auth_tokens["lawyer_id"]}
    )
    assert res_assign.status_code == 403

    # Client attempts to submit lawyer substantive decision
    res_decide = client.post(
        "/api/review/rev-nonexistent/decision",
        headers=client_headers,
        json={"clause_id": "cl-1", "decision_type": "ACCEPTED", "rationale": "Attempting client override"}
    )
    assert res_decide.status_code == 403


def test_repeated_upload_preserves_audit_chain(client, auth_tokens):
    """Verifies that repeated contract uploads hydrate the audit store and preserve SHA-256 hash chain continuity."""
    from src.persistence.models import AuditEventRecord

    headers = {"Authorization": f"Bearer {auth_tokens['client_token']}"}

    # Record the last event in the DB before uploads
    with get_db_session() as sess:
        initial_last_event = (
            sess.query(AuditEventRecord)
            .order_by(AuditEventRecord.created_at.desc(), AuditEventRecord.id.desc())
            .first()
        )
        initial_last_hash = initial_last_event.event_hash if initial_last_event else None
        initial_count = sess.query(AuditEventRecord).count()

    # Upload 1 (include uuid so it's fresh each run)
    u1 = str(uuid.uuid4())
    doc1 = (
        f"FIRST VERIFICATION CONTRACT {u1}\n\n"
        "1. CONFIDENTIALITY\n"
        "Each party agrees to maintain confidentiality.\n"
    ).encode("utf-8")
    res1 = client.post(
        "/api/review/upload",
        headers=headers,
        data={"file": (io.BytesIO(doc1), f"first_chain_{u1[:8]}.txt")},
        content_type="multipart/form-data"
    )
    assert res1.status_code == 201

    # Upload 2
    u2 = str(uuid.uuid4())
    doc2 = (
        f"SECOND VERIFICATION CONTRACT {u2}\n\n"
        "1. INDEMNIFICATION\n"
        "The Provider shall indemnify the Customer against third party claims.\n"
    ).encode("utf-8")
    res2 = client.post(
        "/api/review/upload",
        headers=headers,
        data={"file": (io.BytesIO(doc2), f"second_chain_{u2[:8]}.txt")},
        content_type="multipart/form-data"
    )
    assert res2.status_code == 201

    # Verify audit event chain in database for newly added events
    with get_db_session() as sess:
        all_events = (
            sess.query(AuditEventRecord)
            .order_by(AuditEventRecord.created_at.asc(), AuditEventRecord.id.asc())
            .all()
        )
        new_events = all_events[initial_count:]
        assert len(new_events) >= 8  # 4 events per upload

        # Verify first new event chained to the initial last event hash
        if initial_last_hash:
            assert new_events[0].previous_event_hash == initial_last_hash

        # Verify cryptographic hash linking between all consecutive new events
        for i in range(1, len(new_events)):
            assert new_events[i].previous_event_hash == new_events[i - 1].event_hash, (
                f"Broken link between new event {i-1} ({new_events[i-1].event_id}) "
                f"and new event {i} ({new_events[i].event_id})"
            )


def test_failed_upload_rollback(client, auth_tokens):
    """Verifies that if an error occurs during review initiation, the transaction is rolled back cleanly."""
    from unittest.mock import patch
    from src.persistence.models import DocumentRecord

    headers = {"Authorization": f"Bearer {auth_tokens['client_token']}"}
    fail_bytes = b"TRANSACTION ROLLBACK TEST CONTRACT\n\n1. SCOPE\nThis contract should be rolled back on failure."

    with patch("src.review.service.ReviewService.initiate_review", side_effect=RuntimeError("Simulated review initiation crash")):
        res = client.post(
            "/api/review/upload",
            headers=headers,
            data={"file": (io.BytesIO(fail_bytes), "rollback_test.txt")},
            content_type="multipart/form-data"
        )
        assert res.status_code == 500
        assert "Simulated review initiation crash" in res.get_json()["error"]

    # Verify that no document record was persisted with this filename
    with get_db_session() as sess:
        doc = sess.query(DocumentRecord).filter_by(sanitized_filename="rollback_test.txt").first()
        assert doc is None, "Document record was not rolled back after review initiation failure!"

