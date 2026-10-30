# Audit Trail

## 1. Purpose
The Audit Trail module (`src/audit`) provides a provenance-aware, tamper-evident logging framework for ContractRisk-XAI. It meticulously records system operations, model predictions, evidence extractions, and lawyer review decisions. 

## 2. Architecture
The architecture comprises an `AuditStore` (an append-only event repository), an `AuditLogger` (handles structured event emission and hashing), and an `AuditVerifier` (enforces integrity checks on the chain). Query functions support retrieving events by prediction, review, document, or partition IDs without mutating data.

## 3. Event Schema
Every `AuditEvent` captures:
- `event_id`, `event_type`, `event_version`
- `timestamp` (Strictly ISO-8601 UTC)
- Identifiers (`source_document_id`, `clause_id`, `partition`, `prediction_id`, `review_id`)
- `actor_type`, `actor_reference`
- Module info (`module_name`, `module_version`)
- References (`input_references`, `output_references`, `configuration_reference`)
- Payload (`event_payload`)
- Tamper-evident chaining (`previous_event_hash`, `event_hash`)

## 4. Event Types
The supported events map to the core workflow operations:
- `DOCUMENT_INGESTED`, `PREPROCESSING_COMPLETED`, `CLAUSE_SEGMENTED`
- `MODEL_PREDICTION`, `EVIDENCE_EXTRACTED`, `CONTEXT_BUILT`, `GRAPH_BUILT`
- `RETRIEVAL_PERFORMED`, `MISSING_PROVISION_ASSESSED`, `LEGAL_SOURCE_RETRIEVED`
- `ABSTENTION_DECIDED`, `LAWYER_REVIEW_CREATED`

## 5. Actor Types
We distinguish between actors explicitly:
- `SYSTEM`
- `REVIEWER`
- `TEST`

## 6. Provenance
Every event maintains explicit identifiers to trace operations back to specific documents, clauses, and predictions. The system leverages the existing ContractRisk-XAI provenance identifiers. It rejects events that exhibit contradictory document/partition references.

## 7. Hash-Chain Design
The system uses a strictly sequential, cryptographic hash chain to detect modifications or reordering:
- The genesis event sets `previous_event_hash` to `null`.
- Every subsequent event references the immediate predecessor's `event_hash`.
- The `event_hash` is computed as the SHA-256 digest of the canonical JSON serialization of the event attributes.

## 8. Canonical Serialization
Serialization ensures that identical events produce identical byte representations. It relies on standard JSON dumping with sorted keys and no structural whitespace.

## 9. Integrity Verification
The `AuditVerifier` guarantees:
1. Event ordering is unbroken.
2. The `event_hash` correctly matches the SHA-256 payload.
3. The `previous_event_hash` matches the predecessor.
4. Duplicate `event_id`s are forbidden.
5. Incomplete provenance triggers an `INVALID_REFERENCE` status.

It returns `VALID`, or explicit failure modes like `INVALID_HASH`, `INVALID_PREVIOUS_HASH`, `INVALID_ORDER`, etc. It does not silently repair corrupted events.

## 10. Storage
The `AuditStore` maintains an in-memory append-oriented list for the runtime duration. It issues deep copies on reads to prevent caller mutation of stored events.

## 11. Querying
Read-only query functions allow safe retrieval of chronological histories scoped to specific predictions, documents, or reviews.

## 12. Privacy Considerations
The `event_payload` must strictly avoid embedding full contract raw text. We prefer logging metadata, references, offsets, artifact identifiers, and cryptographic hashes to minimize privacy exposure.

## 13. Limitations
The hash chain operates inside the single `AuditStore` lifecycle context. It is an internal organizational tool to guarantee operational reproducibility and chronological integrity within the software's execution environment. 

## 14. Synthetic-Test Policy
All simulated test events use `is_test_fixture=True`.

## 15. Distinction Between Tamper-Evident and Tamper-Proof
This framework is **TAMPER-EVIDENT**, not "tamper-proof". While no internal logic mutates records, and the verifier will loudly flag any manual memory manipulation, a sufficiently privileged hostile actor could theoretically recalculate and overwrite the entire chain.

## 16. Distinction Between Auditability and Legal Correctness
> [!CAUTION]
> The audit trail is merely provenance infrastructure.
It does **NOT**:
- Determine legal validity, enforceability, or illegality.
- Establish legal compliance, precedent, or legal authority.

**NO EMPIRICAL SECURITY OR LEGAL AUDIT PERFORMED.** 
**NO PROJECT EXPERIMENTAL RESULTS GENERATED.**
