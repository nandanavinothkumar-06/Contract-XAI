# CONTRACTRISK-XAI: Task 038 — Evidence-Grounded Contract Analysis and Review Presentation

**Document Version:** 1.0.0  
**Status:** ✅ Completed & Verified  
**Classification:** Core Engineering Specification & Verification Record  
**Date:** 2026-10-15  

---

## 1. Executive Summary

Task 038 establishes an end-to-end, evidence-grounded contract intelligence and review presentation pipeline for **CONTRACTRISK-XAI**. It hardens the unbroken traceability chain connecting raw uploaded agreements to preliminary AI observations, model attribution spans, authoritative Indian statutory provisions, verified advocate determinations, client-facing workspaces, and tamper-evident PDF reports.

### Core Objectives Achieved
1. **Unbroken Traceability Chain:** A contract finding unambiguously identifies the source contract document (`DocumentRecord`), exact character offsets within the text snapshot (`ExtractedTextSnapshot` & `SegmentRecord`), document version, preliminary AI observation, attribution evidence, retrieved statutory source, and independent advocate determination.
2. **Zero Fabricated Evidence:** BM25/similarity scores are explicitly disclaimed as ranking metrics and never transformed into legal confidence percentages. Statutory citations are restricted to verified provisions from the curated repository of 6 central commercial statutes.
3. **Calibrated AI Transparency:** Preliminary AI observations prominently disclose the research baseline model identity (`legalbert-base-uncased`), calibrated threshold ($\tau^* = 0.04$), raw model outputs, and a mandatory disclaimer stating that AI findings do not constitute legal advice.
4. **Attribution Faithfulness:** Feature attribution spans (Gradient × Input) are grounded in actual model inputs and token alignments, highlighting key risk drivers without claiming autonomous legal reasoning.
5. **Granular Evidence Quality States:** Evaluated evidence transitions into one of 6 explicit quality and abstention states:
   - `TRACEABLE`: Active, verified statutory provision with high lexical alignment.
   - `PARTIAL`: Active, verified statutory provision with moderate lexical alignment.
   - `INSUFFICIENT`: Weak lexical alignment falling below the abstention threshold.
   - `SOURCE_UNVERIFIED`: Provision flagged as unverified, amended, or disputed.
   - `STALE_EVIDENCE`: Finding evaluated against a superseded document version or outdated statutory snapshot.
   - `NO_MATCHING_EVIDENCE`: No matching statutory provision retrieved or identified.
6. **Strict Client Privacy & Privilege Protection:** Internal advocate notes (`lawyer_notes`) and internal review discussions are strictly suppressed from all client API endpoints, client UI views, and exported PDF reports.
7. **Human-in-the-Loop Determination:** Only verified advocates (`AdvocateStatus.VERIFIED`) are authorized to make determinations, author findings, and issue final reports.
8. **Cryptographic Provenance:** ReportLab PDF reports and compiled report payloads maintain SHA-256 integrity digests and continuous audit ledger hash-chaining.

---

## 2. End-to-End Evidence Traceability Architecture

The following diagram illustrates the unbroken evidence pipeline established in Task 038:

```
[Uploaded Contract] (PDF / DOCX / TXT)
       │
       ▼ (SHA-256 digest & text normalization)
[ExtractedTextSnapshot] ─── char_count, raw_text, text_sha256
       │
       ▼ (Clause boundary detection)
[SegmentRecord] ─── original_start, original_end, heading, numbering
       │
       ▼ (LegalBERT inference with tau* = 0.04 threshold)
[Preliminary AI Observation] ─── risk_label, raw_score, model_identity, non-legal-advice disclaimer
       │
       ├─────────────────────────────────┬─────────────────────────────────┐
       ▼                                 ▼                                 ▼
[Attribution Spans]             [Statutory Retrieval]            [Evidence Quality Evaluator]
• Gradient x Input tokens       • ICA 1872, IT Act 2000,          • TRACEABLE / PARTIAL
• TokenAligner spans              DPDP Act 2023, SRA 1963,        • INSUFFICIENT / STALE
• Highlighted clause drivers      ACA 1996, BSA 2023              • SOURCE_UNVERIFIED
                                • Exact section + BM25            • NO_MATCHING_EVIDENCE
                                • Source SHA-256 checksum
       │                                 │                                 │
       └─────────────────────────────────┴─────────────────────────────────┘
                                         │
                                         ▼
                   [Advocate Workbench (Verified Advocate Only)]
                   • AI Observation vs. Retrieved Evidence Inspector
                   • Mandatory Legal Rationale Input
                   • ACCEPT / CORRECT / REJECT / CLARIFICATION Decisions
                   • Confidential Internal Advocate Notes
                                         │
                                         ▼
                   [Client Workspace & Publication-Ready PDF]
                   • Segregated AI vs. Lawyer Determinations
                   • Verbatim Clause Excerpt & Plain-Language Guidance
                   • Grounded Statutory References with SHA-256 Checksums
                   • Strictly Excluded Internal Notes
                   • Tamper-Evident SHA-256 Digest & Audit Chaining
```

---

## 3. Database Schema & Persistence Extensions

### 3.1 `EvidenceQualityStatus` Enum
Defined in `src/persistence/models.py`:
```python
class EvidenceQualityStatus(str, enum.Enum):
    TRACEABLE = "TRACEABLE"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    SOURCE_UNVERIFIED = "SOURCE_UNVERIFIED"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    NO_MATCHING_EVIDENCE = "NO_MATCHING_EVIDENCE"
```

### 3.2 `ClauseFindingRecord` Model Extensions
Added nullable, backward-compatible columns to `ClauseFindingRecord`:
- `document_version` (`Integer`, default `1`): Tracks the document revision version against which the finding was evaluated.
- `ai_metadata_json` (`Text`, nullable): Serializes model identity (`legalbert-base-uncased`), inference timestamp, calibrated threshold $\tau^* = 0.04$, raw confidence score, and mandatory non-legal-advice disclaimer.
- `model_attribution_json` (`Text`, nullable): Serializes Gradient × Input token spans with start/end character offsets and attribution weight values.
- `evidence_quality_status` (`String(64)`, default `NO_MATCHING_EVIDENCE`): Encodes the computed or lawyer-affirmed evidence quality state.

### 3.3 SQLite Schema Auto-Migration
In `src/persistence/database.py`, `init_db()` was enhanced to introspect SQLite `PRAGMA table_info(clause_findings)` and automatically execute non-destructive `ALTER TABLE clause_findings ADD COLUMN` statements for missing fields when running on existing local development databases.

---

## 4. Statutory Corpus & Retrieval Quality Engine

### 4.1 Curated Commercial Corpus Disclosure
The platform accesses a curated repository containing 40 commercial sections across 6 central Indian statutes:
1. **The Indian Contract Act, 1872 (ICA 1872)** — Sections 10, 23, 27, 28, 73, 74, 124, 148, etc.
2. **The Information Technology Act, 2000 (IT Act 2000)** — Sections 43A, 65, 66, 72A, etc.
3. **The Digital Personal Data Protection Act, 2023 (DPDP Act 2023)** — Sections 4, 5, 6, 8, 9, etc.
4. **The Specific Relief Act, 1963 (SRA 1963)** — Sections 10, 14, 16, 20, 21, etc.
5. **The Arbitration and Conciliation Act, 1996 (ACA 1996)** — Sections 7, 8, 9, 11, 34, etc.
6. **The Bharatiya Sakshya Adhiniyam, 2023 (BSA 2023)** — Sections 57, 61, 62, 63, etc.

**Statutory Disclosure Notice:**
> *"The retrieved statutory passages are drawn from a curated repository of key Indian commercial statutes. This does not represent an exhaustive search of all Indian central, state, or subordinate legislation, nor does it replace professional legal verification."*

### 4.2 Score Semantics & Disclaimers
Lexical retrieval utilizes Okapi BM25 scores. To prevent misleading clients and advocates, scores are strictly disclaimed:
> *"BM25 and similarity scores indicate lexical and semantic alignment between contract clauses and statutory text within the curated extract collection. These scores do not measure legal validity, statutory compliance, or court enforceability."*

### 4.3 Evidence Quality Computation Logic
`ClauseEvidenceRetriever` in `src/review/evidence.py` evaluates evidence quality across 6 mutually exclusive states:
1. **Version Staleness Check:** If the finding's `document_version` is lower than the contract's latest revision, or if `document_version_mismatch` is detected, the status is immediately flagged as `STALE_EVIDENCE`.
2. **Source Registry Verification:** If a retrieved passage references a source identifier not found in the verified `StatutoryRegistry` or marked unverified, the status is flagged as `SOURCE_UNVERIFIED`.
3. **Passage Content Integrity:** Formatted passages include the SHA-256 checksum of the statutory text, matching the source snapshot in the statutory corpus.
4. **Lexical Alignment Thresholds:**
   - Score $\ge 2.5$ and active legal status $\rightarrow$ `TRACEABLE`
   - Score between $0.5$ and $2.5$ $\rightarrow$ `PARTIAL`
   - Score $< 0.5$ $\rightarrow$ `INSUFFICIENT`
   - Zero passages found $\rightarrow$ `NO_MATCHING_EVIDENCE`

---

## 5. UI/UX Presentation & Client Workspace

### 5.1 Lawyer Workbench Enhancements
- **Clause Navigation & Context:** Displays clause numbering, heading, character offsets, and document version badge.
- **Eight-Section Structured Layout:**
  1. **Contract Clause Text:** Verbatim text with character offsets.
  2. **Preliminary AI Observation:** Risk category badge, calibrated confidence score, and model identity badge (`legalbert-base-uncased`).
  3. **Model Feature Attribution:** Gradient × Input token chips highlighting primary linguistic drivers.
  4. **Retrieved Statutory Evidence:** Section citation, act title, commencement status, and source SHA-256 checksum preview.
  5. **Evidence Quality Badge:** Distinct color-coded badge (`.badge-traceable`, `.badge-partial`, `.badge-insufficient`, `.badge-unverified`, `.badge-stale`, `.badge-no-evidence`).
  6. **Statutory Limitations & Disclaimers:** Visible disclosure of the 6-statute curated corpus and BM25 score semantics.
  7. **Lawyer Determination Controls:** Decision selector (`ACCEPT`, `CORRECT`, `REJECT`, `NEEDS_MORE_EVIDENCE`, `REQUIRES_CLIENT_CLARIFICATION`, `NOT_APPLICABLE_TO_REVIEW`).
  8. **Lawyer Legal Rationale & Notes:** Mandatory legal reasoning textarea and confidential internal notes textarea.
- **Client Disclosure Toggle:** Controlled visibility toggle determining whether the finding is exported to client views.

### 5.2 Client Workspace Presentation
- **Clean Segregation:** Clearly separates verbatim clause excerpts from advocate evaluations and statutory grounding.
- **Plain-Language Guidance:** Displays lawyer rationale in plain language with commercial risk impact assessments.
- **Strict Privilege Preservation:** Internal lawyer notes (`lawyer_notes`) are strictly omitted from client responses and UI rendering.
- **Audit Verification:** Prominently links to downloadable final reports bearing SHA-256 integrity digests.

---

## 6. Verification & Test Suite

The implementation was validated against 21 dedicated test cases in `tests/test_evidence_grounded_analysis.py`, covering every functional, security, and presentation requirement:

| # | Test Case Description | Verified Behavior |
| :- | :--- | :--- |
| **01** | Finding links to correct contract | Foreign contract ID rejection and document link integrity. |
| **02** | Finding links to correct document version | Preserves document version association across revisions. |
| **03** | Finding links to correct clause/segment | Verifies character offsets `[original_start:original_end]` match exact segment text. |
| **04** | Evidence metadata preserved during retrieval | Preserves statute ID, section number, title, and checksum. |
| **05** | Displayed statutory passage matches stored source | Validates text fidelity against the curated commercial corpus. |
| **06** | Missing source identifier handled safely | Returns `SOURCE_UNVERIFIED` without server errors. |
| **07** | Missing section identifier handles gracefully | Prevents fabricated statutory citations when section is unassigned. |
| **08** | Source unverified state displayed accurately | Flags unverified/repealed statutory provisions. |
| **09** | Stale document version reference detected | Automatically computes `STALE_EVIDENCE` for older versions. |
| **10** | Stale source snapshot not treated as current | Rejects or flags outdated statutory index entries. |
| **11** | Weak retrieval results produce appropriate abstention | Low BM25 score produces `INSUFFICIENT` or `NO_MATCHING_EVIDENCE`. |
| **12** | Retrieval scores not displayed as legal confidence | Validates non-legal-confidence disclaimers and score semantics. |
| **13** | Attribution scores faithful to model output | Gradient × Input spans accurately highlight input tokens. |
| **14** | Missing attribution data handled gracefully | Falls back safely when attribution weights are absent. |
| **15** | AI observations remain separate from lawyer decisions | Enforces structural distinction between AI observation and lawyer determination. |
| **16** | Lawyer rationale associated with correct decision | Mandates legal rationale for every recorded decision. |
| **17** | Internal lawyer notes remain hidden from clients | Client API endpoints and payload compilation strictly omit internal notes. |
| **18** | Final reports include only eligible evidence | Disclosed, verified findings are compiled into reports. |
| **19** | Report hashes and integrity checks remain valid | SHA-256 digests and ReportLab PDF compilation pass integrity validation. |
| **20** | Unauthorized users cannot access restricted evidence | Non-owner clients and unassigned lawyers receive 403 Forbidden. |
| **21** | Existing lifecycle integration continues to work | Upload $\rightarrow$ Assignment $\rightarrow$ Decision $\rightarrow$ Completion $\rightarrow$ Final Report passes end-to-end. |

---

## 7. Regression Test Results

All regression test suites pass with 100% compliance:

```
tests/test_ingestion_persistence.py           18 passed (1.65s)
tests/test_auth_rbac.py                        23 passed (2.92s)
tests/test_indian_legal_sources.py             27 passed (1.26s)
tests/test_lawyer_workbench.py                 24 passed (4.79s)
tests/test_final_reports_feedback.py           22 passed (4.19s)
tests/test_session_management.py               15 passed (3.33s)
tests/test_contract_lifecycle_integration.py   14 passed (4.75s)
tests/test_evidence_grounded_analysis.py       21 passed (2.67s)
tests/test_acceptance_verification.py           5 passed
tests/test_ui_interactions.py                   8 passed
tests/test_ui_modernization.py                 11 passed
-----------------------------------------------------------------
TOTAL: 188 / 188 tests passed
```

---

## 8. Commitments & Constraints Enforced

- **Tasks 028 and 029:** Remain strictly `🔒 LOCKED`.
- **Task 039:** Has **NOT** been started.
- **Zero Mock Bypasses:** Verified advocate authorization, CSRF double-submit protection, HttpOnly cookie sessions, and multi-tenant isolation remain strictly enforced across all routes.
- **Execution Mode:** Execution has followed Inspect $\rightarrow$ Trace Architecture $\rightarrow$ Identify Gaps $\rightarrow$ Implement $\rightarrow$ Test $\rightarrow$ Verify $\rightarrow$ Document $\rightarrow$ STOP.
