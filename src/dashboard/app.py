import os
import sys
import json
import uuid
import hashlib
from flask import Flask, jsonify, render_template_string, Response, request

from .data_loader import DashboardDataLoader
from src.auth.routes import auth_bp
from src.legal_sources.routes import legal_bp
from src.review.routes import review_bp
from src.reporting.routes import reporting_bp
from src.annotation.routes import annotation_bp
from src.persistence.database import init_db, get_db_session
from src.auth.csrf import validate_csrf_request, generate_csrf_token
from src.auth.config import AuthConfig
from src.audit.store import AuditStore
from src.audit.logger import AuditLogger
from src.audit.provenance import EventType, ActorType

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
app.register_blueprint(auth_bp)
app.register_blueprint(legal_bp)
app.register_blueprint(review_bp)
app.register_blueprint(reporting_bp)
app.register_blueprint(annotation_bp)

@app.before_request
def csrf_protect_hook():
    is_valid, err_msg = validate_csrf_request(request)
    if not is_valid:
        try:
            store = AuditStore()
            logger = AuditLogger(store)
            logger.log_event(
                event_type=EventType.CSRF_VALIDATION_FAILED,
                actor_type=ActorType.ANONYMOUS,
                actor_id=request.remote_addr or "unknown",
                payload={
                    "path": request.path,
                    "method": request.method,
                    "error": err_msg
                }
            )
        except Exception:
            pass
        return jsonify({
            "error": err_msg or "CSRF validation failed",
            "status_code": 403
        }), 403

@app.after_request
def csrf_cookie_hook(response):
    cfg = AuthConfig()
    if cfg.csrf_cookie_name not in request.cookies:
        csrf_tok = generate_csrf_token()
        response.set_cookie(
            cfg.csrf_cookie_name,
            csrf_tok,
            httponly=False,
            secure=cfg.cookie_secure,
            samesite=cfg.cookie_samesite,
            path=cfg.cookie_path
        )
    return response

loader = DashboardDataLoader()
init_db()

def seed_demo_environment():
    """Seeds standard demo accounts and a realistic demo contract with segmented clauses and evidence."""
    try:
        from src.persistence.models import (
            UserRecord, DocumentRecord, ExtractedTextSnapshot, SegmentRecord,
            ReviewRecord, ClauseFindingRecord, UserRole, AccountStatus, AdvocateStatus,
            ReviewStatus, FindingOrigin, LawyerDecisionType
        )
        from src.auth.password import PasswordManager

        pwd_mgr = PasswordManager()

        with get_db_session() as session:
            demo_users = [
                {
                    "email": "advocate@legal.in",
                    "role": UserRole.LAWYER.value,
                    "name": "Adv. Priya Sharma",
                    "advocate_status": AdvocateStatus.VERIFIED.value,
                    "bar_id": "D/1429/2014",
                    "council": "Bar Council of Delhi",
                    "year": 2014,
                    "password": "LegalTech2026!"
                },
                {
                    "email": "client@enterprise.in",
                    "role": UserRole.CLIENT.value,
                    "name": "Vikram Patel (General Counsel, TechCorp)",
                    "advocate_status": AdvocateStatus.NOT_APPLICABLE.value,
                    "bar_id": None,
                    "council": None,
                    "year": None,
                    "password": "ClientTech2026!"
                },
                {
                    "email": "supervisor@legal.in",
                    "role": UserRole.SUPERVISING_LAWYER.value,
                    "name": "Adv. Rajeshwar Rao (Senior Partner)",
                    "advocate_status": AdvocateStatus.VERIFIED.value,
                    "bar_id": "MH/3811/2005",
                    "council": "Bar Council of Maharashtra & Goa",
                    "year": 2005,
                    "password": "SuperTech2026!"
                },
                {
                    "email": "auditor@governance.in",
                    "role": UserRole.AUDITOR.value,
                    "name": "Deepa Narayanan (Compliance Auditor)",
                    "advocate_status": AdvocateStatus.NOT_APPLICABLE.value,
                    "bar_id": None,
                    "council": None,
                    "year": None,
                    "password": "AuditTech2026!"
                }
            ]

            user_map = {}
            for u in demo_users:
                existing = session.query(UserRecord).filter_by(email=u["email"]).first()
                if not existing:
                    hashed = pwd_mgr.hash_password(u["password"])
                    user = UserRecord(
                        id=str(uuid.uuid4()),
                        email=u["email"],
                        password_hash=hashed,
                        role=u["role"],
                        account_status=AccountStatus.ACTIVE.value,
                        advocate_status=u["advocate_status"],
                        full_name=u["name"],
                        bar_enrolment_id=u["bar_id"],
                        state_bar_council=u["council"],
                        year_of_enrolment=u["year"]
                    )
                    session.add(user)
                    session.flush()
                    user_map[u["email"]] = user
                else:
                    user_map[u["email"]] = existing

            client_user = user_map.get("client@enterprise.in")
            advocate_user = user_map.get("advocate@legal.in")
            if client_user and advocate_user:
                existing_doc = session.query(DocumentRecord).filter_by(owner_id=client_user.id).first()
                if not existing_doc:
                    doc_id = str(uuid.uuid4())
                    filename = "Master_Software_Services_Agreement_2026.txt"
                    raw_text = (
                        "MASTER SOFTWARE AND CLOUD SERVICES AGREEMENT\n\n"
                        "1. DEFINITIONS AND SCOPE OF SERVICES\n"
                        "The Vendor agrees to provide enterprise contract analysis cloud services to Client subject to standard terms.\n\n"
                        "2. NON-COMPETE AND RESTRAINT OF TRADE\n"
                        "Neither party shall during the term of this Agreement and for a period of five (5) years following termination directly or indirectly engage in any competing software enterprise across India.\n\n"
                        "3. DATA PROTECTION AND CONFIDENTIALITY\n"
                        "The parties agree that all personal data processed under this agreement shall be handled strictly in compliance with applicable Indian law, including the Digital Personal Data Protection Act, 2023.\n\n"
                        "4. INDEMNITY AND LIMITATION OF LIABILITY\n"
                        "Vendor shall indemnify Client against all third-party intellectual property infringement claims. Aggregate liability shall be capped at the total fees paid during preceding 12 months.\n\n"
                        "5. GOVERNING LAW AND ARBITRATION\n"
                        "Any dispute arising out of or in connection with this agreement shall be settled through binding arbitration conducted in New Delhi under the Arbitration and Conciliation Act, 1996.\n"
                    )
                    content_sha = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
                    doc = DocumentRecord(
                        id=doc_id,
                        file_sha256=content_sha,
                        original_filename=filename,
                        sanitized_filename=filename,
                        mime_type="text/plain",
                        document_format="TXT",
                        file_size_bytes=len(raw_text.encode("utf-8")),
                        storage_path=f"data/contracts/{doc_id}.txt",
                        owner_id=client_user.id,
                        assigned_lawyer_id=advocate_user.id,
                        status="PROCESSED",
                        extraction_method="PLAIN_TEXT",
                        page_count=1,
                        char_count=len(raw_text)
                    )
                    session.add(doc)
                    session.flush()

                    snapshot = ExtractedTextSnapshot(
                        id=str(uuid.uuid4()),
                        document_id=doc_id,
                        raw_text=raw_text,
                        char_count=len(raw_text),
                        text_sha256=content_sha
                    )
                    session.add(snapshot)
                    session.flush()

                    clauses = [
                        ("1. DEFINITIONS AND SCOPE OF SERVICES", "The Vendor agrees to provide enterprise contract analysis cloud services to Client subject to standard terms."),
                        ("2. NON-COMPETE AND RESTRAINT OF TRADE", "Neither party shall during the term of this Agreement and for a period of five (5) years following termination directly or indirectly engage in any competing software enterprise across India."),
                        ("3. DATA PROTECTION AND CONFIDENTIALITY", "The parties agree that all personal data processed under this agreement shall be handled strictly in compliance with applicable Indian law, including the Digital Personal Data Protection Act, 2023."),
                        ("4. INDEMNITY AND LIMITATION OF LIABILITY", "Vendor shall indemnify Client against all third-party intellectual property infringement claims. Aggregate liability shall be capped at the total fees paid during preceding 12 months."),
                        ("5. GOVERNING LAW AND ARBITRATION", "Any dispute arising out of or in connection with this agreement shall be settled through binding arbitration conducted in New Delhi under the Arbitration and Conciliation Act, 1996.")
                    ]
                    segments = []
                    offset = 0
                    for idx, (heading, text) in enumerate(clauses):
                        start_pos = raw_text.find(text)
                        if start_pos == -1:
                            start_pos = offset
                        end_pos = start_pos + len(text)
                        seg_id = f"seg_{idx + 1}"
                        seg = SegmentRecord(
                            id=str(uuid.uuid4()),
                            document_id=doc_id,
                            segment_id=seg_id,
                            segment_type="CLAUSE",
                            text=text,
                            original_start=start_pos,
                            original_end=end_pos,
                            heading=heading,
                            numbering=str(idx + 1),
                            sequence=idx
                        )
                        session.add(seg)
                        segments.append(seg)
                    session.flush()

                    rev_id = str(uuid.uuid4())
                    review = ReviewRecord(
                        id=rev_id,
                        document_id=doc_id,
                        document_version=1,
                        status=ReviewStatus.IN_REVIEW.value,
                        assigned_lawyer_id=advocate_user.id
                    )
                    session.add(review)
                    session.flush()

                    finding = ClauseFindingRecord(
                        id=str(uuid.uuid4()),
                        review_id=rev_id,
                        document_id=doc_id,
                        segment_id=segments[1].segment_id,
                        document_version=1,
                        finding_origin=FindingOrigin.AI_GENERATED.value,
                        risk_label="Restraint of Trade / Section 27 ICA",
                        ai_confidence_score="0.92",
                        ai_observation="Post-termination 5-year non-compete restraint is prima facie void under Section 27 of the Indian Contract Act, 1872 unless falling within narrow goodwill exceptions.",
                        decision=LawyerDecisionType.ACCEPT_AI_OBSERVATION.value,
                        lawyer_rationale="Accepted. Under Indian law (Section 27, Indian Contract Act 1872; Percept D'Mark v. Zaheer Khan), post-employment and post-termination non-compete covenants are void and unenforceable in India.",
                        lawyer_notes="Advise client to replace with reasonable non-solicitation and strict NDA provisions.",
                        is_disclosed_to_client=True
                    )
                    session.add(finding)
                    session.commit()
    except Exception as e:
        print(f"Notice: Demo environment seeder note: {e}")

# Run demo seeding once on import/startup
seed_demo_environment()

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ContractRisk-XAI &mdash; Intelligent Contract Analysis &amp; Legal Review Platform</title>
  <link rel="icon" type="image/svg+xml" href="/static/img/favicon.svg">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/css/design_system.css">
  <script src="/static/js/dashboard.js" defer></script>
</head>
<body>

  <!-- ========================================================================= -->
  <!-- APPLICATION HEADER & NAVIGATION SHELL                                     -->
  <!-- ========================================================================= -->
  <header class="app-header" role="banner">
    <div class="header-container">
      <div class="brand-group">
        <a href="/" class="brand-link" aria-label="ContractRisk-XAI Home">
          <img src="/static/img/logo.svg" alt="ContractRisk-XAI Logo" class="brand-logo-img">
        </a>
      </div>

      <div class="header-actions">
        <div id="user-profile-badge" class="user-profile-badge" aria-label="Current User Profile">
          <span class="user-avatar" id="nav-user-avatar">&#9878;</span>
          <div class="user-meta">
            <span class="user-name" id="nav-user-name">Guest (Viewing)</span>
            <span class="user-role" id="nav-user-role">Demo Mode</span>
          </div>
        </div>

        <button class="btn btn-secondary btn-sm" id="btn-open-login" onclick="openLoginModal()" aria-haspopup="dialog">
          &#128273; Switch Role / Sign In
        </button>

        <button class="btn btn-secondary btn-sm" id="btn-logout" onclick="logoutUser()" style="display: none;">
          Logout
        </button>
      </div>
    </div>

    <!-- MAIN ROLE-BASED NAVIGATION BAR -->
    <div class="header-container nav-container">
      <nav class="nav-tabs" role="tablist" aria-label="Application Sections">
        <button class="nav-tab active" role="tab" aria-selected="true" aria-controls="tab-lawyer-workbench" onclick="switchTab('lawyer-workbench'); loadWorkbenchQueue();">
          Lawyer Workbench
        </button>
        <button class="nav-tab" role="tab" aria-selected="false" aria-controls="tab-client-workspace" onclick="switchTab('client-workspace'); loadClientWorkspace();">
          Client Workspace
        </button>
        <button class="nav-tab" role="tab" aria-selected="false" aria-controls="tab-overview" onclick="switchTab('overview')">
          Executive Overview
        </button>
        <button class="nav-tab" role="tab" aria-selected="false" aria-controls="tab-ledgar" onclick="switchTab('ledgar')">
          LEDGAR Multi-Label
        </button>
        <button class="nav-tab" role="tab" aria-selected="false" aria-controls="tab-contractnli" onclick="switchTab('contractnli')">
          ContractNLI Baseline
        </button>
        <button class="nav-tab" role="tab" aria-selected="false" aria-controls="tab-cases" onclick="switchTab('cases')">
          Error Cases &amp; Evidence
        </button>
        <button class="nav-tab" role="tab" aria-selected="false" aria-controls="tab-robustness" onclick="switchTab('robustness')">
          Robustness Benchmarks
        </button>
        <button class="nav-tab" role="tab" aria-selected="false" aria-controls="tab-taxonomy" onclick="switchTab('taxonomy')">
          Failure Taxonomy
        </button>
        <button class="nav-tab" role="tab" aria-selected="false" aria-controls="tab-audit" onclick="switchTab('audit'); loadAuditLogs();">
          Audit &amp; Compliance
        </button>
      </nav>
    </div>
  </header>

  <!-- ========================================================================= -->
  <!-- MAIN APPLICATION BODY                                                     -->
  <!-- ========================================================================= -->
  <main class="app-main" role="main">

    <!-- MANDATORY LEGAL NOTICE BANNER (Preserved for regulatory compliance) -->
    <div class="banner-legal-disclaimer" role="alert">
      <div class="disclaimer-icon" aria-hidden="true">&#9888;</div>
      <div>
        <strong>LEGAL SAFETY NOTICE &amp; ACADEMIC RESEARCH DISCLAIMER:</strong>
        <p style="margin-top: 0.25rem;">
          ContractRisk-XAI is an experimental LegalTech SaaS platform and computer science research benchmark. It is <strong>NOT a validated legal decision-maker</strong>. 
          Model predictions and gradient attribution spans represent statistical patterns and <strong>must not be interpreted as legal advice</strong>, verified rationales, or binding contract interpretations. All findings require independent qualified human attorney review under the Advocates Act, 1961.
        </p>
      </div>
    </div>

    <!-- ======================================================================= -->
    <!-- TAB: LAWYER WORKBENCH                                                   -->
    <!-- ======================================================================= -->
    <div id="tab-lawyer-workbench" class="tab-content active" role="tabpanel">
      
      <!-- Workbench Top Bar -->
      <div class="workbench-header-bar">
        <div>
          <h2>Advocate Review Workbench</h2>
          <p class="section-desc">
            Human-in-the-loop review queue, segmented clause inspection, authoritative Indian statutory evidence retrieval, and independent advocate decisions.
          </p>
        </div>

        <div class="controls-cluster">
          <label for="queue-status-filter" class="form-label" style="margin-bottom:0;">Filter State:</label>
          <select id="queue-status-filter" class="form-control" style="width: auto; padding: 0.35rem 0.75rem;" onchange="loadWorkbenchQueue()">
            <option value="">All Review States</option>
            <option value="AWAITING_LAWYER_ASSIGNMENT">Waiting for a lawyer</option>
            <option value="ASSIGNED">Lawyer assigned</option>
            <option value="IN_REVIEW">In Review</option>
            <option value="REVISION_REQUESTED">Revision Requested</option>
            <option value="CLIENT_RESPONSE_RECEIVED">Client Response Received</option>
            <option value="REVIEW_COMPLETED">Review Completed</option>
          </select>
          <button class="btn btn-secondary btn-sm" onclick="loadWorkbenchQueue()">&#8635; Refresh Queue</button>
        </div>
      </div>

      <!-- Workbench Layout Grid -->
      <div class="workbench-grid">
        
        <!-- Left: Work Queue -->
        <div class="card">
          <div class="card-title">
            <span>Assigned Review Queue</span>
            <span id="queue-count-badge" class="badge badge-info">0 Documents</span>
          </div>
          <div id="workbench-queue-list" class="queue-list" style="max-height: 580px; overflow-y: auto;">
            <p style="color: var(--text-muted); font-size: 0.85rem; padding: 1rem; text-align: center;">
              Loading review queue...
            </p>
          </div>
        </div>

        <!-- Right: Active Document Review & Evidence Inspector -->
        <div>
          <!-- Document Overview Strip -->
          <div id="wb-doc-header-card" class="card" style="margin-bottom: 1rem; display: none;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 1rem;">
              <div>
                <h3 id="wb-doc-title" style="font-size: 1.15rem; font-weight: 700; color: var(--navy-900);">Document Review</h3>
                <div style="display: flex; gap: 0.5rem; align-items: center; margin-top: 0.35rem; flex-wrap: wrap;">
                  <span id="wb-doc-status-badge" class="badge badge-info">IN_REVIEW</span>
                  <span id="wb-doc-version" class="code-pill">Version 1</span>
                  <span id="wb-doc-lawyer" style="font-size: 0.82rem; color: var(--slate-600);">Assigned: Advocate</span>
                </div>
              </div>

              <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                <button id="wb-screen-btn" class="btn btn-secondary btn-sm" onclick="triggerWorkbenchScreening()" title="Run or re-run core LegalBERT & statutory screening across all clauses">&#9881; Re-screen with AI</button>
                <button id="wb-assign-lawyer-btn" class="btn btn-secondary btn-sm" style="display: none;" onclick="openAssignLawyerModal()">Assign Advocate</button>
                <button class="btn btn-secondary btn-sm" onclick="openRevisionModal()">Propose Revision</button>
                <button class="btn btn-success btn-sm" onclick="openCompleteReviewModal()">Complete Review</button>
              </div>
            </div>

            <div class="banner-legal-disclaimer" style="margin-top: 0.75rem; padding: 0.5rem 0.75rem; font-size: 0.8rem;">
              <div><strong>Notice:</strong> This workbench reflects advocate assessment based on available statutory extracts. It does not constitute an automated legal certification.</div>
            </div>
          </div>

          <!-- Split Workbench: Clauses List & Evidence / Decisions -->
          <div id="wb-content-grid" class="workbench-split-grid" style="display: none;">
            
            <!-- Left Panel: Contract Clauses List -->
            <div class="card">
              <div class="card-title">
                <span>Contract Clauses</span>
                <span id="clause-count-badge" class="badge badge-info">0</span>
              </div>
              <p style="font-size: 0.8rem; color: var(--slate-500); margin-bottom: 0.5rem;">
                Select a clause to inspect AI observations and retrieve Indian statutory evidence:
              </p>
              <div id="wb-clause-list" class="clause-list" style="max-height: 480px; overflow-y: auto;">
                <!-- Populated dynamically -->
              </div>
            </div>

            <!-- Right Panel: Evidence & Decision Inspector -->
            <div class="card">
              <div class="card-title">
                <span>Indian Statutory Evidence</span>
                <span id="evidence-status-badge" class="badge badge-warn">Select Clause</span>
              </div>
              
              <div id="wb-evidence-panel" class="evidence-container">
                <p style="color: var(--slate-500); font-size: 0.85rem; padding: 1.5rem 0; text-align: center;">
                  Select a contract clause on the left to inspect verbatim Indian statutory extracts and record your assessment.
                </p>
              </div>

              <!-- Lawyer Decision Form Container -->
              <div id="wb-decision-form-container" style="display: none; border-top: 1px solid var(--border-color); padding-top: 1rem; margin-top: 1rem;">
                <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--navy-900); margin-bottom: 0.6rem;">
                  Record Lawyer Assessment
                </h4>

                <div class="form-group">
                  <label for="wb-decision-type" class="form-label">Lawyer Decision <span class="required-star">*</span></label>
                  <select id="wb-decision-type" class="form-control">
                    <option value="ACCEPT_AI_OBSERVATION">ACCEPT_AI_OBSERVATION &mdash; Affirm AI Risk</option>
                    <option value="CORRECT_AI_OBSERVATION">CORRECT_AI_OBSERVATION &mdash; Modify Finding</option>
                    <option value="REJECT_AI_OBSERVATION">REJECT_AI_OBSERVATION &mdash; Dismiss AI Finding</option>
                    <option value="NEEDS_MORE_EVIDENCE">NEEDS_MORE_EVIDENCE &mdash; Require Additional Precedents</option>
                    <option value="NOT_APPLICABLE_TO_REVIEW">NOT_APPLICABLE_TO_REVIEW &mdash; Standard Clause</option>
                    <option value="REQUIRES_CLIENT_CLARIFICATION">REQUIRES_CLIENT_CLARIFICATION &mdash; Client Clarification</option>
                  </select>
                </div>

                <div class="form-group">
                  <label for="wb-decision-rationale" class="form-label">Substantive Lawyer Rationale <span class="required-star">*</span></label>
                  <textarea id="wb-decision-rationale" class="form-control" rows="2" placeholder="Required substantive legal rationale supporting this determination..."></textarea>
                </div>

                <div class="form-group">
                  <label for="wb-decision-notes" class="form-label">
                    Internal Lawyer Notes <span style="font-size: 0.75rem; color: var(--slate-500);">&#128274; Strictly Confidential</span>
                  </label>
                  <textarea id="wb-decision-notes" class="form-control" rows="2" placeholder="Private internal advocate notes (never disclosed to client)..."></textarea>
                </div>

                <div class="form-group" style="display: flex; align-items: center; gap: 0.5rem;">
                  <input type="checkbox" id="wb-disclose-check">
                  <label for="wb-disclose-check" style="font-size: 0.82rem; color: var(--slate-700); cursor: pointer;">
                    Disclose finding and legal recommendation to Client Workspace
                  </label>
                </div>

                <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                  <button class="btn btn-primary" onclick="submitLawyerDecision()">Record Decision</button>
                  <button class="btn btn-secondary" onclick="openAuthorFindingModal()">+ Author Finding</button>
                </div>
              </div>
            </div>

          </div>

          <!-- Comments & Clarifications Section -->
          <div id="wb-comments-card" class="card" style="margin-top: 1rem; display: none;">
            <div class="card-title">
              <span>Review Communications &amp; Clarifications</span>
              <span id="comment-count-badge" class="badge badge-info">0</span>
            </div>
            
            <div id="wb-comment-thread" class="comments-thread" style="max-height: 220px; overflow-y: auto; margin-bottom: 0.75rem;">
              <!-- Comments dynamically rendered -->
            </div>

            <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
              <input type="text" id="wb-comment-input" class="form-control" style="flex: 1;" placeholder="Write a note or clarification request...">
              <select id="wb-comment-vis" class="form-control" style="width: auto;">
                <option value="INTERNAL_LAWYER_ONLY">&#128274; Internal Lawyer Only</option>
                <option value="CLIENT_VISIBLE">&#128065; Client Visible</option>
                <option value="CLARIFICATION_REQUEST">&#10067; Clarification Request</option>
              </select>
              <button class="btn btn-primary" onclick="postWorkbenchComment()">Post</button>
            </div>
          </div>

          <!-- Reports & Feedback Panel -->
          <div id="wb-report-card" class="card" style="margin-top: 1rem; display: none;">
            <div class="card-title">
              <span>Final Lawyer-Reviewed Reports (Task 034)</span>
              <span id="wb-report-status-badge" class="badge badge-info">Eligibility Checking</span>
            </div>
            <p style="font-size: 0.85rem; color: var(--slate-600); margin-bottom: 0.75rem;">
              Final client reports require REVIEW_COMPLETED status, recorded lawyer rationales on all findings, and 0 unresolved client clarifications.
            </p>

            <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem;">
              <button id="wb-generate-report-btn" class="btn btn-primary" onclick="generateFinalReport()">
                &#128196; Generate Final Client Report (PDF)
              </button>
              <button class="btn btn-secondary" onclick="previewDraftReport()">
                &#128065; Preview Draft Report
              </button>
            </div>

            <div style="border-top: 1px solid var(--border-color); padding-top: 0.75rem; margin-top: 0.5rem;">
              <h4 style="font-size: 0.9rem; font-weight: 700; color: var(--navy-900); margin-bottom: 0.4rem;">
                Issued Reports &amp; Version History
              </h4>
              <div id="wb-reports-history" style="font-size: 0.82rem; color: var(--slate-600);">
                <p style="color: var(--slate-500);">No reports generated for this review yet.</p>
              </div>
            </div>

            <div style="border-top: 1px solid var(--border-color); padding-top: 0.75rem; margin-top: 0.75rem;">
              <h4 style="font-size: 0.9rem; font-weight: 700; color: var(--navy-900); margin-bottom: 0.4rem;">
                Client Feedback &amp; Follow-up Actions
              </h4>
              <div id="wb-feedback-list" style="font-size: 0.82rem; color: var(--slate-600);">
                <p style="color: var(--slate-500);">No client feedback submitted yet.</p>
              </div>
            </div>
          </div>

        </div>
      </div>
    </div>

    <!-- ======================================================================= -->
    <!-- TAB: CLIENT WORKSPACE                                                   -->
    <!-- ======================================================================= -->
    <div id="tab-client-workspace" class="tab-content" role="tabpanel">
      
      <div class="workbench-header-bar">
        <div>
          <h2>Client Contract Workspace</h2>
          <p class="section-desc">
            Upload new contracts, monitor legal review stages, view approved lawyer recommendations, access final signed PDF reports, and submit feedback.
          </p>
        </div>

        <div>
          <button class="btn btn-primary" onclick="openUploadModal()">
            &#128194; Upload New Contract
          </button>
        </div>
      </div>

      <div class="workbench-grid">
        
        <!-- Left: Client Contract Portfolio -->
        <div class="card">
          <div class="card-title">
            <span>My Contracts</span>
            <span id="client-contract-count" class="badge badge-info">0</span>
          </div>
          <div id="client-contract-list" class="queue-list" style="max-height: 540px; overflow-y: auto;">
            <p style="color: var(--slate-500); font-size: 0.85rem; padding: 1.5rem; text-align: center;">
              Loading contracts...
            </p>
          </div>
        </div>

        <!-- Right: Contract Details, Approved Findings, Reports & Feedback -->
        <div>
          <div id="client-doc-details" class="card" style="display: none;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 1rem;">
              <div>
                <h3 id="client-doc-title" style="font-size: 1.15rem; font-weight: 700; color: var(--navy-900);">Contract Title</h3>
                <div style="display: flex; gap: 0.5rem; align-items: center; margin-top: 0.35rem; flex-wrap: wrap;">
                  <span id="client-doc-status" class="badge badge-info">Status</span>
                  <span id="client-doc-lawyer" style="font-size: 0.85rem; color: var(--slate-600);">Assigned Advocate</span>
                </div>
              </div>
              <button class="btn btn-secondary btn-sm" onclick="openClientRevisionModal()">Submit Information / Changes</button>
            </div>

            <!-- Approved Findings -->
            <div style="margin-top: 1.25rem;">
              <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--navy-900); margin-bottom: 0.5rem;">
                Approved Legal Findings &amp; Recommendations
              </h4>
              <div id="client-approved-findings">
                <p style="color: var(--slate-500); font-size: 0.85rem;">No findings disclosed for client review yet.</p>
              </div>
            </div>

            <!-- Clarification Inquiries & Responses -->
            <div style="margin-top: 1.25rem; border-top: 1px solid var(--border-color); padding-top: 1rem;">
              <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--navy-900); margin-bottom: 0.5rem;">
                Lawyer Communications &amp; Clarification Requests
              </h4>
              <div id="client-comments-thread" class="comments-thread" style="max-height: 200px; overflow-y: auto; margin-bottom: 0.75rem;">
                <!-- Client comments -->
              </div>
              <div style="display: flex; gap: 0.5rem;">
                <input type="text" id="client-reply-input" class="form-control" placeholder="Respond to advocate clarification request...">
                <button class="btn btn-primary" onclick="submitClientClarificationReply()">Submit Response</button>
              </div>
            </div>

            <!-- Final Reports & Feedback Submission -->
            <div style="margin-top: 1.25rem; border-top: 1px solid var(--border-color); padding-top: 1rem;">
              <div class="card-title" style="margin-bottom: 0.5rem;">
                <span>Final Signed Reports &amp; Downloads</span>
                <span class="code-pill">SHA-256 Provenance</span>
              </div>
              <div id="client-reports-list" style="margin-bottom: 1rem;">
                <p style="color: var(--slate-500); font-size: 0.85rem;">No finalized lawyer report available yet.</p>
              </div>

              <!-- Structured Client Feedback Form (Task 034) -->
              <div id="client-feedback-form-box" style="display: none; background: var(--bg-main); padding: 1rem; border-radius: 8px; border: 1px solid var(--border-color); margin-top: 0.75rem;">
                <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--navy-900); margin-bottom: 0.5rem;">
                  Submit Report Feedback &amp; Follow-up Request
                </h4>
                
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem; margin-bottom: 0.75rem;">
                  <div>
                    <label for="cf-rating-overall" class="form-label" style="font-size: 0.78rem;">Overall Satisfaction (1-5)</label>
                    <select id="cf-rating-overall" class="form-control">
                      <option value="5">5 - Excellent</option>
                      <option value="4">4 - Good</option>
                      <option value="3">3 - Satisfactory</option>
                      <option value="2">2 - Needs Improvement</option>
                      <option value="1">1 - Poor</option>
                    </select>
                  </div>

                  <div>
                    <label for="cf-rating-clarity" class="form-label" style="font-size: 0.78rem;">Report Clarity (1-5)</label>
                    <select id="cf-rating-clarity" class="form-control">
                      <option value="5">5 - Very Clear</option>
                      <option value="4">4 - Clear</option>
                      <option value="3">3 - Moderate</option>
                      <option value="2">2 - Difficult</option>
                      <option value="1">1 - Confusing</option>
                    </select>
                  </div>

                  <div>
                    <label for="cf-rating-usefulness" class="form-label" style="font-size: 0.78rem;">Findings Usefulness (1-5)</label>
                    <select id="cf-rating-usefulness" class="form-control">
                      <option value="5">5 - Highly Useful</option>
                      <option value="4">4 - Useful</option>
                      <option value="3">3 - Somewhat Useful</option>
                      <option value="2">2 - Limited</option>
                      <option value="1">1 - Not Useful</option>
                    </select>
                  </div>
                </div>

                <div style="display: flex; gap: 1.5rem; margin-bottom: 0.75rem; font-size: 0.85rem;">
                  <label><input type="checkbox" id="cf-clarification-check"> Need Further Clarification</label>
                  <label><input type="checkbox" id="cf-followup-check"> Request Advocate Follow-up</label>
                </div>

                <div class="form-group">
                  <textarea id="cf-comments-input" class="form-control" rows="2" placeholder="Optional written feedback or questions for the reviewing advocate..."></textarea>
                </div>

                <button class="btn btn-primary btn-sm" onclick="submitReportFeedback()">Submit Feedback</button>
              </div>

              <!-- Client Feedback History -->
              <div id="client-feedback-history" style="margin-top: 1rem;">
                <!-- Populated dynamically -->
              </div>
            </div>

          </div>
        </div>

      </div>
    </div>

    <!-- ======================================================================= -->
    <!-- TAB 1: EXECUTIVE OVERVIEW (Preserving test strings)                     -->
    <!-- ======================================================================= -->
    <div id="tab-overview" class="tab-content" role="tabpanel">
      <div class="metrics-grid">
        <div class="stat-card">
          <div class="stat-label">Model Architecture</div>
          <div class="stat-val navy">LEGAL-BERT</div>
          <p class="stat-desc">Frozen 109.5M encoder + 9.5M linear head</p>
        </div>
        <div class="stat-card">
          <div class="stat-label">Held-Out Test Set</div>
          <div class="stat-val">87,956</div>
          <p class="stat-desc">Provisions (105,283 actual positive labels)</p>
        </div>
        <div class="stat-card">
          <div class="stat-label">Calibrated Threshold</div>
          <div class="stat-val green">&tau;* = 0.04</div>
          <p class="stat-desc">Selected via argmax(Val Micro-F1)</p>
        </div>
        <div class="stat-card">
          <div class="stat-label">Relative F1 Gain</div>
          <div class="stat-val green">+675.7%</div>
          <p class="stat-desc">vs uncalibrated &tau; = 0.50 baseline</p>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 1.5rem; margin-top: 1.5rem;">
        <div class="card">
          <div class="card-title">
            <span>Model Provenance &amp; Integrity</span>
            <span class="code-pill">SHA-256 Verified</span>
          </div>
          <table class="data-table">
            <tr><td>Model Weights File</td><td><span class="code-pill">results/models/.../final_model/model.safetensors</span></td></tr>
            <tr><td>File Size</td><td>476,116,436 bytes (454.06 MB)</td></tr>
            <tr><td>Weights SHA-256</td><td><span class="code-pill">7cd08d2c086f5046eb2b5ef85aa68fec84b5ce7ae3c12bef50c1baea096a8e5f</span></td></tr>
            <tr><td>Output Taxonomy</td><td>12,407 evaluated classes (bijective mapping verified)</td></tr>
            <tr><td>Training Split</td><td>Deterministic 10% contract subset (4,844 contracts, 67,776 provisions, seed 42)</td></tr>
            <tr><td>Split Overlap</td><td>0 contract overlap across Train/Val/Test (GroupShuffleSplit)</td></tr>
          </table>
        </div>

        <div class="card">
          <div class="card-title">
            <span>Evaluated Benchmark Datasets</span>
            <span class="code-pill">Strictly Decoupled</span>
          </div>
          <table class="data-table">
            <thead>
              <tr><th>Dataset</th><th>Task Type</th><th>Test Size</th><th>Compatibility</th></tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>LEDGAR</strong></td>
                <td>Multi-Label Provision</td>
                <td>87,956 provisions</td>
                <td><span class="badge badge-info">Primary Proposed</span></td>
              </tr>
              <tr>
                <td><strong>ContractNLI</strong></td>
                <td>Document 3-Class NLI</td>
                <td>2,091 doc pairs</td>
                <td><span class="code-pill">Independent Baseline</span></td>
              </tr>
              <tr>
                <td><strong>CUAD</strong></td>
                <td>Extractive QA / Span</td>
                <td>510 contracts</td>
                <td><span class="badge badge-warn">Task Mismatch (Audit Only)</span></td>
              </tr>
            </tbody>
          </table>
          <p style="font-size: 0.8rem; color: var(--slate-500); margin-top: 0.5rem;">
            * In accordance with Task 020 research safeguards, disparate dataset tasks are never combined into an artificial composite score.
          </p>
        </div>
      </div>
    </div>

    <!-- ======================================================================= -->
    <!-- TAB 2: LEDGAR MULTI-LABEL (Contains 12,699 and 58,947 for tests)         -->
    <!-- ======================================================================= -->
    <div id="tab-ledgar" class="tab-content" role="tabpanel">
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 1.5rem;">
        <div class="card">
          <div class="card-title">
            <span>Calibrated Threshold Operating Comparison</span>
            <span class="code-pill">Held-Out Test Split (87,956 provisions)</span>
          </div>
          <table class="data-table">
            <thead>
              <tr>
                <th>Metric</th>
                <th>Calibrated (&tau;* = 0.04)</th>
                <th>Baseline (&tau; = 0.50)</th>
                <th>Delta / Trade-off</th>
              </tr>
            </thead>
            <tbody>
              <tr><td><strong>True Positives (TP)</strong></td><td><strong style="color: var(--success); font-weight:700;">12,699</strong></td><td>989</td><td>+11,710 (12.83&times; recall gain)</td></tr>
              <tr><td><strong>False Positives (FP)</strong></td><td><strong style="color: var(--danger); font-weight:700;">58,947</strong></td><td>438</td><td>+58,509 (134.58&times; FP surge)</td></tr>
              <tr><td><strong>False Negatives (FN)</strong></td><td>92,584</td><td><strong style="color: var(--danger);">104,294</strong></td><td>-11,710 (99.06% missed at 0.50)</td></tr>
              <tr><td><strong>Micro-Precision</strong></td><td>0.1772 (17.72%)</td><td><strong>0.6931 (69.31%)</strong></td><td>-51.59% precision drop</td></tr>
              <tr><td><strong>Micro-Recall</strong></td><td><strong>0.1206 (12.06%)</strong></td><td>0.0094 (0.94%)</td><td>+11.12% absolute recall</td></tr>
              <tr><td><strong>Micro-F1</strong></td><td><strong style="color: var(--success);">0.1435</strong></td><td>0.0185</td><td><strong>+675.7% relative gain</strong></td></tr>
              <tr><td><strong>Macro-F1</strong></td><td>0.0045</td><td>0.0009</td><td>Collapsed by 11,298 tail classes</td></tr>
              <tr><td><strong>Weighted-F1</strong></td><td><strong>0.0937</strong></td><td>0.0141</td><td>+564.5% relative gain</td></tr>
            </tbody>
          </table>
        </div>

        <div class="card">
          <div class="card-title">
            <span>Training Subset Frequency Tier Breakdown</span>
            <span class="code-pill">12,608 Class Taxonomy</span>
          </div>
          <table class="data-table">
            <thead>
              <tr><th>Tier</th><th>Training Count</th><th>Class Count</th><th>Taxonomy %</th></tr>
            </thead>
            <tbody>
              <tr>
                <td><strong style="color: var(--danger);">Zero-Shot Unlearned</strong></td>
                <td>0 examples</td>
                <td><strong>2,833</strong></td>
                <td>22.47%</td>
              </tr>
              <tr>
                <td><strong style="color: var(--warning);">Extreme Tail (Rare)</strong></td>
                <td>1 &ndash; 9 examples</td>
                <td><strong>8,465</strong></td>
                <td>67.14%</td>
              </tr>
              <tr>
                <td><strong>Moderate Tail</strong></td>
                <td>10 &ndash; 99 examples</td>
                <td>1,208</td>
                <td>9.58%</td>
              </tr>
              <tr>
                <td><strong style="color: var(--success);">Head (Common)</strong></td>
                <td>&ge; 100 examples</td>
                <td>102</td>
                <td>0.81%</td>
              </tr>
            </tbody>
          </table>
          <div style="background: var(--bg-main); border-left: 3px solid var(--secondary-blue); padding: 0.75rem; border-radius: 4px; font-size: 0.82rem; margin-top: 1rem;">
            <strong>Macro-F1 Collapse Mechanism:</strong> Because 91.07% of the taxonomy (11,298 classes) has fewer than 10 training instances, over 90% of classes have near-zero recall. Unweighted Macro-F1 averages across all 12,407 classes equally, mathematically depressing the score to 0.0045 despite solid head-class performance.
          </div>
        </div>
      </div>
    </div>

    <!-- ======================================================================= -->
    <!-- TAB 3: CONTRACTNLI BASELINE                                             -->
    <!-- ======================================================================= -->
    <div id="tab-contractnli" class="tab-content" role="tabpanel">
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 1.5rem;">
        <div class="card">
          <div class="card-title">
            <span>ContractNLI 3-Class Confusion Matrix</span>
            <span class="code-pill">TF-IDF Linear SVM (2,091 test pairs)</span>
          </div>
          <table class="data-table">
            <thead>
              <tr>
                <th>True \\ Predicted</th>
                <th>Pred Contradiction</th>
                <th>Pred Entailment</th>
                <th>Pred NotMentioned</th>
                <th>Total Support</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Contradiction</strong></td>
                <td>81</td>
                <td style="color: var(--danger); font-weight:700;">90</td>
                <td>49</td>
                <td>220</td>
              </tr>
              <tr>
                <td><strong>Entailment</strong></td>
                <td>20</td>
                <td style="font-weight:700; color: var(--success);">834</td>
                <td>114</td>
                <td>968</td>
              </tr>
              <tr>
                <td><strong>NotMentioned</strong></td>
                <td>64</td>
                <td style="color: var(--danger); font-weight:700;">383</td>
                <td style="font-weight:700; color: var(--navy-900);">456</td>
                <td>903</td>
              </tr>
            </tbody>
          </table>
          <p style="font-size: 0.85rem; color: var(--slate-600); margin-top: 0.5rem;">
            Test Accuracy: <strong>65.57%</strong> | Macro-F1: <strong>0.5844</strong>
          </p>
        </div>

        <div class="card">
          <div class="card-title">
            <span>Dominant Confusion Error Mechanisms</span>
            <span class="code-pill">Bag-of-Words Fallacy</span>
          </div>
          <div style="background: var(--bg-main); border-left: 3px solid var(--danger); padding: 0.75rem; border-radius: 4px; font-size: 0.85rem; margin-bottom: 1rem;">
            <strong style="color: var(--danger);">1. NotMentioned &rarr; Entailment (383 instances, 42.41% error rate):</strong><br>
            Standard NDA boilerplate contains dense terms like "confidential", "information", and "disclose". High lexical n-gram overlap tricks the linear SVM into predicting Entailment even when the contract is completely silent on the hypothesis.
          </div>
          <div style="background: var(--bg-main); border-left: 3px solid var(--warning); padding: 0.75rem; border-radius: 4px; font-size: 0.85rem;">
            <strong style="color: var(--warning);">2. Contradiction &rarr; Entailment (90 instances, 40.91% error rate):</strong><br>
            Linear bag-of-words models lack sensitivity to scope qualifiers and negation markers ("except as expressly provided", "solely"). Shared topical words dominate, flipping contradictions into false entailments.
          </div>
        </div>
      </div>
    </div>

    <!-- ======================================================================= -->
    <!-- TAB 4: ERROR CASES & EVIDENCE                                           -->
    <!-- ======================================================================= -->
    <div id="tab-cases" class="tab-content" role="tabpanel">
      <div class="card" style="margin-bottom: 1.5rem;">
        <div class="card-title">
          <span>Case ERR_CASE_01: Taxonomy Granularity &amp; Morphological Collision</span>
          <span class="badge badge-warn">1 FP + 2 FN Penalty</span>
        </div>
        <div style="background: var(--bg-main); padding: 0.75rem; border-radius: 6px; font-style: italic; margin-bottom: 1rem; border-left: 3px solid var(--secondary-blue);">
          &ldquo;This Agreement shall be governed by, and construed in accordance with, the laws of the State of Delaware, without giving effect to any principles of conflicts of law.&rdquo;
        </div>
        <table class="data-table">
          <tr><td>Ground Truth Labels</td><td><span class="code-pill">applicable laws</span>, <span class="code-pill">governing law</span> (singular)</td></tr>
          <tr><td>Model Predicted (&tau;* = 0.04)</td><td><span class="code-pill" style="color: var(--danger);">governing laws</span> (plural)</td></tr>
          <tr><td>Root Cause</td><td>The 12,407 SEC taxonomy contains separate singular and plural classes. Exact-match binary scoring penalizes this correct semantic detection as 1 False Positive and 2 False Negatives.</td></tr>
        </table>
      </div>

      <div class="card">
        <div class="card-title">
          <span>Case ERR_CASE_04: Attribution Saliency Function-Word Bias</span>
          <span class="badge badge-danger">Explanation Artifact</span>
        </div>
        <div style="background: var(--bg-main); padding: 0.75rem; border-radius: 6px; font-style: italic; margin-bottom: 1rem; border-left: 3px solid var(--danger);">
          &ldquo;This Agreement shall be governed by, <strong style="color: var(--secondary-blue);">and</strong> construed in <strong style="color: var(--secondary-blue);">accordance</strong> with, <strong style="color: var(--secondary-blue);">the</strong> laws of the State of New York.&rdquo;
        </div>
        <table class="data-table">
          <tr><td>Target Label</td><td><span class="code-pill">applicable laws (ID 862)</span></td></tr>
          <tr><td>Top Attributed Spans</td><td>
            <span class="code-pill">"and" [37:40] (score 1.836)</span>,
            <span class="code-pill">"the" [83:86] (score 1.461)</span>,
            <span class="code-pill">"accordance" [54:64] (score 1.306)</span>
          </td></tr>
          <tr><td>Character Invariant</td><td><strong style="color: var(--success);">100% Exact Match</strong></td></tr>
          <tr><td>Legal Validity Analysis</td><td>Gradients highlight high-norm function words and syntax tokens rather than the operative jurisdiction ("State of New York"). Mathematical Gini sparsity (0.5633) does not equal legal validity.</td></tr>
        </table>
      </div>
    </div>

    <!-- ======================================================================= -->
    <!-- TAB 5: ROBUSTNESS BENCHMARKS                                            -->
    <!-- ======================================================================= -->
    <div id="tab-robustness" class="tab-content" role="tabpanel">
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem;">
        <div class="card">
          <div class="card-title">Input Perturbations</div>
          <table class="data-table">
            <thead><tr><th>Variant</th><th>Cosine Sim</th><th>Jaccard</th></tr></thead>
            <tbody>
              <tr><td>ORIGINAL</td><td>1.0000</td><td>1.0000</td></tr>
              <tr><td>UPPERCASE</td><td>1.0000</td><td>1.0000</td></tr>
              <tr><td>WHITESPACE</td><td>1.0000</td><td>1.0000</td></tr>
              <tr><td>TYPOGRAPHICAL</td><td>0.9706</td><td>0.8214</td></tr>
              <tr><td>ENTITY SWAP</td><td>0.9311</td><td>0.7500</td></tr>
            </tbody>
          </table>
        </div>

        <div class="card">
          <div class="card-title">Context Stress &amp; Invariants</div>
          <table class="data-table">
            <thead><tr><th>Test Scenario</th><th>Invariant</th><th>Status</th></tr></thead>
            <tbody>
              <tr><td>Budget Overflow (&gt;1000 tok)</td><td>Target preserved</td><td><strong style="color: var(--success);">&#10003; PASS</strong></td></tr>
              <tr><td>Giant Target (&gt;512 tok)</td><td>Flagged accurately</td><td><strong style="color: var(--success);">&#10003; PASS</strong></td></tr>
              <tr><td>Singleton Clause</td><td>Graceful degrade</td><td><strong style="color: var(--success);">&#10003; PASS</strong></td></tr>
              <tr><td>Cross-Doc Leak Attack</td><td>100% Blocked</td><td><strong style="color: var(--success);">&#10003; PASS</strong></td></tr>
            </tbody>
          </table>
        </div>

        <div class="card">
          <div class="card-title">Graph Robustness</div>
          <table class="data-table">
            <thead><tr><th>Stress Case</th><th>Outcome</th><th>Status</th></tr></thead>
            <tbody>
              <tr><td>Mutual Circular Citations</td><td>Zero recursion</td><td><strong style="color: var(--success);">&#10003; PASS</strong></td></tr>
              <tr><td>Dangling Citation (Sec 99.9)</td><td>UNRESOLVED status</td><td><strong style="color: var(--success);">&#10003; PASS</strong></td></tr>
              <tr><td>Document Partition Boundary</td><td>0 edge leakage</td><td><strong style="color: var(--success);">&#10003; PASS</strong></td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- ======================================================================= -->
    <!-- TAB 6: FAILURE TAXONOMY                                                 -->
    <!-- ======================================================================= -->
    <div id="tab-taxonomy" class="tab-content" role="tabpanel">
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 1.5rem;">
        <div class="card">
          <div class="card-title">
            <span>FM-01: Long-Tail Starvation &amp; Zero-Shot Collapse</span>
            <span class="badge badge-danger">Data / Taxonomy</span>
          </div>
          <p style="font-size: 0.88rem; color: var(--navy-900); margin-bottom: 0.5rem;">
            <strong>Affected Scope:</strong> 11,298 / 12,407 classes (91.07% of taxonomy).
          </p>
          <p style="font-size: 0.85rem; color: var(--slate-600);">
            2,833 classes have 0 training examples in the 10% subset, yielding 0.0% recall and causing Macro-F1 collapse (0.0045).
          </p>
        </div>

        <div class="card">
          <div class="card-title">
            <span>FM-02: Precision-Recall Threshold Dilemma</span>
            <span class="badge badge-warn">Calibration</span>
          </div>
          <p style="font-size: 0.88rem; color: var(--navy-900); margin-bottom: 0.5rem;">
            <strong>Affected Scope:</strong> Full Held-Out Test Split (87,956 provisions).
          </p>
          <p style="font-size: 0.85rem; color: var(--slate-600);">
            Calibrated operating point &tau;* = 0.04 recovers 12.83&times; recall over standard 0.50, but causes a 134.6&times; surge in false positives (58,947 FPs), capping micro-precision at 17.72%.
          </p>
        </div>

        <div class="card">
          <div class="card-title">
            <span>FM-03: Linear Probe Representation Bottleneck</span>
            <span class="badge badge-info">Model Architecture</span>
          </div>
          <p style="font-size: 0.88rem; color: var(--navy-900); margin-bottom: 0.5rem;">
            <strong>Affected Scope:</strong> Multi-Label Classification Head.
          </p>
          <p style="font-size: 0.85rem; color: var(--slate-600);">
            Frozen Legal-BERT backbone cannot adapt token embeddings to specific contractual nuances; the linear layer is restricted to generic pretrained features.
          </p>
        </div>

        <div class="card">
          <div class="card-title">
            <span>FM-04: Lexical Overlap Without Entailment</span>
            <span class="badge badge-danger">Baseline NLI</span>
          </div>
          <p style="font-size: 0.88rem; color: var(--navy-900); margin-bottom: 0.5rem;">
            <strong>Affected Scope:</strong> 42.41% of NotMentioned test instances.
          </p>
          <p style="font-size: 0.85rem; color: var(--slate-600);">
            Bag-of-words and n-gram TF-IDF baselines over-predict Entailment (62.5% of outputs) due to ubiquitous NDA boilerplate vocabulary.
          </p>
        </div>

        <div class="card">
          <div class="card-title">
            <span>FM-05: Saliency Noise &amp; Stopword Dominance</span>
            <span class="badge badge-warn">Explainability</span>
          </div>
          <p style="font-size: 0.88rem; color: var(--navy-900); margin-bottom: 0.5rem;">
            <strong>Affected Scope:</strong> Gradient &times; Input Saliency Maps.
          </p>
          <p style="font-size: 0.85rem; color: var(--slate-600);">
            Unsubtracted embedding gradients highlight frequent function words ("and", "the") and punctuation ("."), creating sparse explanations that lack legal validity.
          </p>
        </div>

        <div class="card">
          <div class="card-title">
            <span>FM-06: Taxonomy Morphological Clashing</span>
            <span class="badge badge-info">Taxonomy Design</span>
          </div>
          <p style="font-size: 0.88rem; color: var(--navy-900); margin-bottom: 0.5rem;">
            <strong>Affected Scope:</strong> Multi-Label Evaluation Accounting.
          </p>
          <p style="font-size: 0.85rem; color: var(--slate-600);">
            Singular vs plural variations ("governing law" vs "governing laws") penalize correct semantic detections as simultaneous false positives and false negatives under exact-match binary metrics.
          </p>
        </div>
      </div>
    </div>

    <!-- ======================================================================= -->
    <!-- TAB 7: AUDIT & COMPLIANCE PROVENANCE                                    -->
    <!-- ======================================================================= -->
    <div id="tab-audit" class="tab-content" role="tabpanel">
      <div class="workbench-header-bar">
        <div>
          <h2>Tamper-Evident Audit &amp; Compliance Trail</h2>
          <p class="section-desc">
            Cryptographic SHA-256 chained audit logs, authentication records, review decisions, and legal report provenance.
          </p>
        </div>
        <div class="controls-cluster">
          <input type="text" id="audit-search-filter" class="form-control" style="width: 260px;" placeholder="Filter events, actors, or hash..." oninput="filterAuditLogs()">
          <button class="btn btn-secondary btn-sm" id="btn-refresh-audit" onclick="loadAuditLogs()">&#8635; Refresh Audit Logs</button>
        </div>
      </div>

      <div class="card" style="margin-top: 1rem;">
        <div class="card-title">
          <span>Immutable Event Chain</span>
          <span id="audit-count-badge" class="badge badge-info">0 Events</span>
        </div>
        <div style="overflow-x: auto; margin-top: 0.75rem;">
          <table class="data-table" id="audit-table">
            <thead>
              <tr>
                <th>Timestamp (UTC)</th>
                <th>Event Type</th>
                <th>Actor</th>
                <th>Role</th>
                <th>Summary / Payload</th>
                <th>Entry Hash</th>
              </tr>
            </thead>
            <tbody id="audit-table-body">
              <tr><td colspan="6" style="text-align:center; color:var(--slate-500); padding: 1.5rem;">Loading audit trail...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

  </main>

  <!-- ========================================================================= -->
  <!-- MODAL: LOGIN / ROLE SWITCHER (Two-Column Layout)                           -->
  <!-- ========================================================================= -->
  <div id="login-modal" class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="login-title">
    <div class="modal-dialog modal-2col">
      <!-- Left Column: Legal Brand Art & Safeguards -->
      <div class="login-brand-col">
        <img src="/static/img/logo.svg" alt="ContractRisk-XAI Logo" class="login-brand-logo" style="max-height: 40px; width: auto; margin-bottom: 1.25rem; display: block;">
        <img src="/static/img/legal_hero.svg" alt="Legal Architecture" class="login-brand-img">
        <h3 class="login-brand-title">CONTRACTRISK-XAI</h3>
        <p class="login-brand-tagline">"Intelligent Contract Analysis. Human-Guided Legal Review."</p>
        
        <div style="margin-top: 1.5rem; text-align: left; font-size: 0.82rem; color: #cbd5e1; line-height: 1.6;">
          <p style="margin-bottom: 0.5rem;">&#10003; <strong>Strictly Human-in-the-Loop:</strong> AI assists; qualified advocates decide.</p>
          <p style="margin-bottom: 0.5rem;">&#10003; <strong>Statutory Verification:</strong> Matched to curated Indian legal extracts.</p>
          <p>&#10003; <strong>Tamper-Evident:</strong> Argon2id, SHA-256 chained audit trail.</p>
        </div>
      </div>

      <!-- Right Column: Role Switcher & Credentials Form -->
      <div class="login-form-col">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
          <h2 id="login-title" style="font-size: 1.3rem; font-weight: 700; color: var(--navy-900); margin: 0;">Sign In / Role Access</h2>
          <button class="btn btn-secondary btn-sm" onclick="closeLoginModal()" aria-label="Close dialog">&times;</button>
        </div>

        <p style="font-size: 0.85rem; color: var(--slate-600); margin-bottom: 1rem;">
          Select a demo persona for instant role-based access, or enter your credentials:
        </p>

        <!-- Role Quick Switcher Buttons -->
        <div class="role-switcher-grid">
          <button class="role-btn active" type="button" onclick="quickSelectRole('LAWYER')">
            <span class="role-icon">&#9878;</span>
            <span class="role-title">Advocate</span>
            <span class="role-sub">Review &amp; Evidence</span>
          </button>
          <button class="role-btn" type="button" onclick="quickSelectRole('CLIENT')">
            <span class="role-icon">&#128188;</span>
            <span class="role-title">Client</span>
            <span class="role-sub">Upload &amp; Reports</span>
          </button>
          <button class="role-btn" type="button" onclick="quickSelectRole('SUPERVISING_LAWYER')">
            <span class="role-icon">&#128084;</span>
            <span class="role-title">Supervisor</span>
            <span class="role-sub">Assignments &amp; QA</span>
          </button>
          <button class="role-btn" type="button" onclick="quickSelectRole('AUDITOR')">
            <span class="role-icon">&#128269;</span>
            <span class="role-title">Auditor</span>
            <span class="role-sub">Audit Provenance</span>
          </button>
        </div>

        <!-- Form fields -->
        <form id="auth-form" onsubmit="handleAuthSubmit(event)">
          <div class="form-group">
            <label for="auth-email" class="form-label">Email Address <span class="required-star">*</span></label>
            <input type="email" id="auth-email" class="form-control" required value="advocate@legal.in" autocomplete="username">
          </div>

          <div class="form-group">
            <label for="auth-password" class="form-label">Password <span class="required-star">*</span></label>
            <div style="position: relative; display: flex; align-items: center;">
              <input type="password" id="auth-password" class="form-control" required value="LegalTech2026!" autocomplete="current-password" style="padding-right: 2.75rem;">
              <button type="button" id="btn-toggle-password" onclick="togglePasswordVisibility()" aria-label="Toggle password visibility" style="position: absolute; right: 0.5rem; background: none; border: none; cursor: pointer; color: var(--slate-600); font-size: 1.05rem; padding: 0.25rem 0.4rem;">&#128065;</button>
            </div>
          </div>

          <div class="form-group" style="display: flex; align-items: center; gap: 0.5rem; margin-top: 0.5rem;">
            <input type="checkbox" id="auth-remember-me" style="width: auto; cursor: pointer;">
            <label for="auth-remember-me" style="font-size: 0.85rem; color: var(--slate-700); cursor: pointer; margin: 0;">Remember me on this workstation (14 days)</label>
          </div>

          <div id="auth-error-msg" class="banner-legal-disclaimer" style="display: none; border-color: var(--danger); background: #fef2f2; color: var(--danger); font-size: 0.82rem; margin-bottom: 1rem;">
          </div>

          <div style="display: flex; gap: 0.75rem; justify-content: flex-end; align-items: center; margin-top: 1.5rem;">
            <button type="button" class="btn btn-secondary" onclick="closeLoginModal()">Cancel</button>
            <button type="submit" id="btn-auth-submit" class="btn btn-primary">Sign In</button>
          </div>
        </form>
      </div>
    </div>
  </div>

  <!-- ========================================================================= -->
  <!-- MODAL: UPLOAD CONTRACT                                                    -->
  <!-- ========================================================================= -->
  <div id="upload-modal" class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="upload-title">
    <div class="modal-dialog">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <h3 id="upload-title" style="font-size: 1.25rem; font-weight: 700; color: var(--navy-900); margin: 0;">Upload Contract for Review</h3>
        <button class="btn btn-secondary btn-sm" onclick="closeUploadModal()" aria-label="Close dialog">&times;</button>
      </div>

      <p style="font-size: 0.85rem; color: var(--slate-600); margin-bottom: 1rem;">
        Upload an agreement in PDF, DOCX, or TXT format. The document will be cryptographically hashed, segmented into clauses, and queued for advocate review.
      </p>

      <form id="contract-upload-form" onsubmit="handleContractUpload(event)">
        <div class="form-group">
          <label for="upload-file-title" class="form-label">Contract Title / Identifier <span class="required-star">*</span></label>
          <input type="text" id="upload-file-title" class="form-control" placeholder="e.g. Master Services Agreement 2026" required>
        </div>

        <div class="form-group">
          <label class="form-label">Contract File (.pdf, .docx, .txt) <span class="required-star">*</span></label>
          <div class="upload-dropzone" id="upload-dropzone" onclick="document.getElementById('upload-file-input').click()">
            <div style="font-size: 2rem; color: var(--secondary-blue);">&#128196;</div>
            <p style="font-weight: 600; font-size: 0.9rem; color: var(--navy-900); margin-top: 0.5rem;">
              Click to select or drag and drop your contract file
            </p>
            <p style="font-size: 0.78rem; color: var(--slate-500); margin-top: 0.25rem;">
              Maximum 50MB. Multi-tenant cryptographic isolation verified.
            </p>
            <div id="selected-file-name" style="margin-top: 0.75rem; font-size: 0.85rem; font-weight: 600; color: var(--secondary-blue);"></div>
          </div>
          <input type="file" id="upload-file-input" style="display: none;" accept=".pdf,.docx,.txt" onchange="handleFileSelection(event)">
        </div>

        <div id="upload-status-msg" style="display: none; padding: 0.75rem; border-radius: 6px; font-size: 0.85rem; margin-bottom: 1rem;"></div>

        <div style="display: flex; gap: 0.75rem; justify-content: flex-end; margin-top: 1.25rem;">
          <button type="button" class="btn btn-secondary" onclick="closeUploadModal()">Cancel</button>
          <button type="submit" id="btn-upload-submit" class="btn btn-primary">Start Ingestion &amp; Review</button>
        </div>
      </form>
    </div>
  </div>

  <!-- ========================================================================= -->
  <!-- MODAL: DRAFT REPORT PREVIEW (Task 034)                                    -->
  <!-- ========================================================================= -->
  <div id="draft-report-modal" class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="draft-report-title">
    <div class="modal-dialog modal-lg">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <h3 id="draft-report-title" style="font-size: 1.25rem; font-weight: 700; color: var(--navy-900); margin: 0;">Draft Legal Review Report Preview</h3>
        <button class="btn btn-secondary btn-sm" onclick="closeDraftReportModal()" aria-label="Close dialog">&times;</button>
      </div>

      <div id="draft-report-content" style="max-height: 520px; overflow-y: auto; background: var(--bg-main); padding: 1rem; border-radius: 6px; font-size: 0.85rem;">
        Loading preview...
      </div>

      <div style="display: flex; justify-content: flex-end; margin-top: 1rem;">
        <button class="btn btn-secondary" onclick="closeDraftReportModal()">Close Preview</button>
      </div>
    </div>
  </div>

  <!-- ========================================================================= -->
  <!-- MODAL: PROPOSE DOCUMENT REVISION (Advocate Workbench)                    -->
  <!-- ========================================================================= -->
  <div id="revision-modal" class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="revision-modal-title">
    <div class="modal-dialog">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <h3 id="revision-modal-title" style="font-size: 1.2rem; font-weight: 700; color: var(--navy-900); margin: 0;">Propose Contract Revision</h3>
        <button class="btn btn-secondary btn-sm" onclick="closeRevisionModal()" aria-label="Close dialog">&times;</button>
      </div>
      <p style="font-size: 0.85rem; color: var(--slate-600); margin-bottom: 1rem;">
        Propose a versioned contract redline. Original uploaded agreement remains cryptographically preserved.
      </p>
      <form onsubmit="submitRevision(event)">
        <div class="form-group">
          <label for="rev-text" class="form-label">Revised Contract Text <span class="required-star">*</span></label>
          <textarea id="rev-text" class="form-control" rows="8" required placeholder="Paste or type revised contract text or proposed clause edits..."></textarea>
        </div>
        <div class="form-group">
          <label for="rev-reason" class="form-label">Substantive Revision Rationale <span class="required-star">*</span></label>
          <input type="text" id="rev-reason" class="form-control" required placeholder="e.g. Severed void post-termination non-compete under Section 27 ICA">
        </div>
        <div style="display: flex; gap: 0.75rem; justify-content: flex-end; margin-top: 1.25rem;">
          <button type="button" class="btn btn-secondary" onclick="closeRevisionModal()">Cancel</button>
          <button type="submit" id="btn-submit-revision" class="btn btn-primary">Submit Revision Proposal</button>
        </div>
      </form>
    </div>
  </div>

  <!-- ========================================================================= -->
  <!-- MODAL: COMPLETE REVIEW (Advocate Workbench)                                -->
  <!-- ========================================================================= -->
  <div id="complete-review-modal" class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="complete-review-title">
    <div class="modal-dialog modal-lg">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <h3 id="complete-review-title" style="font-size: 1.2rem; font-weight: 700; color: var(--navy-900); margin: 0;">Complete Legal Review</h3>
        <button class="btn btn-secondary btn-sm" onclick="closeCompleteReviewModal()" aria-label="Close dialog">&times;</button>
      </div>
      <p style="font-size: 0.85rem; color: var(--slate-600); margin-bottom: 1rem;">
        Finalize the advocate review workflow. Prerequisite: all clauses evaluated with substantive rationale and 0 open clarifications.
      </p>
      <form onsubmit="submitCompleteReview(event)">
        <div class="form-group">
          <label for="comp-summary" class="form-label">Executive Review Summary <span class="required-star">*</span></label>
          <textarea id="comp-summary" class="form-control" rows="3" required placeholder="Comprehensive legal review summary and overall risk evaluation..."></textarea>
        </div>
        <div class="form-group">
          <label for="comp-limitations" class="form-label">Outstanding Scope &amp; Statutory Limitations</label>
          <textarea id="comp-limitations" class="form-control" rows="2" placeholder="e.g. Review limited to Indian Contract Act 1872 and DPDP Act 2023 extracts; tax implications excluded."></textarea>
        </div>
        <div class="form-group">
          <label for="comp-unresolved" class="form-label">Unresolved Ambiguities / Questions</label>
          <input type="text" id="comp-unresolved" class="form-control" placeholder="Any remaining commercial questions for client counsel...">
        </div>
        <div class="form-group" style="display: flex; align-items: center; gap: 0.5rem;">
          <input type="checkbox" id="comp-action-required" style="width: auto;">
          <label for="comp-action-required" style="font-size: 0.85rem; color: var(--slate-700); cursor: pointer; margin: 0;">Further client action or renegotiation required</label>
        </div>
        <div class="form-group" style="background: var(--bg-card-subtle); padding: 0.85rem; border-radius: 6px; border: 1px solid var(--border-color); display: flex; align-items: flex-start; gap: 0.6rem; margin-top: 1rem;">
          <input type="checkbox" id="comp-disclaimer-check" required style="margin-top: 0.25rem;">
          <label for="comp-disclaimer-check" style="font-size: 0.82rem; color: var(--navy-900); cursor: pointer; margin: 0;">
            <strong>Statutory Compliance Confirmation:</strong> I confirm that this review reflects independent professional assessment by a qualified advocate enrolled with an Indian State Bar Council under the Advocates Act, 1961, and not an automated decision.
          </label>
        </div>
        <div style="display: flex; gap: 0.75rem; justify-content: flex-end; margin-top: 1.25rem;">
          <button type="button" class="btn btn-secondary" onclick="closeCompleteReviewModal()">Cancel</button>
          <button type="submit" id="btn-submit-complete-review" class="btn btn-success">Confirm &amp; Complete Review</button>
        </div>
      </form>
    </div>
  </div>

  <!-- ========================================================================= -->
  <!-- MODAL: AUTHOR INDEPENDENT FINDING (Advocate Workbench)                    -->
  <!-- ========================================================================= -->
  <div id="author-finding-modal" class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="author-finding-title">
    <div class="modal-dialog">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <h3 id="author-finding-title" style="font-size: 1.2rem; font-weight: 700; color: var(--navy-900); margin: 0;">Author Independent Legal Finding</h3>
        <button class="btn btn-secondary btn-sm" onclick="closeAuthorFindingModal()" aria-label="Close dialog">&times;</button>
      </div>
      <p style="font-size: 0.85rem; color: var(--slate-600); margin-bottom: 1rem;">
        Add an advocate-authored risk assessment on the currently selected clause. Origin will be recorded strictly as <span class="code-pill">LAWYER_AUTHORED</span>.
      </p>
      <form onsubmit="submitAuthorFinding(event)">
        <div class="form-group">
          <label for="af-risk-label" class="form-label">Risk Category / Heading <span class="required-star">*</span></label>
          <input type="text" id="af-risk-label" class="form-control" required placeholder="e.g. Restraint of Legal Proceedings / Section 28 ICA">
        </div>
        <div class="form-group">
          <label for="af-decision" class="form-label">Determination <span class="required-star">*</span></label>
          <select id="af-decision" class="form-control">
            <option value="ACCEPT_AI_OBSERVATION">ACCEPT_AI_OBSERVATION &mdash; Valid Risk Finding</option>
            <option value="CORRECT_AI_OBSERVATION">CORRECT_AI_OBSERVATION &mdash; Modified Assessment</option>
            <option value="NEEDS_MORE_EVIDENCE">NEEDS_MORE_EVIDENCE &mdash; Evidence Review</option>
            <option value="REQUIRES_CLIENT_CLARIFICATION">REQUIRES_CLIENT_CLARIFICATION &mdash; Client Clarification</option>
          </select>
        </div>
        <div class="form-group">
          <label for="af-observation" class="form-label">Advocate Observation <span class="required-star">*</span></label>
          <textarea id="af-observation" class="form-control" rows="3" required placeholder="Detailed factual and legal observation of the clause provision..."></textarea>
        </div>
        <div class="form-group">
          <label for="af-rationale" class="form-label">Substantive Legal Rationale <span class="required-star">*</span></label>
          <textarea id="af-rationale" class="form-control" rows="2" required placeholder="Statutory citations, precedents, and legal reasoning..."></textarea>
        </div>
        <div class="form-group">
          <label for="af-notes" class="form-label">Internal Lawyer Notes <span style="font-size: 0.75rem; color: var(--slate-500);">&#128274; Confidential</span></label>
          <textarea id="af-notes" class="form-control" rows="2" placeholder="Private internal advocate thoughts (never disclosed)..."></textarea>
        </div>
        <div class="form-group" style="display: flex; align-items: center; gap: 0.5rem;">
          <input type="checkbox" id="af-disclose-check" checked style="width: auto;">
          <label for="af-disclose-check" style="font-size: 0.82rem; color: var(--slate-700); cursor: pointer; margin: 0;">Disclose finding to Client Workspace</label>
        </div>
        <div style="display: flex; gap: 0.75rem; justify-content: flex-end; margin-top: 1.25rem;">
          <button type="button" class="btn btn-secondary" onclick="closeAuthorFindingModal()">Cancel</button>
          <button type="submit" id="btn-submit-author-finding" class="btn btn-primary">Save Finding</button>
        </div>
      </form>
    </div>
  </div>

  <!-- ========================================================================= -->
  <!-- MODAL: ASSIGN ADVOCATE (Supervisor Workspace)                             -->
  <!-- ========================================================================= -->
  <div id="assign-lawyer-modal" class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="assign-lawyer-title">
    <div class="modal-dialog">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <h3 id="assign-lawyer-title" style="font-size: 1.2rem; font-weight: 700; color: var(--navy-900); margin: 0;">Assign Review to Verified Advocate</h3>
        <button class="btn btn-secondary btn-sm" onclick="closeAssignLawyerModal()" aria-label="Close dialog">&times;</button>
      </div>
      <p style="font-size: 0.85rem; color: var(--slate-600); margin-bottom: 1rem;">
        Supervising Lawyer assignment. Only advocates with verified Bar Council credentials can be assigned to active reviews.
      </p>
      <form onsubmit="submitLawyerAssignment(event)">
        <div class="form-group">
          <label for="assign-lawyer-select" class="form-label">Select Verified Advocate <span class="required-star">*</span></label>
          <select id="assign-lawyer-select" class="form-control" required>
            <option value="">Loading eligible advocates...</option>
          </select>
        </div>
        <div class="form-group">
          <label for="assign-rationale" class="form-label">Supervisory Assignment Rationale</label>
          <input type="text" id="assign-rationale" class="form-control" placeholder="e.g. Assigned based on corporate commercial contracting expertise">
        </div>
        <div style="display: flex; gap: 0.75rem; justify-content: flex-end; margin-top: 1.25rem;">
          <button type="button" class="btn btn-secondary" onclick="closeAssignLawyerModal()">Cancel</button>
          <button type="submit" id="btn-submit-assignment" class="btn btn-primary">Confirm Assignment</button>
        </div>
      </form>
    </div>
  </div>

  <!-- ========================================================================= -->
  <!-- MODAL: CLIENT SUBMIT INFORMATION / CHANGES                                -->
  <!-- ========================================================================= -->
  <div id="client-revision-modal" class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="client-rev-title">
    <div class="modal-dialog">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
        <h3 id="client-rev-title" style="font-size: 1.2rem; font-weight: 700; color: var(--navy-900); margin: 0;">Submit Information or Changes</h3>
        <button class="btn btn-secondary btn-sm" onclick="closeClientRevisionModal()" aria-label="Close dialog">&times;</button>
      </div>
      <p style="font-size: 0.85rem; color: var(--slate-600); margin-bottom: 1rem;">
        Provide updated contract clauses or supplementary commercial facts to your reviewing advocate.
      </p>
      <form onsubmit="submitClientRevision(event)">
        <div class="form-group">
          <label for="client-rev-text" class="form-label">Updated Text / Information <span class="required-star">*</span></label>
          <textarea id="client-rev-text" class="form-control" rows="6" required placeholder="Enter updated contract wording, revised clauses, or detailed information..."></textarea>
        </div>
        <div class="form-group">
          <label for="client-rev-reason" class="form-label">Description of Changes <span class="required-star">*</span></label>
          <input type="text" id="client-rev-reason" class="form-control" required placeholder="e.g. Clarification regarding IP ownership and indemnity limits">
        </div>
        <div style="display: flex; gap: 0.75rem; justify-content: flex-end; margin-top: 1.25rem;">
          <button type="button" class="btn btn-secondary" onclick="closeClientRevisionModal()">Cancel</button>
          <button type="submit" id="btn-submit-client-revision" class="btn btn-primary">Submit to Advocate</button>
        </div>
      </form>
    </div>
  </div>

  <!-- Toast Notification Container -->
  <div id="toast-container" class="toast-container" aria-live="polite" aria-atomic="true"></div>

  <!-- ========================================================================= -->
  <!-- APPLICATION FOOTER                                                        -->
  <!-- ========================================================================= -->
  <footer class="app-footer" role="contentinfo">
    <div class="footer-container">
      <div>
        <strong>CONTRACTRISK-XAI</strong> &mdash; Intelligent Contract Analysis. Human-Guided Legal Review.
      </div>
      <div>
        <span>Manifest: <span class="code-pill">task023_error_analysis_manifest.json</span></span>
        <span style="margin-left: 1rem;">Operating Point: <span class="code-pill">&tau;* = 0.04</span></span>
      </div>
      <div style="font-size: 0.75rem; color: var(--slate-500);">
        Licensed for Academic &amp; LegalTech Evaluation &bull; Strictly Human-in-the-Loop
      </div>
    </div>
  </footer>

</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/api/provenance")
def api_provenance():
    return jsonify(loader.get_provenance())

@app.route("/api/ledgar")
def api_ledgar():
    return jsonify(loader.get_ledgar_data())

@app.route("/api/contractnli")
def api_contractnli():
    return jsonify(loader.get_contractnli_data())

@app.route("/api/cross_domain")
def api_cross_domain():
    return jsonify(loader.get_cross_domain_data())

@app.route("/api/robustness")
def api_robustness():
    return jsonify(loader.get_robustness_data())

@app.route("/api/cases")
def api_cases():
    return jsonify(loader.get_error_cases_and_taxonomy())

@app.route("/api/health")
def api_health():
    prov = loader.get_provenance()
    ledgar = loader.get_ledgar_data()
    cnli = loader.get_contractnli_data()
    rob = loader.get_robustness_data()
    
    all_ok = (
        prov.get("weights_file_exists", False) and
        ledgar.get("status") == "AVAILABLE" and
        cnli.get("status") == "AVAILABLE" and
        rob.get("status") == "AVAILABLE"
    )
    return jsonify({
        "status": "HEALTHY" if all_ok else "DEGRADED",
        "data_sources": {
            "model_weights": prov.get("weights_file_exists", False),
            "ledgar_calibrated_eval": ledgar.get("status") == "AVAILABLE",
            "contractnli_baseline": cnli.get("status") == "AVAILABLE",
            "robustness_manifest": rob.get("status") == "AVAILABLE"
        }
    })

def main():
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting ContractRisk-XAI Dashboard on port {port}...")
    app.run(host="127.0.0.1", port=port, debug=False)

if __name__ == "__main__":
    main()
