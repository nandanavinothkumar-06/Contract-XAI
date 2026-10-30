# CONTRACTRISK-XAI — Blinded Annotation Security & Governance Remediation Report

**Date:** 2026-10-17  
**Auditor / Engineering Role:** Senior Legal-Tech Verification Engineer, Digital Evidence Auditor, Security Reviewer, Research Integrity Reviewer  
**Module:** Blinded Legal Annotation & Ground-Truth Benchmarking Infrastructure (Strategy A)  
**Status:** ✅ REMEDIATED AND INDEPENDENTLY VERIFIED  

---

## 1. Executive Summary & Authorization Context

During independent security and research integrity auditing of the newly created Blinded Annotation Infrastructure (`src/annotation/`), five critical vulnerabilities and governance discrepancies were identified:
- **SEC-01:** Client-side trust vulnerability allowing malicious or biased callers to forge model identity, model version, and confidence values in candidate identification metadata.
- **SEC-02:** Missing role-based access control (RBAC) on submission retrieval endpoint, allowing `CLIENT` role tokens to query internal advocate annotation submissions.
- **SEC-03:** Adjudication dossier leakage transmitting unparsed raw `payload_json`, creating a risk of metadata and confidence leakage to senior counsel.
- **SEC-04:** Out-of-sync annotation stages between documentation/database enum and PresentationFirewall projection logic, with silent fallbacks masking invalid stage queries.
- **SEC-05:** Scope boundary assurance ensuring Task 042 remains `NOT STARTED`, Tasks 028 & 029 remain `LOCKED`, and no unauthorized model training or threshold calibration occurs.

All five items have been comprehensively resolved, reinforced at both database and service layers, covered by 13 dedicated security tests in [tests/test_blinded_annotation_security_remediation.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/tests/test_blinded_annotation_security_remediation.py), and verified against the complete 650-test repository regression suite with **0 failures**.

---

## 2. Detailed Root Cause Analysis & Code-Level Remediation

### SEC-01: Candidate Metadata Ingestion Trust Defect

#### Root Cause
In initial implementation of `submit_annotation`, candidate identification attributes (`model_identifier`, `model_version`, `candidate_confidence`, `contract_id`, `clause_id`) were accepted directly from the client request payload. Although intended for convenience during pilot testing, this allowed an annotator or client script to forge model provenance, distort confidence scores, or associate findings with incorrect contract clauses, violating research integrity.

#### Remediation
1. **Created Server-Side Candidate Registry:** Implemented [src/annotation/candidate_registry.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/annotation/candidate_registry.py). The `CandidateRegistry` provides authoritative, server-side lookup across:
   - In-memory candidate registry.
   - Flask application context (`g.candidate_store` / `g.active_candidate_data`).
   - SQLite persistence layer (`ClauseFindingRecord`).
   - Standard verified test/demo fixtures.
2. **Authoritative Server-Side Injection:** In [src/annotation/service.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/annotation/service.py#L151-L225), `submit_annotation()` authoritatively resolves the candidate finding from `CandidateRegistry`. Any client-supplied `identification` block is completely discarded. The server constructs the trusted `identification` record (including verified `contract_id`, `clause_id`, `clause_text`, `prediction_category`, `model_identifier`, `model_version`, and `candidate_confidence`) and binds it to the evaluative payload before running JSON schema validation and canonical SHA-256 digest computation.
3. **Explicit Rejection of Missing Metadata:** If the candidate cannot be resolved from trusted sources, the submission is strictly rejected with `ValueError` ("Candidate finding '{candidate_finding_id}' cannot be resolved from trusted candidate source..."). In [src/annotation/routes.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/annotation/routes.py#L82-L130), this returns HTTP 400.

---

### SEC-02: Route-Level RBAC & Client Role Exclusion

#### Root Cause
In `src/annotation/routes.py`, `GET /api/annotation/submission/<annotation_id>` lacked explicit `@require_roles` decoration. While peer blinding logic was present, a caller with the `CLIENT` role possessing a valid JWT could query the endpoint and receive internal advocate notes if blinding conditions did not explicitly raise an error.

#### Remediation
1. **Route-Level Role Decoration:** Added `@require_roles(UserRole.LAWYER, UserRole.SUPERVISING_LAWYER, UserRole.AUDITOR)` to `get_submission()` in [src/annotation/routes.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/annotation/routes.py#L160-L180). Any caller with `UserRole.CLIENT` is immediately rejected with HTTP 403 Forbidden.
2. **Defense-in-Depth Service Layer Checks:** Updated `get_submission_for_user()` in [src/annotation/service.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/annotation/service.py#L342-L405) to explicitly check:
   - `if requester_user.role == UserRole.CLIENT.value: raise PermissionError(...)`
   - Requester must possess `LAWYER`, `SUPERVISING_LAWYER`, or `AUDITOR` role.
   - For `LAWYER` role, advocate verification (`AdvocateStatus.VERIFIED`) is strictly validated.

---

### SEC-03: Adjudication Dossier Sanitization & Payload JSON Removal

#### Root Cause
In `get_adjudication_dossier()`, primary annotator submissions were forwarded to senior counsel with the raw `payload_json` string included in `submission_1` and `submission_2`. Because annotator payloads originally contained embedded identification metadata (including model name and confidence), forwarding the raw JSON created a potential cognitive anchoring risk for adjudicators.

#### Remediation
1. **Evaluative Payload Allowlisting:** Added `PresentationFirewall.sanitize_evaluative_payload()` in [src/annotation/firewall.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/annotation/firewall.py#L110-L165). This method parses the stored JSON and applies explicit section-by-section allowlists (`HUMAN_EVALUATIVE_FIELD_ALLOWLISTS`):
   - `prediction_assessment`: `status`, `rationale`, `identified_risk_severity`
   - `evidence_support`: `status`, `rationale`, `passages`
   - `evidence_sufficiency`: `status`, `rationale`
   - `source_status`: `status`, `source_repository`, `provenance_classification`, `source_sha256`, `notes`
   - `source_applicability`: `currentness_status`, `applicability_status`, `rationale`
   - `version_consistency`: `status`, `finding_contract_version`, `active_contract_version`, `text_hash_matches`, `version_mismatch_details`
   - `final_reference_decision`: `reference_action`, `decision_rationale`, `confidence_in_decision`, `failure_category_if_withhold`
   - `epistemic_firewall_attestation`: 5 required boolean attestations
   - `annotation_provenance`: `annotator_code`, `annotator_qualification`, `annotation_phase`, `blinding_conditions`, `disagreement_flag`, `created_at`
2. **Elimination of Raw `payload_json`:** Both `filter_adjudication_dossier()` and `filter_submission_for_annotator()` permanently strip `payload_json` from the serialized response, returning only the parsed, validated `evaluative_payload`.
3. **Fail-Safe Parser:** Malformed or corrupt JSON strings safely evaluate to `{}` without raising uncaught exceptions or leaking unparsed text.

---

### SEC-04: Canonical Stage Synchronization & Strict Query Validation

#### Root Cause
`src/persistence/models.py` originally defined 7 annotation stages, omitting `STAGE_7_PEER_INDEPENDENT` and `STAGE_8_ADJUDICATION`. Furthermore, `PresentationFirewall.filter_candidate_for_annotator()` silently fell back to full record view on unrecognized stage query parameters, preventing callers from detecting typos.

#### Remediation
1. **Synchronized Canonical Enum:** Updated `AnnotationStage` in [src/persistence/models.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/persistence/models.py#L93-L104) to include all 9 stages:
   ```python
   class AnnotationStage(str, Enum):
       FULL_RECORD = "FULL_RECORD"
       STAGE_1_PREDICTION = "STAGE_1_PREDICTION"
       STAGE_2_SUPPORT = "STAGE_2_SUPPORT"
       STAGE_3_SUFFICIENCY = "STAGE_3_SUFFICIENCY"
       STAGE_4_SOURCE = "STAGE_4_SOURCE"
       STAGE_5_VERSION = "STAGE_5_VERSION"
       STAGE_6_DISPOSITION = "STAGE_6_DISPOSITION"
       STAGE_7_PEER_INDEPENDENT = "STAGE_7_PEER_INDEPENDENT"
       STAGE_8_ADJUDICATION = "STAGE_8_ADJUDICATION"
   ```
2. **Strict Stage Validation:** In both `get_blinded_candidate()` and `submit_annotation()` in `routes.py`, `stage` is validated against the canonical set. Any unrecognized stage immediately returns HTTP 400 Bad Request.
3. **Firewall Rejection:** In `PresentationFirewall.filter_candidate_for_annotator()`, any unrecognized stage string raises `ValueError`, eliminating silent presentation fallbacks.

---

### SEC-05: Research Integrity & Epistemic Boundaries

#### Scope Constraints Maintained
- **Task 042 Status:** Strictly `NOT STARTED`. No task board modifications or unauthorized stage initiations were conducted.
- **Tasks 028 and 029 Status:** Strictly `🔒 LOCKED`.
- **Model Invariance:** No machine learning models were retrained, fine-tuned, or evaluated. No decision thresholds (including `multilabel_threshold = 0.5` or workbench display constants) were recalibrated.
- **No Superiority Claims:** No scientific claims of algorithmic superiority, legal validity, or production readiness are made. The framework remains an empirical benchmarking and blinded data-collection apparatus.

---

## 3. Verification Test Results

### Targeted Security Remediation Tests
All 13 security regression tests in [tests/test_blinded_annotation_security_remediation.py](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/tests/test_blinded_annotation_security_remediation.py) passed:

| Test ID | Test Case | Target Security Invariant | Status |
|:---|:---|:---|:---:|
| **SEC-01.1** | `test_sec01_client_cannot_inject_model_identity_or_confidence` | Forged model ID/confidence discarded, server injects authoritative metadata | ✅ PASSED |
| **SEC-01.2** | `test_sec01_missing_candidate_metadata_causes_explicit_rejection` | Submissions for unverified candidates rejected with ValueError | ✅ PASSED |
| **SEC-01.3** | `test_sec01_flask_route_rejects_missing_candidate_with_400` | HTTP POST /submit returns 400 for unknown candidate | ✅ PASSED |
| **SEC-02.1** | `test_sec02_client_role_cannot_retrieve_internal_annotation_submission` | HTTP GET /submission/<id> returns 403 Forbidden for CLIENT role | ✅ PASSED |
| **SEC-02.2** | `test_sec02_service_layer_strictly_rejects_client_role` | Service layer throws PermissionError for CLIENT callers | ✅ PASSED |
| **SEC-02.3** | `test_sec02_unverified_lawyer_cannot_retrieve_submission` | Unverified advocates rejected from submission inspection | ✅ PASSED |
| **SEC-03.1** | `test_sec03_adjudication_dossier_excludes_raw_payload_json_and_prohibited_fields` | Raw `payload_json` stripped, evaluative allowlist projected | ✅ PASSED |
| **SEC-03.2** | `test_sec03_malformed_json_does_not_bypass_firewall` | Corrupt JSON safely resolves to empty dict | ✅ PASSED |
| **SEC-03.3** | `test_sec03_malicious_prohibited_fields_in_payload_are_stripped` | Nested injected model/confidence fields completely purged | ✅ PASSED |
| **SEC-04.1** | `test_sec04_invalid_stage_query_param_returns_400` | HTTP GET /candidate with invalid stage returns 400 | ✅ PASSED |
| **SEC-04.2** | `test_sec04_invalid_stage_in_submit_returns_400` | HTTP POST /submit with invalid stage returns 400 | ✅ PASSED |
| **SEC-04.3** | `test_sec04_presentation_firewall_raises_valueerror_on_unrecognized_stage` | Firewall raises ValueError on invalid stage name | ✅ PASSED |
| **SEC-04.4** | `test_sec04_all_canonical_stages_supported_without_error` | All 9 canonical stages correctly filtered without error | ✅ PASSED |

### Full Repository Regression Run
Execution of the complete test suite confirmed zero regressions across the codebase:
- **Total Tests Collected:** 650
- **Total Tests Passed:** 650 (100%)
- **Failures:** 0
- **Execution Duration:** 143.43 seconds (02:23)

---

## 4. Architectural Limitations & Current State

1. **Evaluation Corpus Binding:** In current developer and test configurations, `CandidateRegistry` resolves candidate findings against static database records (`ClauseFindingRecord`), registered memory fixtures, or verified demonstration benchmarks. Integration with a live 80–100 commercial contract evaluation corpus under Indian law requires milestone authorization under future experimental tasks.
2. **Epistemic Distinctions:** The system strictly separates:
   - *BM25 Lexical Proximity* $\ne$ *Legal Evidence Sufficiency*.
   - *SHA-256 Digest Integrity* $\ne$ *Sovereign Gazette Authenticity*.
   - *Automated Policy Output* $\ne$ *Ground-Truth Legal Reference Action*.
   All human judgments collected through this framework reflect independent advocate assessments blinded to automated system outputs.
