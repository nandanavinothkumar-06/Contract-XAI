# Candidate Generation Pipeline and Evaluation Metric Harness

**Project:** `CONTRACTRISK-XAI`  
**Module:** `src/candidates/` and `src/evaluation/abstention_eval.py`  
**Purpose:** Technical foundation for candidate finding generation and defensible evaluation of evidence-aware abstention policies.  
**Date:** 2026-10-17  
**Status:** IMPLEMENTED (Technical Foundation / Synthetic Test Verified)  
**Strict Research Boundary:** This implementation does **not** evaluate a real-world legal pilot, does **not** validate the underlying model for Indian commercial law, and does **not** establish research superiority or legal correctness.

---

## 1. Architectural Overview and System Boundary

The candidate generation and evaluation subsystem bridges raw contract text snapshots with downstream research evaluation. It isolates candidate prediction generation from client presentation, enforces cryptographic provenance, mandates defensive label-space validation, and implements a mathematically defensible metric harness for comparing confidence-only and evidence-aware abstention policies.

```
+--------------------------------------------------------------------------------------------------+
|                            CANDIDATE GENERATION & EVALUATION HARNESS                             |
+==================================================================================================+
|  [Contract Text Snapshot] ──> [Segmented Clauses]                                                |
|                                     │                                                            |
|                                     ▼                                                            |
|                    CandidateGenerationPipeline                                                   |
|                    - Model inference (PyTorch LegalBERT or batch input)                          |
|                    - Defensive Label Mapping (VALID_INDIAN_RISK_CATEGORIES)                      |
|                    - Confidence Semantics (SIGMOID / SOFTMAX / UNCALIBRATED)                     |
|                    - Statutory BM25 Evidence & EQ Status (TRACEABLE, etc.)                       |
|                    - Document Version Consistency (CONSISTENT vs STALE)                          |
|                    - Deterministic Finding ID Generation (SHA-256)                               |
|                    - Deduplication Protocol (DuplicateFindingEntry log)                          |
|                    - Client Isolation (is_disclosed_to_client = False)                           |
|                                     │                                                            |
|                                     ▼                                                            |
|                         [Frozen Candidate Pool (F)]                                              |
|                                     │                                                            |
|                 ┌───────────────────┴───────────────────┐                                        |
|                 ▼                                       ▼                                        |
|       [Policy A: Confidence]                 [Policy B: Evidence-Aware]                          |
|       (threshold tau_conf)                   (5-Tier Precedence Cascade)                         |
|                 │                                       │                                        |
|                 └───────────────────┬───────────────────┘                                        |
|                                     ▼                                                            |
|                         Abstention Evaluation Harness                                            |
|                         (src/evaluation/abstention_eval.py)                                       |
|                         - Primary UFR (WITHHOLD fraction; undef if empty)                        |
|                         - Human-Review Safety Discrepancies reported separately                  |
|                         - Useful Finding Coverage (UFC; review != retain)                        |
|                         - Matched Coverage (|UFC_A - UFC_B| <= 0.02)                             |
|                         - SEAR (Stale Document Version Acceptance Rate)                          |
|                         - Deterministic Tie-Breaking (SortKey = (-conf, id))                     |
+--------------------------------------------------------------------------------------------------+
```

---

## 2. Candidate Generation Pipeline (`src/candidates/`)

### 2.1 Capabilities Actually Supported
1. **Clause-Level Candidate Generation:** Ingests clause text segments with contract metadata (`contract_id`, `contract_version`, `document_content_hash`, `clause_id`).
2. **Defensive Label Mapping:** Validates raw model class labels against `VALID_INDIAN_RISK_CATEGORIES`. If an explicit mapping exists in `label_mapper`, the mapped category is assigned with `LabelMappingStatus.MAPPED`. If a raw label cannot be defensibly mapped, `LabelMappingStatus.UNSUPPORTED_LABEL_MAPPING` is assigned and recorded in `missing_capabilities`. The pipeline strictly **refuses to invent fake mappings**.
3. **Explicit Confidence Semantics:** Distinguishes between `MULTILABEL_SIGMOID_SCORE` and `MULTICLASS_SOFTMAX_SCORE`. The field `confidence_is_calibrated` is set to `False` by default; raw scores are never misrepresented as calibrated posterior probabilities.
4. **Deterministic Finding Identification:** Generates a deterministic SHA-256 finding identifier formatted as a standard 36-character UUID string:
   $$\text{ID} = \text{SHA256}(\text{contract\_id} : \text{version} : \text{clause\_id} : \text{category} : \text{raw\_label} : \text{model\_id})$$
5. **Document Version Consistency:** Checks the finding draft version against the document's active revision. Mismatches are flagged as `VersionConsistencyStatus.STALE` and trigger version-stale evidence cascades.
6. **Statutory Retrieval Attachment:** Connects to `ClauseEvidenceRetriever` to attach lexical passages and the 6 discrete evidence quality states (`TRACEABLE`, `PARTIAL`, `INSUFFICIENT`, etc.).
7. **Deterministic Deduplication:** Implements the canonical deduplication key:
   $$\text{DeduplicationKey} = (\text{contract\_id}, \text{version}, \text{clause\_id}, \text{prediction\_category}, \text{normalize}(\text{text}))$$
   Preserves distinct multi-label risk categories on the same clause segment while collapsing exact duplicates and logging them to `DuplicateFindingEntry`.
8. **Client Disclosure Isolation:** Enforces `is_disclosed_to_client = False` on all generated candidate records. Candidate generation never bypasses lawyer review or auto-discloses findings.

### 2.2 Capabilities NOT Supported (Model & Domain Limitations)
- **Zero Indian Legal Adaptation:** The underlying LegalBERT model (`nlpaueb/legal-bert-base-uncased`) was trained on US SEC corporate filings (LEDGAR). Its internal representations reflect US securities agreements, not Indian contract drafting conventions under the Indian Contract Act 1872 or Specific Relief Act 1963.
- **No Textual Finding Generation:** The model is a classification model emitting class indices/probabilities, not a generative language model. The pipeline strictly leaves `candidate_finding_text = None` rather than fabricating synthetic summaries.
- **No Sovereign Gazette Verification:** Checksums attached to retrieved passages represent local snapshot file integrity; they do not certify sovereign gazette publication.

---

## 3. Evaluation Data Contract (`src/evaluation/abstention_eval.py`)

The evaluation harness operates on an explicit input/output data contract separating three orthogonal objects:

1. **Candidate Finding Records (`CandidateFindingRecord`):** The frozen candidate pool ($\mathcal{F}$) holding input clause text, confidence score $c(F)$, and version metadata.
2. **Reference Annotations (`ReferenceAnnotationRecord`):** Ground-truth human legal decisions assigned by authorized legal annotators:
   - `RETAIN`: Substantively valid risk, legally grounded, active contract version. Safe for unassisted client presentation.
   - `WITHHOLD`: Defective finding (`INCORRECT`, `STALE`, `REPEALED`, or low/med `UNSUPPORTED`). Unsafe to surface.
   - `HUMAN_REVIEW_REQUIRED`: Substantively genuine risk with evidentiary gaps, textual diffs, contractual overrides, or ambiguity.
   - `NOT_ASSESSABLE`: Corrupt text, unreadable OCR. Excluded from evaluable denominators.
3. **Policy Decisions (`PolicyDecisionRecord`):** Algorithmic operational actions emitted by an evaluated policy:
   - `ACCEPT` / `RETAIN`: Automatically surface to client.
   - `WITHHOLD`: Suppress from client report.
   - `REVIEW_REQUIRED`: Route to advocate review queue.

---

## 4. Evaluation Metrics Specification

| Metric | Exact Mathematical Formula | Valid Denominator | Edge Cases & Invariants |
| :--- | :--- | :--- | :--- |
| **Unsupported-Finding Rate (UFR)** | $\frac{\sum_{F \in \text{Retained}_{\text{eval}}} \mathbb{I}(y_{\text{ref}}(F) = \text{WITHHOLD})}{\|\text{Retained}_{\text{eval}}\|}$ | $\|\text{Retained}_{\text{eval}}\|$ (evaluable retained candidates) | **STRICT INVARIANT:** If retained denominator is 0, $\text{UFR} = \text{None}$ (`UNDEFINED`). Never reported as 0.0%. Safety discrepancies ($y_{\text{ref}} = \text{REVIEW}$) reported separately. |
| **Useful-Finding Coverage (UFC)** | $\frac{\sum_{F \in \text{Retained}_{\text{eval}}} \mathbb{I}(y_{\text{ref}}(F) = \text{RETAIN})}{\sum_{F \in \mathcal{F}_{\text{eval}}} \mathbb{I}(y_{\text{ref}}(F) = \text{RETAIN})}$ | Total reference-`RETAIN` in evaluable corpus | Candidates routed to `REVIEW_REQUIRED` do **NOT** count as automatically retained in numerator. |
| **Retention Rate (RR)** | $\frac{\|\text{Retained}\|}{\|\mathcal{F}\|}$ | Total candidate pool $\|\mathcal{F}\|$ | Evaluates overall operational retention throughput. |
| **Unnecessary Abstention Rate (UAR)** | $\frac{\sum_{F \in \text{Abstained}_{\text{eval}}} \mathbb{I}(y_{\text{ref}}(F) = \text{RETAIN})}{\|\mathcal{F}_{\text{eval}}\|}$ | Total evaluable candidates $\|\mathcal{F}_{\text{eval}}\|$ | Reported with explicit breakdown: `uar_withheld` vs `uar_human_review`. |
| **Stale-Evidence Acceptance Rate (SEAR)** | $\frac{\sum_{F \in \text{Retained}} \mathbb{I}(\text{Version}(F) = \text{STALE})}{\|\text{Retained}\|}$ | Total retained candidates | Measures contract draft version consistency. Unknown version status reported separately as `sear_unknown_rate`. |
| **Human-Review Workload (HRW)** | $\frac{\|\text{Review\_Required}\|}{\|\mathcal{F}\|}$ | Total candidate pool $\|\mathcal{F}\|$ | Quantifies advocate review burden. |
| **Unassessable Rate (UR)** | $\frac{\sum_{F \in \mathcal{F}} \mathbb{I}(y_{\text{ref}}(F) = \text{NOT\_ASSESSABLE})}{\|\mathcal{F}\|}$ | Total candidate pool $\|\mathcal{F}\|$ | Primary data quality metric tracking input corruption. |

### Coverage Matching Diagnostics
- Comparison between Policy A ($\pi_{\text{conf}}$) and Policy B ($\pi_{\text{evid}}$) strictly enforces the prespecified absolute tolerance:
  $$|\text{UFC}(\pi_A) - \text{UFC}(\pi_B)| \le 0.02$$
- If within tolerance, `status = "MATCHED_COVERAGE_ACHIEVED"` and $\Delta\text{UFR} = \text{UFR}_A - \text{UFR}_B$ is computed.
- If outside tolerance, `status = "MATCHED_COVERAGE_UNACHIEVED"`. Forced interpolation or claiming superiority without coverage parity is strictly prohibited.

---

## 5. What Must Happen Before a Real Evaluation or Feasibility Pilot

Before executing any evaluation or feasibility study, the following external prerequisites must be completed under explicit user authorization:

1. **Target Contract Corpus:** Curate 10–12 public Indian commercial contracts, sanitize all PII, and record immutable SHA-256 text snapshots.
2. **Indian Risk Model Adaptation:** Fine-tune or calibrate a sequence classifier on Indian commercial contract clauses or establish a validated mapping dictionary from model classes to Indian risk categories.
3. **Blinded Annotation Interface:** Build the presentation firewall stripping confidence scores and model IDs prior to advocate review.
4. **Dual Annotator Recruitment:** Onboard two enrolled Indian advocates and one senior adjudicator.
5. **Frozen Policy Implementation:** Implement the executable 5-tier evidence-aware policy and the continuous baseline threshold sweep script.
6. **Task Board Authorization:** Formally authorize and initiate Task 042 (currently **NOT STARTED**).
