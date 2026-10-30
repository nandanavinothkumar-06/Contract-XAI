# TASK 033: COLLABORATIVE LAWYER REVIEW WORKBENCH
## Implementation, Architecture, Governance & Verification Report

---

### 1. Executive Summary & Objective

Task 033 implements a secure, functional, lawyer-in-the-loop contract review workbench for **CONTRACTRISK-XAI**. The workbench bridges automated ingestion (Task 030), cryptographic authentication and RBAC (Task 031), and verified Indian statutory legal retrieval (Task 032) into a cohesive human-in-the-loop review system.

Key principles enforced throughout Task 033:
1. **Decoupling AI Predictions from Legal Decisions**: AI findings remain strictly preliminary observations; only authorized advocates record binding decisions (`ACCEPT_AI_OBSERVATION`, `CORRECT_AI_OBSERVATION`, `REJECT_AI_OBSERVATION`, `NEEDS_MORE_EVIDENCE`, `NOT_APPLICABLE_TO_REVIEW`, `REQUIRES_CLIENT_CLARIFICATION`).
2. **Advocate Verification Gate**: Only verified advocates (`AdvocateStatus.VERIFIED`) can be assigned to reviews or execute legal assessments.
3. **Multi-Tenant Isolation & Role Boundaries**: Clients can only see their own contracts and disclosed recommendations; internal lawyer-only notes and comments are strictly redacted on the server.
4. **Immutable Original Preservation**: Uploaded contracts remain permanently immutable; revisions create versioned proposals (`DocumentRevisionRecord`) with SHA-256 content hashes and line diffs.
5. **No False Legal Guarantees**: Completed reviews do not certify legal compliance or guarantee legal outcomes; all reviews mandate a prominent statutory assessment disclaimer.
6. **Continuous Cryptographic Audit Trail**: Every review initiation, assignment, state transition, decision, comment, revision, completion, and reopening is recorded with SHA-256 hash chaining.

---

### 2. User Roles & Access Control Policy

The platform enforces four strictly separated user roles with deny-by-default server-side authorization:

| Role | Permissions & Access Boundaries |
| :--- | :--- |
| **CLIENT** | Upload contracts; view status of owned contracts; view approved findings disclosed by reviewing advocate; read released recommendations; respond to clarification requests; submit revision requests; view version history of owned documents. **Forbidden:** Accessing another client's documents, internal lawyer notes, or unreleased findings. |
| **LAWYER** | View review queue of assigned contracts; inspect clause segmentations; query authoritative Indian legal sources; record clause-level review decisions with mandatory rationale; author independent findings; post internal notes or client-visible comments; request clarifications; suggest revisions; complete reviews. **Prerequisite:** Must have `advocate_status == AdvocateStatus.VERIFIED`. |
| **SUPERVISING_LAWYER** | Full review queue visibility; assign and reassign reviews to verified advocates; supervisory override access; author findings; complete or reopen reviews; review and decide advocate credential verifications. |
| **AUDITOR** | Inspect tamper-evident audit logs and document review metadata for regulatory and compliance oversight. **Forbidden:** Viewing raw contract text or modifying reviews/decisions. |

---

### 3. Review Lifecycle State Machine

The persistent review workflow enforces 10 explicit states with strictly validated server-side transitions:

```
[DOCUMENT_SUBMITTED]
       │
       ├──► [PROCESSING] ──► [PROCESSING_FAILED] ──► [PROCESSING] (retry)
       │         │
       │         └──► [AWAITING_LAWYER_ASSIGNMENT]
       │                        │
       └────────────────────────┘
                                │ (Supervisor assigns verified lawyer)
                                ▼
                           [ASSIGNED]
                                │ (Advocate commences review)
                                ▼
                           [IN_REVIEW] ◄──────────────────────┐
                                │   ▲                          │
  (Revision proposed by lawyer) │   │                          │
                                ▼   │ (Lawyer resumes review)  │ (Audit Reopening)
                      [REVISION_REQUESTED]                     │
                                │   ▲                          │
  (Client submits reply/prop)   ▼   │                          │
                  [CLIENT_RESPONSE_RECEIVED]                   │
                                │                              │
                                ▼ (All prerequisites pass)     │
                       [REVIEW_COMPLETED]                      │
                                │                              │
                                └──► [REVIEW_REOPENED] ────────┘
```

#### Transition Validation Rules:
- Invalid state transitions (e.g., `DOCUMENT_SUBMITTED` directly to `REVIEW_COMPLETED`) are rejected server-side with HTTP 400 (`ValueError`).
- Every state transition records:
  - `review_id`
  - `from_state`
  - `to_state`
  - `actor_id`
  - `reason`
  - `timestamp`
- Reopening a completed review requires an authorized lawyer or supervisor, mandating an explicit, substantive justification.

---

### 4. Advocate Assignment & Verification Policy

1. **Eligibility Check**: A lawyer can only be assigned to a review if:
   - `user.role in ("LAWYER", "SUPERVISING_LAWYER")`
   - `user.advocate_status == "VERIFIED"`
   - `user.account_status == "ACTIVE"`
2. **Supervisor Authority**: Only `SUPERVISING_LAWYER` can perform initial assignments or reassignments.
3. **Prevention of Self-Assignment**: A client who owns a contract cannot be assigned as the reviewing advocate for their own contract.
4. **Honest Verification Provenance**: The system explicitly notes that advocate credentials are verified via **manual supervisory review of Bar Council enrollment IDs and state certificates**. No fictitious live Bar Council API is claimed.

---

### 5. Clause Findings & Lawyer Decision Controls

The workbench provides structured decision controls for every clause:

#### Decision Types:
- `ACCEPT_AI_OBSERVATION`: Advocate confirms the validity of the preliminary AI observation.
- `CORRECT_AI_OBSERVATION`: Advocate corrects or refines the scope/interpretation of the observation.
- `REJECT_AI_OBSERVATION`: Advocate rejects the observation as legally unfounded or inapplicable.
- `NEEDS_MORE_EVIDENCE`: Current evidence is inconclusive; further retrieval or client input required.
- `NOT_APPLICABLE_TO_REVIEW`: The clause does not present a relevant risk in this commercial context.
- `REQUIRES_CLIENT_CLARIFICATION`: Clause interpretation hinges on client business intent.

#### Invariants:
- **Mandatory Lawyer Rationale**: Every decision must be accompanied by an independent written rationale.
- **Independent Lawyer Findings**: Lawyers can author entirely new findings (`finding_origin = LAWYER_AUTHORED`), completely separate from AI models.
- **Client Disclosure Control**: Findings are hidden from the client workspace until explicitly marked `is_disclosed_to_client = True`.

---

### 6. Authoritative Indian Statutory Evidence Integration

Connecting directly to the verified corpus from Task 032 (comprising the Indian Contract Act 1872, Specific Relief Act 1963, Information Technology Act 2000, Arbitration and Conciliation Act 1996, Companies Act 2013, and DPDP Act 2023):

1. **Exact Statutory Extracts**: Retrieved passages display exact section numbers, official headings, and verified text.
2. **Currentness & Commencement Tracking**:
   - Provisions in force are marked `COMMENCED` (`IN_FORCE`).
   - Uncommenced provisions (e.g., DPDP Act substantive sections) are surfaced with explicit warnings (`UNKNOWN_COMMENCEMENT`).
   - Struck-down sections (e.g., IT Act Section 66A) are labelled `HISTORICAL_ONLY_VERSION`.
3. **Retrieval Score Semantics**: All scores are accompanied by a mandatory disclaimer:
   > *"Retrieval scores reflect heuristic lexical/BM25 relevance ranking metrics within the authoritative Indian statutory corpus. They do NOT represent probabilities that a legal provision applies or that a contract is legally compliant."*

---

### 7. Scoped Comments & Clarification Workflow

Comments support granular visibility scopes enforced server-side:

| Visibility Scope | Target Audience & Visibility Rules |
| :--- | :--- |
| `INTERNAL_LAWYER_ONLY` | Accessible only to reviewing lawyers and supervisors. **Strictly filtered out of client API responses.** Clients attempting to write internal notes are rejected with HTTP 403. |
| `CLIENT_VISIBLE` | General advice, recommendations, and explanations released for client viewing. |
| `CLARIFICATION_REQUEST` | Specific questions from advocate to client regarding intent, schedules, or missing context. |
| `CLIENT_RESPONSE` | Client answers to specific clarification threads. |

Clarification threads track resolution (`is_resolved = Boolean`, `resolved_by_id`, `resolved_at`).

---

### 8. Document Revisions & Versioning

1. **Original Immutability**: The original uploaded contract file, its SHA-256 fingerprint, and initial text snapshot remain permanently read-only.
2. **Versioned Revisions**: Proposed contract changes generate a `DocumentRevisionRecord` with:
   - Incremented version number (`version_number = 2, 3, ...`)
   - Proposed full text
   - Deterministic SHA-256 text checksum
   - Generated line-by-line unified diff vs original text
   - Change reason and author identity
3. **Formal Decisioning**: Lawyers or supervisors can mark revisions `ACCEPTED` or `REJECTED` with recorded rationale.

---

### 9. Review Completion Prerequisites & Disclaimer

A review can only be completed when all workflow requirements pass:
1. Review status must be `IN_REVIEW`.
2. Caller must be the assigned advocate or supervising lawyer.
3. Substantive completion summary must be provided.
4. **Zero Open Clarifications**: All `CLARIFICATION_REQUEST` items must be resolved.
5. **Mandatory Statutory Disclaimer Attached**:
   > *"This review reflects the professional assessment of the assigned advocate based on the provided document version and available statutory extracts at the time of review. It does not constitute a guarantee of legal outcome or certified statutory compliance."*

---

### 10. Database Models & Schema Extensions

The SQLAlchemy persistence layer (`src/persistence/models.py`) was compatibly extended:

- `ReviewRecord` (`reviews`): Review lifecycle, assignment links, version reviewed, completion metadata, disclaimer.
- `ReviewStateTransitionRecord` (`review_state_transitions`): State machine transition log (from_state, to_state, actor_id, reason).
- `ClauseFindingRecord` (`clause_findings`): Clause-to-finding association, decision, lawyer rationale, internal notes, statutory evidence JSON, client disclosure flag.
- `ReviewCommentRecord` (`review_comments`): Scoped threaded comments, resolution status.
- `DocumentRevisionRecord` (`document_revisions`): Versioned text revisions, original SHA-256 reference, diff summary.

---

### 11. Cryptographic Audit Trail Events

All actions emit SHA-256 tamper-evident hash-chained events to `audit_events`:
- `REVIEW_CREATED`
- `LAWYER_ASSIGNED`
- `LAWYER_REASSIGNED`
- `REVIEW_OPENED`
- `FINDING_CREATED`
- `LAWYER_DECISION_RECORDED`
- `COMMENT_ADDED`
- `COMMENT_RESOLVED`
- `CLIENT_CLARIFICATION_SUBMITTED`
- `REVISION_PROPOSED`
- `REVISION_ACCEPTED`
- `REVIEW_COMPLETED`
- `REVIEW_REOPENED`
- `AUTHORIZATION_FAILURE`
- `UNAUTHORIZED_ACCESS_ATTEMPT`

Chain continuity is validated using `AuditVerifier` walking previous-hash links.

---

### 12. Setup, Execution & Test Commands

#### Run Focused Workbench Tests:
```powershell
python -m pytest tests/test_lawyer_workbench.py -v
```

#### Run Combined Integration Suite (Tasks 030–033):
```powershell
python -m pytest tests/test_lawyer_workbench.py tests/test_indian_legal_sources.py tests/test_auth_rbac.py tests/test_ingestion_persistence.py -v
```

#### Run Full Project Regression Suite:
```powershell
python -m pytest tests/
```

---

### 13. Known Limitations & Scope Boundaries

1. **Bar Council Integration**: Manual supervisory review is utilized as no public automated Bar Council API is available.
2. **Certified PDF Reports (Task 034)**: Report generation, PDF digital signing, and client certification workflows remain strictly **LOCKED** for Task 034.
3. **Legal Advice Boundaries**: System outputs do not constitute legal advice or automated compliance certifications.
