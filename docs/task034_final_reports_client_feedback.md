# Task 034: Final Lawyer-Reviewed Reports and Client Feedback

**Project:** CONTRACTRISK-XAI  
**Phase:** Application Layer — Final Reports and Client Feedback  
**Status:** COMPLETE  
**Date:** 2026-10-15  

---

## 1. Objective & Scope

Task 034 completes the human-in-the-loop lifecycle of ContractRisk-XAI by providing an authorized lawyer review finalization workflow, verifiable client-facing report generation, publication-quality PDF compilation, and a structured client feedback and advocate response mechanism.

The implementation strictly integrates with:
- **Task 030:** Document ingestion, text snapshotting, segmentation, and relational persistence.
- **Task 031:** Authentication, token management, multi-tenant isolation, and advocate verification gates.
- **Task 032:** Authoritative Indian statutory corpus, citation generation, and lexical retrieval.
- **Task 033:** Collaborative Lawyer Review Workbench, clause finding decisions, comments, and document revisions.

**Legal & Safety Disclaimer:**
ContractRisk-XAI is an AI-assisted legal decision-support system operating under mandatory human advocate oversight. It does **not** certify legal compliance, replace a qualified lawyer, or provide guaranteed legal outcomes.

---

## 2. Report Eligibility Verification

A final client-facing report is never generated or released unless server-side validation verifies all mandatory prerequisites:

1. **Document & Version Identity:** The document exists, belongs to the expected client/workspace, and matches the document version reviewed.
2. **Review State:** The review record must have reached the `REVIEW_COMPLETED` state. Reopened (`REVIEW_REOPENED`) or in-progress (`IN_REVIEW`) reviews are rejected.
3. **Lawyer Authorization:** The actor must be the assigned advocate with verified credentials (`AdvocateStatus.VERIFIED`) or a Supervising Lawyer.
4. **Mandatory Completion Summary:** A non-empty completion summary authored by the reviewing advocate must be present.
5. **No Blockers:** 0 unresolved client clarification requests (`CLARIFICATION_REQUEST` with `is_resolved == False`).
6. **Finding Rationales:** Every released finding must have a recorded lawyer decision and a substantive advocate rationale.
7. **Draft Preview Separation:** Draft previews (`is_final = False`) are supported for inspection during review but are clearly labeled `DRAFT — PRELIMINARY ASSESSMENT — NOT A FINAL LAWYER REPORT`.

---

## 3. Report Structure & Content Segregation

The report payload is structured into segregated domains to guarantee that AI observations are never confused with legal conclusions:

### A. Report Identification & Provenance
- Unique Report ID and Report Number (e.g. `REP-ABCD1234-V1-9F2B8A`)
- Report Version (incremented upon superseding)
- Document ID, Version, and Original Filename
- Original File SHA-256 and Report Content SHA-256
- Assigned Reviewing Advocate (Full Name, Email, Bar Council Enrolment ID, State Bar Council)
- Review Completion and Report Generation Timestamps

### B. Executive Summary
- Contract description and review scope
- Findings counts breakdown (Accepted AI, Corrected, Rejected AI, Lawyer-Authored)
- Review outcome summary
- Outstanding limitations and unresolved questions

### C. Reviewed Findings & Legal Grounding
- Segment identifier, clause heading, numbering, and verbatim clause excerpt
- Finding origin (`AI_GENERATED` vs `LAWYER_AUTHORED`)
- AI observation and confidence score (when origin is AI)
- Advocate decision (`ACCEPT_AI_OBSERVATION`, `CORRECT_AI_OBSERVATION`, `REJECT_AI_OBSERVATION`, etc.)
- **Explicit Marking of Rejections:** Rejected AI observations are highlighted with `REJECTED BY ADVOCATE`, preventing false positive observations from being mistaken for approved risks.
- Advocate rationale
- Statutory grounding (Act name, Section number, provision text, corpus snapshot version, score semantics disclaimer)
- **Strict Privacy Rule:** Internal confidential advocate notes (`lawyer_notes`) and internal lawyer comments are strictly omitted from client reports.

### D. Mandatory Disclaimers
- **Mandatory Legal Disclaimer:** AI-assisted decision-support platform notice; no certification of legal validity or guarantee of enforceability.
- **Statutory Corpus Notice:** Discloses that Indian statutory citations are grounded in curated statutory extracts and do not constitute an exhaustive search of all Indian central/state legislation.
- **Score Semantics Notice:** BM25 and lexical retrieval relevance scores indicate token matching, not legal confidence or probability.

---

## 4. PDF Generation Architecture

Client-ready PDF documents are compiled using ReportLab:
- **Two-Pass NumberedCanvas:** Implements `ClientReportNumberedCanvas` rendering running headers and two-pass footers ("Page X of Y") with mandatory disclaimer notices.
- **Unicode & Indic Text Support:** Clean escaping and safe XML entity handling for Indian legal currency symbols (`₹`), em-dashes, and quotation marks.
- **Layout Flow:** PageBreak and KeepTogether flowables prevent splitting finding cards across arbitrary margins.
- **Artifact Persistence:** PDFs are stored in `data/reports/{report_number}.pdf` with SHA-256 checksums recorded in the database.

---

## 5. Report Versioning & Traceability

Reports are immutable once finalized:
- Generating a new report for an updated document version or revision marks the previous active report as `SUPERSEDED` (`ReportStatus.SUPERSEDED`).
- The superseded report preserves its unique ID, content hash, PDF file, timestamp, and supersession reason.
- Both active and historical superseded reports remain auditable by authorized users.

---

## 6. Client Feedback & Advocate Response Lifecycle

Structured client feedback is tied to the exact report version viewed by the client:

### A. Feedback Schema
- Overall satisfaction rating (1 to 5)
- Report clarity rating (1 to 5)
- Usefulness of findings rating (1 to 5)
- Clarification needed checkbox
- Follow-up requested checkbox
- Optional client written comments

### B. Lifecycle State Machine
```
[SUBMITTED] -----------> [ACKNOWLEDGED]
     |                         |
     v                         v
[RESPONSE_REQUIRED] ---> [RESPONDED] ---> [CLOSED]
```
- If `needs_clarification` or `follow_up_requested` is true, the initial state is `RESPONSE_REQUIRED`.
- Assigned advocate records responses. Client-visible responses are segregated from internal notes.
- Feedback status transitions are audited and timestamped.

---

## 7. Role-Based Access Control (RBAC)

- **CLIENT:**
  - Can view and download reports only for contracts they own (`owner_id == user.id`).
  - Can submit feedback only on their own final reports.
  - Can view only client-visible responses; internal lawyer notes are hidden.
- **LAWYER:**
  - Can access reports and feedback only for assigned reviews.
  - Can generate final reports only if verified (`AdvocateStatus.VERIFIED`).
  - Can respond to feedback and transition feedback states.
- **SUPERVISING_LAWYER:**
  - Supervisory oversight across all reviews, reports, version histories, and client feedback.
- **AUDITOR:**
  - Metadata and provenance inspection; denied raw contract body access.

---

## 8. Database & Persistence Model Additions

In `src/persistence/models.py`:
1. **`ReportStatus` Enum:** `DRAFT`, `FINAL`, `SUPERSEDED`.
2. **`FeedbackStatus` Enum:** `SUBMITTED`, `ACKNOWLEDGED`, `RESPONSE_REQUIRED`, `RESPONDED`, `CLOSED`.
3. **`FinalReportRecord` (`reports` table):**
   - `id`, `report_number`, `document_id`, `review_id`, `document_version`, `report_version`, `status`, `is_final`
   - `generated_by_id`, `generated_at`, `title`, `executive_summary`, `scope_of_review`, `review_outcome_summary`, `outstanding_limitations`, `disclaimer_text`, `statutory_corpus_version`
   - `report_payload_json` (immutable JSON snapshot), `content_sha256`
   - `pdf_storage_path`, `pdf_sha256`, `pdf_file_size_bytes`, `pdf_generated_at`
   - `superseded_at`, `superseded_by_id`, `supersession_reason`
4. **`ClientFeedbackRecord` (`client_feedback` table):**
   - `id`, `report_id`, `document_id`, `review_id`, `client_id`, `status`
   - `overall_satisfaction`, `clarity_rating`, `usefulness_rating`, `needs_clarification`, `follow_up_requested`, `client_comments`
   - `submitted_at`, `updated_at`
5. **`FeedbackResponseRecord` (`feedback_responses` table):**
   - `id`, `feedback_id`, `responder_id`, `responder_role`, `response_text`, `is_client_visible`, `internal_notes`, `created_at`

In `src/persistence/repository.py`:
- `create_report`, `get_report_by_id`, `get_report_by_number`, `get_reports_for_document`, `get_reports_for_review`, `get_active_final_report_for_review`, `supersede_report`, `update_report_pdf_artifact`
- `create_client_feedback`, `get_feedback_by_id`, `get_feedback_for_report`, `get_feedback_for_client`, `update_feedback_status`, `add_feedback_response`

---

## 9. Audit & Provenance Chaining

New audit event types added to `src/audit/provenance.py`:
- `REPORT_PREVIEWED`
- `REPORT_GENERATION_REQUESTED`
- `REPORT_GENERATED`
- `REPORT_GENERATION_FAILED`
- `REPORT_DOWNLOADED`
- `REPORT_SUPERSEDED`
- `FEEDBACK_SUBMITTED`
- `FEEDBACK_ACKNOWLEDGED`
- `FEEDBACK_RESPONSE_RECORDED`
- `FEEDBACK_CLOSED`

All events are cryptographically hash-chained (`event_hash = SHA256(previous_event_hash + payload)`).

---

## 10. REST API Endpoints

| Endpoint | Method | Role / Auth | Description |
|---|---|---|---|
| `/api/reports/generate/<review_id>` | `POST` | Verified Advocate / Supervisor | Validates prerequisites and generates final report + PDF |
| `/api/reports/preview/<review_id>` | `GET` | Assigned Lawyer / Client | Generates draft preview (`is_final = False`) |
| `/api/reports/<report_id>` | `GET` | Authenticated (Tenant Isolated) | Retrieves structured report JSON |
| `/api/reports/<report_id>/pdf` | `GET` | Authenticated (Tenant Isolated) | Streams publication-quality PDF |
| `/api/reports/document/<document_id>` | `GET` | Authenticated (Tenant Isolated) | Lists all report versions for document |
| `/api/reports/client/queue` | `GET` | Client | Lists client's available final reports |
| `/api/reports/<report_id>/feedback` | `POST` | Client | Submits 1–5 structured feedback |
| `/api/reports/<report_id>/feedback` | `GET` | Authenticated (Tenant Isolated) | Retrieves report feedback items |
| `/api/reports/feedback/<feedback_id>/respond` | `POST` | Verified Advocate / Supervisor | Records advocate response |
| `/api/reports/feedback/<feedback_id>/status` | `POST` | Verified Advocate / Supervisor | Transitions feedback state |

---

## 11. Files Created and Modified

- **Created:**
  - `src/reporting/schema.py`
  - `src/reporting/client_pdf.py`
  - `src/reporting/service.py`
  - `src/reporting/routes.py`
  - `tests/test_final_reports_feedback.py`
  - `docs/task034_final_reports_client_feedback.md`
- **Modified:**
  - `src/persistence/models.py` (added ReportStatus, FeedbackStatus, FinalReportRecord, ClientFeedbackRecord, FeedbackResponseRecord)
  - `src/persistence/repository.py` (added report & feedback repository methods)
  - `src/persistence/__init__.py` (exported new models)
  - `src/reporting/__init__.py` (exported reporting modules)
  - `src/audit/provenance.py` (added 10 Task 034 audit event types)
  - `src/dashboard/app.py` (registered reporting_bp, added Lawyer Workbench report card, Client Workspace feedback section, and JS logic)

---

## 12. Verification & Test Execution Results

- **Focused Test Suite:** `pytest tests/test_final_reports_feedback.py -v`  
  **Result:** `22 passed in 10.25s`
- **Application Regression Suite:** `pytest tests/test_ingestion_persistence.py tests/test_auth_rbac.py tests/test_indian_legal_sources.py tests/test_lawyer_workbench.py tests/test_final_reports_feedback.py -v`  
  **Result:** `114 passed in 12.43s`
- **Full Test Suite:** `pytest tests/`  
  **Result:** `418 passed in 130.64s` (100% pass rate)

---

## 13. Known Limitations

1. **Curated Indian Statutory Corpus:** Grounded in curated extracts (ICA 1872, IT Act 2000, SRA 1963, ACA 1996, Companies Act 2013). Does not cover all central/state enactments or unreported high court rulings.
2. **Deterministic PDF Formatting:** Standard Letter size with auto-flowing flowables; very large tables (e.g., > 100 findings) will paginate over multiple pages.
3. **No Automatic Client Notification:** Feedback submission relies on in-app workbench and client workspace polling rather than external SMTP/SMS triggers.
