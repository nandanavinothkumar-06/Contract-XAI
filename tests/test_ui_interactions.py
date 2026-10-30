import json
import pytest
from src.dashboard.app import app
from src.persistence.database import get_db_session
from src.persistence.models import (
    UserRecord, DocumentRecord, ReviewRecord, SegmentRecord, ClauseFindingRecord,
    UserRole, AccountStatus, AdvocateStatus, ReviewStatus, LawyerDecisionType, FindingOrigin
)
from src.auth.token import TokenManager
from src.auth.password import PasswordManager

@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def seeded_env():
    pwd_mgr = PasswordManager()
    token_mgr = TokenManager()

    with get_db_session() as sess:
        # Client
        c = sess.query(UserRecord).filter_by(email="client_audit_test@legal.in").first()
        if not c:
            c = UserRecord(
                id="user-c-audit-99",
                email="client_audit_test@legal.in",
                password_hash=pwd_mgr.hash_password("Pass12345!"),
                role=UserRole.CLIENT.value,
                account_status=AccountStatus.ACTIVE.value,
                advocate_status=AdvocateStatus.NOT_APPLICABLE.value,
                full_name="Audit Test Client"
            )
            sess.add(c)

        # Advocate
        adv = sess.query(UserRecord).filter_by(email="adv_audit_test@legal.in").first()
        if not adv:
            adv = UserRecord(
                id="user-adv-audit-99",
                email="adv_audit_test@legal.in",
                password_hash=pwd_mgr.hash_password("Pass12345!"),
                role=UserRole.LAWYER.value,
                account_status=AccountStatus.ACTIVE.value,
                advocate_status=AdvocateStatus.VERIFIED.value,
                bar_enrolment_id="D/9999/2020",
                state_bar_council="Bar Council of Delhi",
                year_of_enrolment=2020,
                full_name="Adv. Audit Reviewer"
            )
            sess.add(adv)

        # Supervisor
        sup = sess.query(UserRecord).filter_by(email="sup_audit_test@legal.in").first()
        if not sup:
            sup = UserRecord(
                id="user-sup-audit-99",
                email="sup_audit_test@legal.in",
                password_hash=pwd_mgr.hash_password("Pass12345!"),
                role=UserRole.SUPERVISING_LAWYER.value,
                account_status=AccountStatus.ACTIVE.value,
                advocate_status=AdvocateStatus.VERIFIED.value,
                full_name="Supervising Partner Audit"
            )
            sess.add(sup)

        # Document
        doc = sess.query(DocumentRecord).filter_by(sanitized_filename="audit_test_contract.pdf").first()
        if not doc:
            doc = DocumentRecord(
                id="doc-audit-test-99",
                owner_id=c.id,
                assigned_lawyer_id=adv.id,
                original_filename="audit_test_contract.pdf",
                sanitized_filename="audit_test_contract.pdf",
                storage_path="/tmp/audit_test_contract.pdf",
                mime_type="application/pdf",
                document_format="PDF",
                file_size_bytes=1024,
                file_sha256="abc123hash"
            )
            sess.add(doc)
        else:
            doc.assigned_lawyer_id = adv.id

        sess.flush()

        # Segment
        seg = sess.query(SegmentRecord).filter_by(document_id=doc.id, segment_id="seg_audit_1").first()
        if not seg:
            seg = SegmentRecord(
                id="seg-rec-audit-1",
                document_id=doc.id,
                segment_id="seg_audit_1",
                segment_type="CLAUSE",
                text="The parties shall arbitrate all disputes in New Delhi under the Arbitration Act.",
                original_start=0,
                original_end=80,
                heading="Dispute Resolution",
                sequence=0
            )
            sess.add(seg)

        # Review
        rev = sess.query(ReviewRecord).filter_by(document_id=doc.id).first()
        if not rev:
            rev = ReviewRecord(
                id="rev-audit-test-99",
                document_id=doc.id,
                document_version=1,
                status=ReviewStatus.IN_REVIEW.value,
                assigned_lawyer_id=adv.id
            )
            sess.add(rev)

        sess.commit()

        c_tok = token_mgr.generate_token(c)
        adv_tok = token_mgr.generate_token(adv)
        sup_tok = token_mgr.generate_token(sup)

        return {
            "client_token": c_tok,
            "advocate_token": adv_tok,
            "supervisor_token": sup_tok,
            "client_id": c.id,
            "advocate_id": adv.id,
            "supervisor_id": sup.id,
            "review_id": rev.id,
            "document_id": doc.id,
            "segment_id": seg.segment_id
        }

def test_audit_tab_and_api_logs_rendered(client, seeded_env):
    """Verifies that the Audit & Compliance tab is present in HTML and API logs return successfully."""
    res_page = client.get("/")
    assert res_page.status_code == 200
    html = res_page.get_data(as_text=True)

    assert "Audit &amp; Compliance" in html
    assert 'id="tab-audit"' in html
    assert 'id="audit-table-body"' in html
    assert 'id="audit-search-filter"' in html

    # Verify audit endpoint as supervisor
    headers = {"Authorization": f"Bearer {seeded_env['supervisor_token']}"}
    res_logs = client.get("/api/audit/logs", headers=headers)
    assert res_logs.status_code == 200
    data = res_logs.get_json()
    assert "events" in data
    assert isinstance(data["events"], list)

def test_modal_accessibility_and_dom_elements(client):
    """Verifies all new modals exist with proper ARIA attributes, IDs, and close buttons."""
    res = client.get("/")
    html = res.get_data(as_text=True)

    modals = [
        ("revision-modal", "revision-modal-title", "Propose Contract Revision"),
        ("complete-review-modal", "complete-review-title", "Complete Legal Review"),
        ("author-finding-modal", "author-finding-title", "Author Independent Legal Finding"),
        ("assign-lawyer-modal", "assign-lawyer-title", "Assign Review to Verified Advocate"),
        ("client-revision-modal", "client-rev-title", "Submit Information or Changes")
    ]

    for modal_id, title_id, title_text in modals:
        assert f'id="{modal_id}"' in html
        assert f'aria-labelledby="{title_id}"' in html
        assert 'role="dialog"' in html
        assert 'aria-modal="true"' in html
        assert title_text in html

    # Toast container
    assert 'id="toast-container"' in html
    assert 'aria-live="polite"' in html

    # Password visibility toggle
    assert 'id="btn-toggle-password"' in html
    assert 'togglePasswordVisibility()' in html

def test_revision_modal_and_propose_endpoint(client, seeded_env):
    """Verifies proposing document revision via REST endpoint."""
    headers = {
        "Authorization": f"Bearer {seeded_env['advocate_token']}",
        "Content-Type": "application/json"
    }
    payload = {
        "revised_text": "The parties shall arbitrate in Mumbai under standard institutional rules.",
        "change_reason": "Relocated seat to Mumbai as mutually agreed."
    }
    res = client.post(
        f"/api/review/{seeded_env['review_id']}/revision/propose",
        headers=headers,
        data=json.dumps(payload)
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["version_number"] >= 2
    assert "revised_text_sha256" in data

def test_author_finding_modal_and_endpoint(client, seeded_env):
    """Verifies advocate can author an independent finding with origin strictly LAWYER_AUTHORED."""
    headers = {
        "Authorization": f"Bearer {seeded_env['advocate_token']}",
        "Content-Type": "application/json"
    }
    payload = {
        "segment_id": seeded_env["segment_id"],
        "risk_label": "Seat vs Venue Ambiguity",
        "lawyer_observation": "Clause designates New Delhi but omits arbitral institution rules.",
        "decision": "ACCEPT_AI_OBSERVATION",
        "rationale": "Under BALCO precedent, clear seat designation is crucial for supervisory jurisdiction.",
        "notes": "Recommend LCIA India or DIAC rules.",
        "is_disclosed_to_client": True
    }
    res = client.post(
        f"/api/review/{seeded_env['review_id']}/finding/create",
        headers=headers,
        data=json.dumps(payload)
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["finding_origin"] == "LAWYER_AUTHORED"
    assert data["segment_id"] == seeded_env["segment_id"]

def test_supervisor_assignment_modal_and_eligible_lawyers(client, seeded_env):
    """Verifies eligible advocate retrieval and supervisor assignment."""
    headers = {
        "Authorization": f"Bearer {seeded_env['supervisor_token']}",
        "Content-Type": "application/json"
    }
    # Eligible lawyers
    res_lawyers = client.get("/api/review/eligible-lawyers", headers=headers)
    assert res_lawyers.status_code == 200
    advocates = res_lawyers.get_json()["advocates"]
    assert len(advocates) >= 1
    assert any(a["advocate_status"] == "VERIFIED" for a in advocates)

    # Assign review
    assign_payload = {
        "lawyer_id": seeded_env["advocate_id"],
        "rationale": "Assigned due to arbitration expertise."
    }
    res_assign = client.post(
        f"/api/review/{seeded_env['review_id']}/assign",
        headers=headers,
        data=json.dumps(assign_payload)
    )
    assert res_assign.status_code == 200
    assert res_assign.get_json()["assigned_lawyer_id"] == seeded_env["advocate_id"]

def test_complete_review_modal_validation(client, seeded_env):
    """Verifies that completing a review mandates executive summary."""
    headers = {
        "Authorization": f"Bearer {seeded_env['advocate_token']}",
        "Content-Type": "application/json"
    }
    # Missing completion_summary
    res_fail = client.post(
        f"/api/review/{seeded_env['review_id']}/complete",
        headers=headers,
        data=json.dumps({})
    )
    assert res_fail.status_code == 400
    assert "completion_summary is mandatory" in res_fail.get_json()["error"]

def test_client_clarification_comment_and_feedback(client, seeded_env):
    """Verifies client can post clarification replies and submit feedback."""
    headers = {
        "Authorization": f"Bearer {seeded_env['client_token']}",
        "Content-Type": "application/json"
    }
    # Reply to lawyer
    reply_payload = {
        "comment_text": "We confirm New Delhi seat is acceptable to our corporate board.",
        "visibility": "CLIENT_VISIBLE"
    }
    res_reply = client.post(
        f"/api/review/{seeded_env['review_id']}/comment",
        headers=headers,
        data=json.dumps(reply_payload)
    )
    assert res_reply.status_code == 201
    assert res_reply.get_json()["visibility"] == "CLIENT_VISIBLE"

def test_draft_preview_modal_content_structure(client, seeded_env):
    """Verifies draft report preview endpoint returns proper DRAFT notice and data."""
    headers = {"Authorization": f"Bearer {seeded_env['advocate_token']}"}
    res = client.get(f"/api/reports/preview/{seeded_env['review_id']}", headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert "DRAFT" in data["notice"]
    assert "preview" in data
