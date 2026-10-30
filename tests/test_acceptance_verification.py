import io
import json
import xml.etree.ElementTree as ET
import pytest
from src.dashboard.app import app
from src.persistence.database import get_db_session
from src.persistence.models import (
    UserRecord, DocumentRecord, ReviewRecord, SegmentRecord, ClauseFindingRecord,
    FinalReportRecord, AuditEventRecord, UserRole, AccountStatus, AdvocateStatus,
    ReviewStatus, LawyerDecisionType, FindingOrigin
)
from src.auth.token import TokenManager
from src.auth.password import PasswordManager
from src.auth.service import AuthService
from src.auth.csrf import generate_csrf_token

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def test_env():
    pwd_mgr = PasswordManager()
    token_mgr = TokenManager()

    with get_db_session() as sess:
        # Client User
        client_user = sess.query(UserRecord).filter_by(email="client_e2e_accept@legal.in").first()
        if not client_user:
            client_user = UserRecord(
                id="user-client-e2e-accept",
                email="client_e2e_accept@legal.in",
                password_hash=pwd_mgr.hash_password("Pass12345!"),
                role=UserRole.CLIENT.value,
                account_status=AccountStatus.ACTIVE.value,
                advocate_status=AdvocateStatus.NOT_APPLICABLE.value,
                full_name="E2E Acceptance Client"
            )
            sess.add(client_user)

        # Verified Advocate User
        advocate_user = sess.query(UserRecord).filter_by(email="adv_e2e_accept@legal.in").first()
        if not advocate_user:
            advocate_user = UserRecord(
                id="user-adv-e2e-accept",
                email="adv_e2e_accept@legal.in",
                password_hash=pwd_mgr.hash_password("Pass12345!"),
                role=UserRole.LAWYER.value,
                account_status=AccountStatus.ACTIVE.value,
                advocate_status=AdvocateStatus.VERIFIED.value,
                bar_enrolment_id="D/8888/2021",
                state_bar_council="Bar Council of Delhi",
                year_of_enrolment=2021,
                full_name="Adv. E2E Acceptance"
            )
            sess.add(advocate_user)

        # Supervising Lawyer User
        supervisor_user = sess.query(UserRecord).filter_by(email="sup_e2e_accept@legal.in").first()
        if not supervisor_user:
            supervisor_user = UserRecord(
                id="user-sup-e2e-accept",
                email="sup_e2e_accept@legal.in",
                password_hash=pwd_mgr.hash_password("Pass12345!"),
                role=UserRole.SUPERVISING_LAWYER.value,
                account_status=AccountStatus.ACTIVE.value,
                advocate_status=AdvocateStatus.VERIFIED.value,
                full_name="Supervisor E2E Acceptance"
            )
            sess.add(supervisor_user)

        # Auditor User
        auditor_user = sess.query(UserRecord).filter_by(email="aud_e2e_accept@legal.in").first()
        if not auditor_user:
            auditor_user = UserRecord(
                id="user-aud-e2e-accept",
                email="aud_e2e_accept@legal.in",
                password_hash=pwd_mgr.hash_password("Pass12345!"),
                role=UserRole.AUDITOR.value,
                account_status=AccountStatus.ACTIVE.value,
                advocate_status=AdvocateStatus.NOT_APPLICABLE.value,
                full_name="Auditor E2E Acceptance"
            )
            sess.add(auditor_user)

        c_id = client_user.id
        adv_id = advocate_user.id
        sup_id = supervisor_user.id
        aud_id = auditor_user.id

        sess.commit()

        client_tok = token_mgr.generate_token(client_user)
        adv_tok = token_mgr.generate_token(advocate_user)
        sup_tok = token_mgr.generate_token(supervisor_user)
        aud_tok = token_mgr.generate_token(auditor_user)

        return {
            "client_id": c_id,
            "advocate_id": adv_id,
            "supervisor_id": sup_id,
            "auditor_id": aud_id,
            "client_token": client_tok,
            "advocate_token": adv_tok,
            "supervisor_token": sup_tok,
            "auditor_token": aud_tok,
        }

# =============================================================================
# 1. LOGO & FAVICON INTEGRITY
# =============================================================================

def test_01_logo_and_favicon_load_and_xml_valid(client):
    """Criterion 1: Verify logo and favicon load correctly, have valid MIME types and XML."""
    # Favicon
    res_fav = client.get("/static/img/favicon.svg")
    assert res_fav.status_code == 200
    assert "image/svg+xml" in res_fav.headers.get("Content-Type", "")
    fav_xml = ET.fromstring(res_fav.get_data())
    assert fav_xml.tag.endswith("svg")

    # Logo
    res_logo = client.get("/static/img/logo.svg")
    assert res_logo.status_code == 200
    assert "image/svg+xml" in res_logo.headers.get("Content-Type", "")
    logo_xml = ET.fromstring(res_logo.get_data())
    assert logo_xml.tag.endswith("svg")

    # Verify HTML template embeds logo and favicon
    res_page = client.get("/")
    assert res_page.status_code == 200
    html = res_page.get_data(as_text=True)
    assert '<link rel="icon" type="image/svg+xml" href="/static/img/favicon.svg">' in html
    assert '<img src="/static/img/logo.svg" alt="ContractRisk-XAI Logo" class="brand-logo-img">' in html
    assert '<img src="/static/img/logo.svg" alt="ContractRisk-XAI Logo" class="login-brand-logo"' in html

# =============================================================================
# 2. VIEW ISOLATION & NO VERTICAL PAGE STACKING
# =============================================================================

def test_02_view_isolation_and_tab_scoping(client):
    """Criterion 2: Verify only selected navigation view is visible via strict CSS scoping."""
    res_css = client.get("/static/css/design_system.css")
    assert res_css.status_code == 200
    css = res_css.get_data(as_text=True)

    # Must have strict display: none !important for .tab-content
    assert ".tab-content {" in css
    assert "display: none !important;" in css
    assert ".tab-content.active {" in css
    assert "display: block !important;" in css

    # Verify exactly one tab has initial active class in INDEX_HTML
    res_page = client.get("/")
    html = res_page.get_data(as_text=True)
    assert 'class="tab-content active"' in html
    # Count occurrences of active tab content
    active_count = html.count('class="tab-content active"')
    assert active_count == 1, f"Expected exactly 1 initially active tab-content, found {active_count}"

# =============================================================================
# 3. LAWYER WORKBENCH QUEUE DIAGNOSIS (Populated, Empty, 401, 500)
# =============================================================================

def test_03_queue_states(client, test_env):
    """Criterion 3: Diagnose Lawyer Workbench review queue under all states."""
    adv_headers = {"Authorization": f"Bearer {test_env['advocate_token']}"}

    # 1. Populated / Filtered State
    res_q = client.get("/api/review/queue", headers=adv_headers)
    assert res_q.status_code == 200
    data = res_q.get_json()
    assert "reviews" in data
    assert "count" in data
    assert isinstance(data["reviews"], list)

    # 2. Empty State (Filter by impossible status)
    res_empty = client.get("/api/review/queue?status=NON_EXISTENT_STATUS", headers=adv_headers)
    assert res_empty.status_code == 200
    data_empty = res_empty.get_json()
    assert data_empty["count"] == 0
    assert len(data_empty["reviews"]) == 0

    # 3. Expired / Missing Session (401)
    res_unauth = client.get("/api/review/queue")
    assert res_unauth.status_code == 401

    # 4. RBAC Privilege Boundaries: Client Forbidden on Audit Logs (403)
    client_headers = {"Authorization": f"Bearer {test_env['client_token']}"}
    res_aud_forbidden = client.get("/api/audit/logs", headers=client_headers)
    assert res_aud_forbidden.status_code == 403

    # 5. RBAC Privilege Boundaries: Auditor Forbidden on Contract Upload (403)
    aud_headers = {"Authorization": f"Bearer {test_env['auditor_token']}"}
    res_up_forbidden = client.post(
        "/api/review/upload",
        headers=aud_headers,
        data={"file": (io.BytesIO(b"contract text"), "forbidden.txt")},
        content_type="multipart/form-data"
    )
    assert res_up_forbidden.status_code == 403

# =============================================================================
# 4. COMPLETE END-TO-END WORKFLOW
# =============================================================================

def test_04_end_to_end_lifecycle_workflow(client, test_env):
    """Criterion 4: Comprehensive end-to-end lifecycle execution."""
    client_headers = {"Authorization": f"Bearer {test_env['client_token']}"}
    adv_headers = {"Authorization": f"Bearer {test_env['advocate_token']}"}
    sup_headers = {"Authorization": f"Bearer {test_env['supervisor_token']}"}
    aud_headers = {"Authorization": f"Bearer {test_env['auditor_token']}"}

    # Stage 1: Client Contract Upload
    import uuid
    run_id = uuid.uuid4().hex[:8]
    contract_text = (
        f"CONTRACT IDENTIFIER: {run_id}\n"
        "SECTION 1. CONFIDENTIALITY.\n"
        "Each party shall protect proprietary information with reasonable care.\n\n"
        "SECTION 2. ARBITRATION AND GOVERNING LAW.\n"
        "Any dispute arising out of this Agreement shall be settled by arbitration in New Delhi "
        "in accordance with the Arbitration and Conciliation Act, 1996. The seat shall be New Delhi.\n\n"
        "SECTION 3. INDEMNITY.\n"
        "The vendor agrees to indemnify customer against third party IP infringement claims.\n"
    )
    upload_data = {
        "file": (io.BytesIO(contract_text.encode("utf-8")), f"Acceptance_Contract_{run_id}.txt")
    }
    res_up = client.post(
        "/api/review/upload",
        headers=client_headers,
        data=upload_data,
        content_type="multipart/form-data"
    )
    assert res_up.status_code == 201
    up_data = res_up.get_json()
    review_id = up_data["review_id"]
    document_id = up_data["document_id"]
    assert up_data["status"] in ["IN_REVIEW", "DOCUMENT_SUBMITTED", "AWAITING_LAWYER_ASSIGNMENT"]

    # Stage 2: Supervisor Assignment to Verified Advocate
    assign_payload = {
        "lawyer_id": test_env["advocate_id"],
        "rationale": "Assigned to Adv. E2E Acceptance based on arbitration and tech contract experience."
    }
    res_assign = client.post(
        f"/api/review/{review_id}/assign",
        headers=sup_headers,
        data=json.dumps(assign_payload),
        content_type="application/json"
    )
    assert res_assign.status_code == 200
    assert res_assign.get_json()["status"] == "ASSIGNED"

    # Stage 3: Lawyer Review and Determination
    # Get review detail
    res_detail = client.get(f"/api/review/{review_id}", headers=adv_headers)
    assert res_detail.status_code == 200
    rev_detail = res_detail.get_json()
    segments = rev_detail["segments"]
    assert len(segments) >= 1
    target_seg = segments[0]

    # Advocate records legal determination
    decision_payload = {
        "segment_id": target_seg["segment_id"],
        "decision": LawyerDecisionType.ACCEPT_AI_OBSERVATION.value,
        "rationale": "Confidentiality provision complies with standard trade secret protection under Indian contract jurisprudence.",
        "internal_notes": "Client should ensure definition excludes public domain data.",
        "is_disclosed_to_client": True
    }
    res_dec = client.post(
        f"/api/review/{review_id}/decision",
        headers=adv_headers,
        data=json.dumps(decision_payload),
        content_type="application/json"
    )
    assert res_dec.status_code == 200

    # Advocate authors independent finding
    finding_payload = {
        "segment_id": target_seg["segment_id"],
        "risk_label": "Trade Secret Scope",
        "lawyer_observation": "Definition of proprietary information should exclude standard open-source components.",
        "decision": LawyerDecisionType.CORRECT_AI_OBSERVATION.value,
        "rationale": "Prevent dispute over dual-licensed components under Copyright Act 1957.",
        "notes": "Advocate authored independent safeguard.",
        "is_disclosed_to_client": True
    }
    res_finding = client.post(
        f"/api/review/{review_id}/finding/create",
        headers=adv_headers,
        data=json.dumps(finding_payload),
        content_type="application/json"
    )
    assert res_finding.status_code == 201
    assert res_finding.get_json()["finding_origin"] == "LAWYER_AUTHORED"

    # Advocate records legal determinations for all remaining auto-generated clause findings
    for finding in rev_detail.get("findings", []):
        if finding["segment_id"] == target_seg["segment_id"]:
            continue
        res_dec_rem = client.post(
            f"/api/review/{review_id}/decision",
            headers=adv_headers,
            data=json.dumps({
                "segment_id": finding["segment_id"],
                "decision": LawyerDecisionType.ACCEPT_AI_OBSERVATION.value,
                "rationale": f"Statutory risk assessment for clause segment {finding['segment_id']} reviewed and verified under applicable Indian law.",
                "internal_notes": "Reviewed and verified by advocate.",
                "is_disclosed_to_client": True
            }),
            content_type="application/json"
        )
        assert res_dec_rem.status_code == 200

    # Stage 4: Client Clarification Request and Reply
    # Lawyer posts clarification request
    clarif_req = {
        "comment_text": "Please confirm whether proprietary software involves open-source GPL components.",
        "visibility": "CLARIFICATION_REQUEST"
    }
    res_req = client.post(
        f"/api/review/{review_id}/comment",
        headers=adv_headers,
        data=json.dumps(clarif_req),
        content_type="application/json"
    )
    assert res_req.status_code == 201
    clarif_id = res_req.get_json()["comment_id"]

    # Verify review completion is blocked while clarification is pending
    res_block = client.post(
        f"/api/review/{review_id}/complete",
        headers=adv_headers,
        data=json.dumps({"completion_summary": "Attempting premature completion"}),
        content_type="application/json"
    )
    assert res_block.status_code == 400
    err_msg = res_block.get_json()["error"].lower()
    assert "unresolved" in err_msg and "clarification" in err_msg

    # Client replies to clarification
    client_reply = {
        "comment_text": "Confirmed: No GPL code is included. Only permissive MIT licenses used.",
        "visibility": "CLIENT_VISIBLE"
    }
    res_reply = client.post(
        f"/api/review/{review_id}/comment",
        headers=client_headers,
        data=json.dumps(client_reply),
        content_type="application/json"
    )
    assert res_reply.status_code == 201

    # Advocate resolves all pending clarification requests
    res_comments = client.get(f"/api/review/{review_id}", headers=adv_headers)
    for c in res_comments.get_json().get("comments", []):
        if c.get("visibility") == "CLARIFICATION_REQUEST" and not c.get("is_resolved"):
            res_resolve = client.post(
                f"/api/review/{review_id}/comment/{c['id']}/resolve",
                headers=adv_headers,
                data=json.dumps({"resolution_notes": "Clarification resolved by advocate."}),
                content_type="application/json"
            )
            assert res_resolve.status_code == 200

    # Stage 5: Review Completion
    complete_payload = {
        "completion_summary": "Comprehensive legal review completed under applicable Indian commercial law (ICA 1872, ACA 1996)."
    }
    res_comp = client.post(
        f"/api/review/{review_id}/complete",
        headers=adv_headers,
        data=json.dumps(complete_payload),
        content_type="application/json"
    )
    assert res_comp.status_code == 200
    assert res_comp.get_json()["status"] == "REVIEW_COMPLETED"

    # Stage 6: Final Report Generation and Download
    res_gen = client.post(
        f"/api/reports/generate/{review_id}",
        headers=adv_headers
    )
    assert res_gen.status_code == 201
    rep_data = res_gen.get_json()
    assert "report_id" in rep_data
    report_id = rep_data["report_id"]
    assert "content_sha256" in rep_data
    assert "pdf_sha256" in rep_data

    # Client downloads PDF
    res_pdf = client.get(
        f"/api/reports/{report_id}/pdf",
        headers=client_headers
    )
    assert res_pdf.status_code == 200
    assert res_pdf.headers.get("Content-Type") == "application/pdf"
    assert len(res_pdf.get_data()) > 100

    # Stage 7: Client Feedback
    feedback_payload = {
        "overall_satisfaction": 5,
        "clarity_rating": 5,
        "usefulness_rating": 5,
        "needs_clarification": False,
        "follow_up_requested": False,
        "client_comments": "Excellent and thorough legal analysis. Clear risk guidance."
    }
    res_feed = client.post(
        f"/api/reports/{report_id}/feedback",
        headers=client_headers,
        data=json.dumps(feedback_payload),
        content_type="application/json"
    )
    assert res_feed.status_code == 201
    assert res_feed.get_json()["status"] == "SUBMITTED"

    # Stage 8: Authorized Audit Log Access
    res_audit = client.get("/api/audit/logs", headers=aud_headers)
    assert res_audit.status_code == 200
    audit_data = res_audit.get_json()
    assert len(audit_data["events"]) >= 5
    assert any(e["event_type"] == "REPORT_GENERATED" for e in audit_data["events"])
    assert any(e["event_type"] == "FEEDBACK_SUBMITTED" for e in audit_data["events"])

# =============================================================================
# 5. MODAL BEHAVIOR AND VALIDATION
# =============================================================================

def test_05_modal_definitions_and_keyboard_dismissal(client):
    """Criterion 5: Test modal presence, titles, cancel/close, and Escape handlers."""
    res = client.get("/")
    html = res.get_data(as_text=True)

    required_modals = [
        ("login-modal", "closeLoginModal()"),
        ("upload-modal", "closeUploadModal()"),
        ("revision-modal", "closeRevisionModal()"),
        ("complete-review-modal", "closeCompleteReviewModal()"),
        ("author-finding-modal", "closeAuthorFindingModal()"),
        ("assign-lawyer-modal", "closeAssignLawyerModal()"),
        ("client-revision-modal", "closeClientRevisionModal()"),
        ("draft-report-modal", "closeDraftReportModal()")
    ]

    for modal_id, close_fn in required_modals:
        assert f'id="{modal_id}"' in html, f"Modal {modal_id} missing from HTML"
        assert close_fn in html, f"Close function {close_fn} missing from HTML"

    # Check dashboard.js contains Escape key handler
    res_js = client.get("/static/js/dashboard.js")
    js = res_js.get_data(as_text=True)
    assert "Escape" in js
    assert "closeAllModals" in js or "activeModals" in js or "closeLoginModal" in js
