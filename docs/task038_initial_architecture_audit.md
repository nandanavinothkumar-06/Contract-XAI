# CONTRACTRISK-XAI: Task 038 — Architecture Audit & Evidence Traceability Baseline

**Document Version:** 1.0.0  
**Status:** Audit Completed  
**Classification:** Engineering Specification & Architecture Baseline  
**Date:** 2026-10-15  

---

## 1. Executive Summary

Task 038 establishes an end-to-end evidence-grounded contract analysis and lawyer review presentation pipeline for **CONTRACTRISK-XAI**. The objective is to strengthen the verifiable, unbroken traceability chain connecting:
1. The uploaded contract document (`DocumentRecord` & `ExtractedTextSnapshot`).
2. The extracted contract clause / segment (`SegmentRecord` with character offsets).
3. The AI-generated preliminary observation (with model identity, raw scores, threshold, and non-legal-advice disclaimer).
4. Supporting model evidence (Gradient × Input attribution spans without claiming legal validity).
5. The retrieved Indian statutory source (from curated extracts of 6 commercial statutes).
6. Evidence quality and abstention states (`TRACEABLE`, `PARTIAL`, `INSUFFICIENT`, `SOURCE_UNVERIFIED`, `STALE_EVIDENCE`, `NO_MATCHING_EVIDENCE`).
7. The independent advocate determination and mandatory legal rationale.
8. The client-facing presentation and final report (ReportLab PDF with cryptographic SHA-256 integrity digests).

This audit documents the existing components, verified data structures, integration points, identified gaps, and proposed minimal changes before code modification.

---

## 2. Existing Components & Services

| Module / Component | Path | Core Responsibilities & Verified State |
| :--- | :--- | :--- |
| **Ingestion Pipeline** | `src/ingestion/pipeline.py` | Multi-format ingestion (PDF, DOCX, TXT), text normalization, character count verification, and raw text snapshotting. |
| **Relational Persistence** | `src/persistence/models.py`, `src/persistence/repository.py` | SQLite/SQLAlchemy schema storing documents, snapshots, segments, reviews, findings, comments, revisions, reports, sessions, and audit events. |
| **Segmentation Engine** | `src/segmentation/pipeline.py` | Structural clause boundary detection preserving character offsets `[original_start:original_end]` against raw text snapshots. |
| **Model Inference & Attribution** | `src/models/`, `src/evidence/extractor.py`, `src/evidence/schema.py` | LegalBERT baseline inference and Gradient × Input token attribution with `TokenAligner`. |
| **Indian Legal Corpus & Retrieval** | `src/legal_sources/ingestion.py`, `src/legal_sources/index.py`, `src/legal_sources/retrieval.py` | Curated extracts of 6 central statutes (40 commercial sections), Okapi BM25 lexical index, exact section lookup, and commencement/currentness provenance. |
| **Review Service & State Machine** | `src/review/service.py`, `src/review/routes.py` | 10-state review lifecycle, advocate verification gate (`AdvocateStatus.VERIFIED`), independent decisions (`ACCEPT`, `CORRECT`, `REJECT`, etc.), and scoped communications. |
| **Statutory Evidence Connector** | `src/review/evidence.py` | `ClauseEvidenceRetriever` bridging clause text to authoritative statutory matching with BM25 score disclaimers. |
| **Reporting & PDF Generation** | `src/reporting/service.py`, `src/reporting/client_pdf.py` | Report eligibility gate, segregated finding compilation, two-pass ReportLab PDF generation, content/file SHA-256 digests, and superseding lifecycle. |
| **Authentication & RBAC** | `src/auth/rbac.py`, `src/auth/service.py` | Role-based authorization (`CLIENT`, `LAWYER`, `SUPERVISING_LAWYER`, `AUDITOR`), HttpOnly cookies, Double-Submit CSRF, and cryptographic session hashing. |
| **Audit Ledger** | `src/audit/provenance.py`, `src/audit/events.py` | Continuous SHA-256 hash chaining of all lifecycle, review, assignment, finding, and reporting events. |
| **Web Dashboard & UI** | `src/dashboard/app.py`, `src/dashboard/static/js/dashboard.js`, `src/dashboard/static/css/design_system.css` | LegalTech Navy & Gold UI, tab-isolated views, review queue, clause list, evidence inspector, decision modal, and client workspace. |

---

## 3. Existing Data Structures & Schemas

### 3.1 Document & Segmentation Data Contracts
- `DocumentRecord`:
  - `id`: UUID primary key.
  - `file_sha256`: SHA-256 fingerprint of the original uploaded file.
  - `original_filename` & `sanitized_filename`: Preserved file identity.
  - `owner_id`: Multi-tenant client ownership link.
  - `assigned_lawyer_id`: Assigned advocate foreign key.
- `ExtractedTextSnapshot`:
  - `id`: UUID primary key.
  - `document_id`: Parent document link.
  - `raw_text`: Verbatim extracted UTF-8 text.
  - `char_count`: Exact character length.
  - `text_sha256`: SHA-256 of extracted raw text.
- `SegmentRecord`:
  - `id`: UUID primary key.
  - `document_id`: Parent document link.
  - `segment_id`: Deterministic segment identifier (e.g. `doc_..._clause_1`).
  - `text`: Verbatim clause text.
  - `original_start`: Exact start offset within `ExtractedTextSnapshot.raw_text`.
  - `original_end`: Exact end offset within `ExtractedTextSnapshot.raw_text`.
  - `heading` & `numbering`: Structural clause metadata.
  - `sequence`: Reading order index.

### 3.2 Review & Clause Finding Data Contracts
- `ReviewRecord`:
  - `id`: UUID primary key.
  - `document_id`: Associated document.
  - `document_version`: Version number under review (default: 1).
  - `status`: Persistent lifecycle state (`DOCUMENT_SUBMITTED`, `AWAITING_LAWYER_ASSIGNMENT`, `ASSIGNED`, `IN_REVIEW`, `REVISION_REQUESTED`, `CLIENT_RESPONSE_RECEIVED`, `REVIEW_COMPLETED`, `REVIEW_REOPENED`).
  - `assigned_lawyer_id`: Reviewing advocate.
  - `completion_summary`: Mandatory advocate review summary.
  - `disclaimer_text`: Mandatory statutory disclaimer.
- `ClauseFindingRecord`:
  - `id`: UUID primary key.
  - `review_id` & `document_id`: Relational links.
  - `segment_id`: Foreign link to `SegmentRecord.segment_id`.
  - `document_version`: Version of document when finding was created.
  - `finding_origin`: `AI_GENERATED` vs `LAWYER_AUTHORED`.
  - `risk_label`: Preliminary classification or lawyer risk tag.
  - `ai_confidence_score`: Raw model score (stored as string).
  - `ai_observation`: Textual observation description.
  - `decision`: Independent lawyer determination (`ACCEPT_AI_OBSERVATION`, `CORRECT_AI_OBSERVATION`, `REJECT_AI_OBSERVATION`, `NEEDS_MORE_EVIDENCE`, `NOT_APPLICABLE_TO_REVIEW`, `REQUIRES_CLIENT_CLARIFICATION`).
  - `lawyer_rationale`: Mandatory legal rationale authored by the advocate.
  - `lawyer_notes`: Internal advocate-only confidential notes.
  - `statutory_evidence_json`: Serialized JSON array/object of supporting statutory passages.
  - `is_disclosed_to_client`: Boolean flag controlling client report and workspace visibility.
  - `author_id`: User ID of author.

### 3.3 Statutory Evidence Data Contracts
- `RetrievedLegalEvidence`:
  - `evidence_id`: UUID.
  - `clause_id`: Identifier of evaluated clause.
  - `status`: `EVIDENCE_FOUND` or `ABSTAIN`.
  - `abstention_reason`: Error or abstention code (`NO_MATCHING_PASSAGES`, `INSUFFICIENT_EVIDENCE`, `HISTORICAL_ONLY_VERSION`, `UNKNOWN_COMMENCEMENT`).
  - `passages`: List of `LegalSourceRetrievalResult`.
- `LegalSourceRetrievalResult`:
  - `source_id`: Statute identifier (e.g. `IN_ACT_1872_09`).
  - `source_title`: Full official statute title.
  - `section_number` & `heading`: Statutory section locator.
  - `passage_text`: Exact verbatim provision text.
  - `similarity_score`: BM25 lexical score.
  - `retrieval_method`: `BM25_LEXICAL` or `EXACT_SECTION_LOOKUP`.
  - `commencement_status`: In force, not commenced, or repealed.
  - `currentness_status`: Current, superseded, or under review.
  - `verification_status`: Official, authoritative, or unverified.

---

## 4. End-to-End Traceability Path & Verification

```
[Contract Upload]
      │ (PDF / DOCX / TXT)
      ▼
[ExtractedTextSnapshot] ──► raw_text, text_sha256 (Immutable)
      │
      ▼
[SegmentationPipeline]  ──► SegmentRecord [original_start:original_end]
      │
      ├───► [LegalBERT & GradXInput] ──► Observation, Raw Logits, Attribution Spans
      │
      └───► [ClauseEvidenceRetriever] ──► Curated Statutory Passages & BM25 Scores
                                                     │
                                                     ▼
                                      [ClauseFindingRecord]
                                       - segment_id, doc_version
                                       - ai_observation, ai_metadata_json
                                       - model_attribution_json
                                       - evidence_quality_status
                                       - statutory_evidence_json
                                                     │
                                                     ▼
                                      [Lawyer Review Workbench]
                                       - Independent Decision
                                       - Mandatory Legal Rationale
                                       - Confidential Lawyer Notes
                                                     │
                                                     ▼
                                        [Final Report & PDF]
                                       - Segregated Findings
                                       - Content & File SHA-256
                                       - Zero Notes Exposed
```

---

## 5. Identified Gaps & Deficiencies

1. **Incomplete Finding Metadata**:
   - `ClauseFindingRecord` stores raw score as a string and lacks structured metadata for model identity (`legalbert-base-uncased`), model version, inference threshold ($\tau^* = 0.04$), raw logits, and an explicit statement that the prediction is an automated statistical observation, not a legal opinion.
2. **Disconnected Attribution Spans**:
   - `src/evidence/extractor.py` computes Gradient × Input token attribution spans, but `ClauseFindingRecord` had no field or pipeline hook to persist and present these spans in the review workbench and final report.
3. **Coarse Evidence Status**:
   - Evidence retrieval currently only reports `EVIDENCE_FOUND` or `ABSTAIN`. It does not evaluate or persist the 6 required quality states: `TRACEABLE`, `PARTIAL`, `INSUFFICIENT`, `SOURCE_UNVERIFIED`, `STALE_EVIDENCE`, `NO_MATCHING_EVIDENCE`.
4. **Document Version Staleness Risk**:
   - When a contract document revision is accepted, findings linked to version 1 could be accessed in version 2 without explicit staleness warnings or offset validation.
5. **Statutory Corpus Disclosure**:
   - The platform retrieves provisions strictly from 6 curated central Acts (40 provisions). While Task 032 documents this, the UI and review endpoints need explicit disclosure that these are curated extracts, not an exhaustive Indian legal corpus.
6. **Frontend Field Name Discrepancy**:
   - `dashboard.js` line 713 calls `p.source_checksum.substring(0, 10)`, while `ClauseEvidenceRetriever` does not serialize `source_checksum`. If unhandled, this could trigger a JavaScript TypeError in browsers.
7. **Lawyer Workbench UI Organization**:
   - In `dashboard.js`, selecting a clause loads only statutory passages into `#wb-evidence-panel`. It does not render segregated visual sections for:
     1. Contract clause (with segment locator and document version)
     2. AI-generated observation (with model identity and disclaimer)
     3. Supporting statutory evidence
     4. Evidence quality and limitations
     5. Model explanation (attributed text spans)
     6. Lawyer determination
     7. Lawyer rationale
     8. Review history / decision status

---

## 6. Proposed Minimal Architecture Changes

1. **Extend `ClauseFindingRecord` in `src/persistence/models.py` & `src/persistence/repository.py`**:
   - Add nullable backward-compatible columns:
     - `ai_metadata_json`: stores `{ model_name, model_version, raw_score, threshold, inference_timestamp, disclaimer }`.
     - `model_attribution_json`: stores `{ method, attributed_spans, target_label, target_score, research_caveat }`.
     - `evidence_quality_status`: stores one of `TRACEABLE`, `PARTIAL`, `INSUFFICIENT`, `SOURCE_UNVERIFIED`, `STALE_EVIDENCE`, `NO_MATCHING_EVIDENCE`.
2. **Enhance `ClauseEvidenceRetriever` in `src/review/evidence.py`**:
   - Compute and assign the appropriate `evidence_quality_status`.
   - Include `source_checksum` in formatted passages from `content_checksum_sha256` / `passage_checksum_sha256`.
   - Embed statutory corpus limitations notice and score semantics disclaimer.
3. **Enhance Review Service & Routes (`src/review/service.py`, `src/review/routes.py`)**:
   - Update `record_clause_decision` and `create_or_update_clause_finding` to support `ai_metadata_json`, `model_attribution_json`, and `evidence_quality_status`.
   - Implement version staleness check: if `finding.document_version != review.document_version`, label finding as `STALE_EVIDENCE`.
   - Deliver segregated finding payload in `/api/review/<review_id>` and `/api/review/<review_id>/evidence/<segment_id>`.
4. **Update Reporting Service & PDF (`src/reporting/service.py`, `src/reporting/client_pdf.py`)**:
   - Preserve clear segregation: Contract Clause, AI Observation, Supporting Statutory Evidence, Evidence Quality/Limitations, Model Explanation Spans, Lawyer Determination, and Lawyer Rationale.
   - Enforce that internal lawyer notes are NEVER included in client reports.
   - Maintain SHA-256 integrity digests for report JSON and compiled PDF.
5. **Modernize Workbench & Client Workspace UI (`src/dashboard/app.py`, `src/dashboard/static/js/dashboard.js`)**:
   - Render the 8 distinct sections in `#wb-evidence-panel` and `#wb-decision-form-container`.
   - Add clear visual badge indicators:
     - `AI OBSERVATION`
     - `RETRIEVED SOURCE EVIDENCE`
     - `EVIDENCE LIMITATION`
     - `LAWYER DETERMINATION`
     - `LAWYER RATIONALE`
   - Handle all evidence states (`TRACEABLE`, `PARTIAL`, `INSUFFICIENT`, `SOURCE_UNVERIFIED`, `STALE_EVIDENCE`, `NO_MATCHING_EVIDENCE`).
   - Fix `source_checksum` null-safe access in JS.
6. **Author Regression Test Suite (`tests/test_evidence_grounded_analysis.py`)**:
   - Cover all 21 verification criteria outlined in Task 038.
