# Strategy A — Blinded Legal Annotation & Independent Evaluation Infrastructure

**Document ID:** `DOC-TASK041B-BLINDED-ANNOTATION`  
**Classification:** Technical Architecture, Security Specification & Verification Report  
**Project:** CONTRACTRISK-XAI  
**Status:** ✅ IMPLEMENTED & VERIFIED  
**Date:** 2026-10-17  
**Author:** Senior Legal-Tech Verification Engineer, Digital Evidence Auditor, Security Reviewer  

---

## Executive Summary

This document specifies and verifies the **Strategy A Blinded Legal Annotation and Independent Storage Infrastructure** for the `CONTRACTRISK-XAI` platform. 

The infrastructure implements the rigorous research protocol formulated in prior stages to evaluate whether an evidence-aware abstention policy improves the reliability of contract analysis compared with a confidence-only baseline. To eliminate cognitive anchoring, confirmation bias, and circular policy leakage, this architecture establishes:

1. **A Formal Draft-07 JSON Schema Specification** (`docs/schemas/candidate_finding_annotation.schema.json`) defining multi-dimensional legal assessments across 6 core evaluative axes with strict types, enums, rationale minimum lengths, and mandatory epistemic firewall attestations.
2. **Deterministic Canonical JSON Serialization & SHA-256 Digest Computation** guaranteeing reproducible, tamper-evident cryptographic fingerprinting for all annotations and adjudication determinations.
3. **Independent Database Persistence** (`BlindedAnnotationRecord` and `BlindedAdjudicationRecord`) stored separately from review findings and model candidates, preventing duplicate active submissions and maintaining versioned correction chains.
4. **Server-Side Presentation Firewall** (`PresentationFirewall` in `src/annotation/firewall.py`) enforcing explicit allowlists that strip model identifiers, raw confidence scores, BM25 retrieval rankings, system-generated evidence quality statuses, and automated policy recommendations before data reaches annotator or adjudicator clients.
5. **Stage-Specific Visibility Filtering** across 6 distinct evaluation stages, ensuring annotators assess each dimension independently without cross-stage contamination.
6. **Strict Peer Blinding Firewalls & Adjudication Gating**, ensuring peer submissions remain completely inaccessible until both independent primary annotations are validated and locked.
7. **Two-Phase Submission and Immutability Locking**, where draft submissions transition to an immutable `is_locked = True` state with complete prohibition of ordinary edits or deletions.
8. **Cryptographic Hash-Chained Audit Trail Logging** linking every submission, locking transition, access denial, and adjudication determination into the tamper-evident provenance log.

---

## 1. Architecture Overview & Design Rationale

### 1.1 The Challenge: Epistemic Leakage & Confirmation Bias

In legal-tech verification and AI safety evaluation, human evaluators presented with model confidence scores, algorithmic evidence quality labels (such as `TRACEABLE`), or automated policy recommendations exhibit pronounced confirmation bias and cognitive anchoring. Evaluators disproportionately accept machine predictions when accompanied by high confidence scores, or assume statutory passages are legally applicable merely because BM25 lexical retrieval ranked them first.

Furthermore, when evaluators see peer opinions or consensus indicators prior to recording their own determinations, independent inter-annotator agreement metrics (e.g., Cohen's $\kappa$) are fatally compromised.

### 1.2 The Strategy A Solution Architecture

```
                                  [ RAW CANDIDATE FINDING ]
                                (Contains: Model ID, Logits,
                                 Confidence, BM25, Status)
                                             │
                                             ▼
                             ┌───────────────────────────────┐
                             │     PresentationFirewall      │
                             │  (Server-Side Strict Filter)  │
                             └───────────────┬───────────────┘
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       ▼                                           ▼
          [ STAGE-SPECIFIC VIEWS ]                    [ PEER BLINDING GATE ]
      - Stage 1: Prediction Correctness           - Peer A cannot see Peer B
      - Stage 2: Evidence Support                 - Peer B cannot see Peer A
      - Stage 3: Evidence Sufficiency             - Blocked until BOTH are LOCKED
      - Stage 4: Source Status                                     │
      - Stage 5: Version Consistency                               │
      - Stage 6: Final Reference Decision                          │
                       │                                           │
                       ▼                                           ▼
          ┌───────────────────────────┐               ┌───────────────────────────┐
          │  Draft-07 Schema Validate │               │   Senior Counsel Dossier  │
          │ & Canonical SHA-256 Digest│               │ (Model Scores & Policies  │
          └────────────┬──────────────┘               │     STRICTLY HIDDEN)      │
                       │                              └─────────────┬─────────────┘
                       ▼                                            │
          ┌───────────────────────────┐                             │
          │  Immutable Submission     │                             │
          │  Locking (is_locked=True) ├─────────────────────────────┘
          └────────────┬──────────────┘
                       │
                       ▼
          ┌───────────────────────────┐
          │ Hash-Chained Audit Events │
          │ (Tamper-Evident Ledger)   │
          └───────────────────────────┘
```

---

## 2. Complete JSON Schema Specification

The formal Draft-07 schema is registered on disk at:
[`docs/schemas/candidate_finding_annotation.schema.json`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/docs/schemas/candidate_finding_annotation.schema.json)

### 2.1 Multi-Dimensional Structure

The schema defines 10 top-level structural objects:

| Object Key | Description | Key Enums / Constraints |
|---|---|---|
| `schema_version` | Schema semantic version | Must equal `"1.0.0"` |
| `annotation_id` | Unique UUID v4 identifier | UUID regex pattern |
| `is_synthetic_fixture` | Distinguishes synthetic benchmark fixtures from live study records | `boolean` |
| `identification` | Contract, clause, candidate finding, and model provenance metadata | Strings, integers, confidence sub-object |
| `prediction_assessment` | Evaluation of candidate risk claim against clause text | `CORRECT`, `PARTIALLY_CORRECT`, `INCORRECT`, `UNCLEAR`, `NOT_ASSESSABLE` (Min length: 10 chars) |
| `evidence_support` | Evaluation of whether cited statutory passages support the risk claim | `SUPPORTED`, `PARTIALLY_SUPPORTED`, `UNSUPPORTED`, `INSUFFICIENT_INFORMATION`, `NOT_APPLICABLE`, `NOT_ASSESSABLE` |
| `evidence_sufficiency` | Assessment of whether retrieved evidence provides legally sufficient basis | `SUFFICIENT`, `INSUFFICIENT`, `CONFLICTING`, `MISSING`, `NOT_APPLICABLE`, `NOT_ASSESSABLE` |
| `source_status` | Status of legal sources according to research protocol | `VERIFIED_RESEARCH_PROTOCOL`, `PARTIALLY_VERIFIED`, `UNVERIFIED`, `HISTORICAL_CURRENTNESS_UNCERTAIN`, `NOT_APPLICABLE`, `NOT_ASSESSABLE` |
| `source_applicability` | Legal currentness and contractual applicability under Indian law | Currentness: `IN_FORCE_CONFIRMED`, `AMENDED_SUBSEQUENTLY`, `REPEALED`, `PROSPECTIVE_ONLY`, `COMMENCEMENT_UNCERTAIN`; Applicability: `APPLICABLE_TO_CONTRACT`, `POTENTIALLY_APPLICABLE`, `INAPPLICABLE`, `UNKNOWN` |
| `version_consistency` | Alignment between finding contract version and active contract version | `CONSISTENT`, `STALE_AMENDMENT`, `SUPERSEDED_CLAUSE`, `DELETED_CLAUSE`, `VERSION_MISMATCH` |
| `final_reference_decision` | Ground-truth reference disposition for evaluating abstention policies | `RETAIN`, `WITHHOLD`, `HUMAN_REVIEW_REQUIRED`, `NOT_ASSESSABLE` |
| `epistemic_firewall_attestation` | Mandatory negative legal rules affirming no false equivalences were assumed | 5 required booleans (all must be `true`) |
| `annotation_provenance` | Annotator qualification, phase, timestamp, and blinding conditions | `ENROLLED_ADVOCATE_INDIA`, `SENIOR_ADVOCATE`, `LEGAL_RESEARCHER`, etc. |

### 2.2 Epistemic Firewall Attestation Rules

To satisfy research integrity standards, every locked annotation must explicitly affirm the 5 negative epistemic rules:
1. `rule_traceable_not_treated_as_correct`: Evaluator confirms that a system status of `TRACEABLE` was not treated as establishing prediction correctness.
2. `rule_bm25_not_treated_as_ground_truth_sufficiency`: Evaluator confirms that high BM25 scores or retrieval ranking were not treated as ground-truth evidence sufficiency.
3. `rule_checksum_not_treated_as_official_authenticity`: Evaluator confirms that local file SHA-256 checksums were not treated as sovereign government authenticity.
4. `rule_authenticity_not_treated_as_applicability`: Evaluator confirms that an authentic statutory extract was not assumed to be applicable to the specific contract without independent legal analysis.
5. `rule_policy_output_not_treated_as_reference_decision`: Evaluator confirms that automated policy actions were not treated as ground truth reference decisions.

---

## 3. Server-Side Presentation Firewall

The presentation firewall (`PresentationFirewall` in `src/annotation/firewall.py`) intercepts all candidate data and submissions on the server before serialization.

### 3.1 Prohibited Fields

The firewall guarantees that the following fields **never** appear in an annotator's or adjudicator's view:
- `model_id`, `model_identifier`, `model_name`, `model_version`, `model_task`
- `raw_model_label`, `confidence_value`, `candidate_confidence`, `confidence_semantics`, `confidence_is_calibrated`, `score`, `raw_logit`, `probability`
- `evidence_quality_status`
- `bm25_score`, `retrieval_rank`, `ranking_score`
- `baseline_policy_decision`, `evidence_aware_policy_decision`, `policy_action`, `is_retained`

### 3.2 Stage-Specific Visibility Filtering

| Stage | Permitted Fields | Strictly Hidden Fields |
|---|---|---|
| **Stage 1 (Prediction Correctness)** | `candidate_finding_id`, `clause_id`, `clause_text`, `candidate_finding_text`, `prediction_category` | Model ID, confidence, all statutory extracts, BM25 scores, policy decisions |
| **Stage 2 (Evidence Support)** | `candidate_finding_id`, `clause_id`, `clause_text`, `candidate_finding_text`, cited passages text, section title | BM25 score, retrieval rank, evidence quality status, confidence, policy decisions |
| **Stage 3 (Evidence Sufficiency)** | `candidate_finding_id`, `clause_id`, `clause_text`, `candidate_finding_text`, `prediction_category`, totality of retrieved passages | BM25 scores, retrieval ranks, evidence quality status, confidence, policy decisions |
| **Stage 4 (Source Status)** | `candidate_finding_id`, statute title, section number, source SHA-256, source repository, commencement status | Candidate finding text, clause text, model prediction text, confidence, policy decisions |
| **Stage 5 (Version Consistency)** | `candidate_finding_id`, `contract_id`, `contract_version`, `document_content_hash`, `clause_id`, `clause_text` | Model confidence scores, policy recommendations |
| **Stage 6 (Final Reference Decision)** | `candidate_finding_id`, `clause_id`, `clause_text`, `candidate_finding_text`, `prediction_category`, sanitized passages | Baseline policy decision ($\pi_{\text{conf}}$), evidence-aware policy decision ($\pi_{\text{evid}}$), model confidence |

---

## 4. Blinding Rules & Access Control Matrix

### 4.1 RBAC & Advocate Verification Gates

Access to annotation and adjudication capabilities requires strict role and credential checks:

| Role | Advocate Status | Permitted Actions |
|---|---|---|
| `CLIENT` | N/A | **STRICTLY FORBIDDEN** (403 Forbidden on all annotation endpoints) |
| `AUDITOR` | N/A | Read-only audit events; cannot submit annotations or adjudicate |
| `LAWYER` | `NOT_APPLICABLE` / `PENDING_VERIFICATION` | **BLOCKED** (Cannot submit annotations without verified advocate status) |
| `LAWYER` | `VERIFIED` | May view firewalled candidates, submit draft annotations, lock own annotations, view own submissions |
| `SUPERVISING_LAWYER` | `VERIFIED` | All Lawyer capabilities + access adjudication dossiers and record final binding adjudications |

### 4.2 Peer Blinding Gate

- **Annotator A** viewing **Annotator A's Submission:** **PERMITTED** (Author access).
- **Annotator B** viewing **Annotator A's Submission (Unlocked):** **STRICTLY BLOCKED** (`BlindingViolationError` 403; audit event `BLINDING_VIOLATION_BLOCKED` recorded).
- **Annotator B** viewing **Annotator A's Submission (Both Locked):** **PERMITTED** for post-study debrief / reconciliation.
- **Adjudicator** viewing **Adjudication Dossier (One or Both Unlocked):** **STRICTLY BLOCKED** (`BlindingViolationError` 403; audit event `ANNOTATION_ACCESS_DENIED` recorded).
- **Adjudicator** viewing **Adjudication Dossier (Both Locked):** **PERMITTED** with both independent submissions, rationales, and sanitized candidate finding.

---

## 5. Submission Lifecycle & Immutability Protocol

```
   [ Unverified Advocate ] ──(Block: 403)──┐
                                           │
   [ Enrolled Advocate ]                   │
             │                             │
             ▼                             ▼
   [ POST /api/annotation/submit ] ────────┴──► [ DRAFT ANNOTATION ]
             │                                   (is_locked = False)
             │                                   (Can update payload)
             ▼                                            │
   [ Draft-07 Schema Validation ]                         │
   [ SHA-256 Digest Verification ]                        │
             │                                            │
             ▼                                            ▼
   [ POST /api/annotation/lock/<id> ] ────────► [ LOCKED ANNOTATION ]
                                                 (is_locked = True)
                                                 (Ordinary edits/deletes BLOCKED)
                                                 (Versioned amendment required for errors)
```

### 5.1 Amendment / Supersession Protocol

If an annotator discovers an error after locking, the record cannot be modified in place. Instead:
1. `repo.supersede_blinded_annotation()` creates a versioned amendment ($v+1$).
2. The original record remains immutable on disk, preserving full historical integrity.
3. The original record's `superseded_by_id` pointer is populated with the ID of the new amendment, and `supersession_reason` is recorded.
4. Active queries select only records where `superseded_by_id IS NULL`.

---

## 6. Verification Results & Invariant Audit

### 6.1 Dedicated Test Suite Results (`tests/test_blinded_annotation.py`)

All 18 targeted test cases pass with 100% success:

```
tests/test_blinded_annotation.py::test_01_candidate_presentation_excludes_model_and_confidence_and_policy PASSED [  5%]
tests/test_blinded_annotation.py::test_02_stage_specific_presentation_filters_stages_1_to_6 PASSED [ 11%]
tests/test_blinded_annotation.py::test_03_annotator_a_cannot_access_annotator_b_submission PASSED [ 16%]
tests/test_blinded_annotation.py::test_04_submission_locking_transitions_state_and_records_digest PASSED [ 22%]
tests/test_blinded_annotation.py::test_05_ordinary_update_rejected_on_locked_submission PASSED [ 27%]
tests/test_blinded_annotation.py::test_06_schema_validation_rejects_malformed_payload PASSED [ 33%]
tests/test_blinded_annotation.py::test_07_sha256_digest_deterministic_across_unordered_json PASSED [ 38%]
tests/test_blinded_annotation.py::test_08_duplicate_submission_rejected PASSED [ 44%]
tests/test_blinded_annotation.py::test_09_adjudication_inaccessible_until_both_submissions_locked PASSED [ 50%]
tests/test_blinded_annotation.py::test_10_adjudication_view_excludes_model_confidence_and_policy PASSED [ 55%]
tests/test_blinded_annotation.py::test_11_versioned_amendment_preserves_locked_original PASSED [ 61%]
tests/test_blinded_annotation.py::test_12_audit_events_recorded_for_lifecycle PASSED [ 66%]
tests/test_blinded_annotation.py::test_13_security_advocate_verification_gate PASSED [ 72%]
tests/test_blinded_annotation.py::test_14_non_supervising_lawyer_cannot_adjudicate PASSED [ 77%]
tests/test_blinded_annotation.py::test_15_task_042_not_started_and_tasks_028_029_locked PASSED [ 83%]
tests/test_blinded_annotation.py::test_16_flask_route_blinded_candidate_filtering PASSED [ 88%]
tests/test_blinded_annotation.py::test_17_flask_route_unauthenticated_and_client_role_rejected PASSED [ 94%]
tests/test_blinded_annotation.py::test_18_flask_route_submit_and_lock_lifecycle PASSED [100%]

============================= 18 passed in 10.78s =============================
```

### 6.2 Scope and Boundary Verifications

1. **Task 042 Status:** Verified strictly **NOT STARTED**. No files or experiments corresponding to Task 042 have been initialized.
2. **Tasks 028 and 029 Status:** Verified strictly `🔒 LOCKED`. No modifications have been made to Task 028 or Task 029.
3. **Task 041 and 041A History:** All historical records and statutory reference artifacts remain intact without alteration.
4. **No Model Training:** No neural models were trained or retrained.
5. **No Threshold Recalibration:** Multilabel threshold (0.5) and workbench defaults remain untouched.
6. **No Fake Claims:** The infrastructure does NOT claim legal validity, regulatory approval, or production readiness; it provides research-grade blinding controls for scientific evaluation.
