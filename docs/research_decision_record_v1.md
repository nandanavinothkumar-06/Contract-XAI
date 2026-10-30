# RESEARCH DECISION RECORD (RDR-001)
## Strategy A: Evidence-Aware Abstention Policy Evaluation

**Document Identifier:** RDR-001-STRATEGY-A-V1  
**Version:** 1.0.0  
**Date:** 2026-10-17  
**Status:** APPROVED RESEARCH DESIGN SPECIFICATION  
**Scope:** CONTRACTRISK-XAI Methodological Protocol  

---

> [!WARNING]
> **RESEARCH-DESIGN DECISION RECORD ONLY — NOT EXPERIMENTAL EVIDENCE**  
> This document formalizes binding methodological decisions, system boundaries, and prerequisites for future, separately authorized research. It does **not** constitute evidence of experimental validation, empirical superiority, statutory completeness, legal certification, or production readiness. Tasks 028 and 029 remain strictly `🔒 LOCKED`. Task 042 remains strictly `NOT STARTED`.

---

## 1. Context and Purpose

This record consolidates the approved methodological design decisions for evaluating evidence-aware abstention in `CONTRACTRISK-XAI`. Its purpose is to prevent repeated design debates, establish immutable experimental invariants, and provide a stable, version-controlled reference for subsequent implementation tasks.

Statements are classified using four explicit normative tags:
- `[DECISION]`: Binding methodological rule approved for the research protocol.
- `[EXISTING LIMITATION]`: Verified current state constraint of the repository or corpus.
- `[PREREQUISITE]`: Required engineering or governance condition that must be completed before real-contract annotation.
- `[UNRESOLVED ISSUE]`: Methodological question to be resolved during pilot execution or by project-owner determination.

---

## 2. Research Question and Core Hypothesis

1. `[DECISION]` **Primary Research Question:**  
   *"When candidate contract-risk findings are proposed for Indian commercial contract clauses, does conditioning automated retention on evidence sufficiency, statutory-source status, and document-version consistency reduce the unsupported-finding rate ($\text{UFR}$) compared with confidence-only thresholding at matched useful-finding coverage ($\text{UFC}$), and what human-review workload ($\text{HRW}$) does this introduce?"*

2. `[DECISION]` **Primary Testable Hypothesis ($H_1$):**  
   At prespecified matched useful-finding coverage ($|\text{UFC}_{\text{conf}} - \text{UFC}_{\text{evid}}| \le 0.02$) on held-out contract clusters, the evidence-aware policy achieves a strictly lower unsupported-finding rate than the confidence-only baseline:
   $$\Delta\text{UFR}_{@\text{MatchedUFC}} = \text{UFR}(\pi_{\text{conf}}) - \text{UFR}(\pi_{\text{evid}}) > 0$$

---

## 3. Study Strategy and Boundaries

1. `[DECISION]` **Selection of Strategy A:**  
   The project proceeds with Strategy A: evaluating the triage reliability of an evidence-aware abstention policy on a common, frozen candidate benchmark.

2. `[DECISION]` **Deferral of Strategy B:**  
   Strategy B (curating large-scale training data and training a bespoke Indian commercial contract risk classifier) is formally deferred. Conflating model training with abstention evaluation introduces severe confounding variables, acute class imbalance, and unsustainable annotation overhead.

3. `[EXISTING LIMITATION]` **Candidate-Triage Scope:**  
   Strategy A evaluates the reliability of triage over *proposed* candidate findings. It does **not** evaluate clause-level false negatives (missing risks that a candidate generator failed to propose) and does not establish end-to-end contract risk discovery recall.

4. `[EXISTING LIMITATION]` **No Production or Clinical Legal Claims:**  
   The study evaluates experimental decision policies in an offline setting. It does not establish clinical legal reliability, comprehensive Indian legal coverage, or fitness for unassisted commercial deployment.

---

## 4. Candidate Generation and Benchmark Freezing

1. `[DECISION]` **Frozen Candidate Benchmark:**  
   All evaluated policies must operate on the exact same immutable pool of candidate findings ($N \approx 150\text{--}200$ across 15–20 contracts for the feasibility pilot).

2. `[DECISION]` **Candidate Generation Mechanism:**  
   Candidates must be generated via a reproducible, documented process. Where supported, the candidate pipeline (`src/candidates/pipeline.py`) is used. Controlled edge cases (stale drafts, repealed sections, non-statutory commercial risks) must be populated using clearly identified, audited fixtures.

3. `[EXISTING LIMITATION]` **Unadapted Neural Model:**  
   The repository's LegalBERT model weights (`nlpaueb/legal-bert-base-uncased`) are derived from US SEC filings and UK legislation. The model has zero domain adaptation to Indian commercial drafting. It must never be represented as a validated Indian-law risk classifier.

4. `[DECISION]` **Candidate Provenance Invariants:**  
   Every candidate record (`CandidateFindingRecord`) must serialize immutable provenance: `candidate_finding_id`, `contract_id`, `contract_version`, `document_content_hash`, `clause_id`, `prediction_category`, continuous `confidence_value` with `is_calibrated = False`, and `generator_origin`.

5. `[PREREQUISITE]` **Deduplication Key Patch:**  
   The deduplication key in `src/candidates/deduplication.py` (`contract_id:version:clause_id:category:norm_text`) treats empty finding text as `""`, risking false merging of distinct candidate proposals in the same category on the same clause. The key must be patched to require a standardized finding summary or generator identifier before candidate pool ingestion.

6. `[DECISION]` **Benchmark Freezing:**  
   Candidate generation must conclude and be frozen prior to annotation. The candidate dataset must be serialized to JSONL with an immutable SHA-256 manifest. No candidates may be added, deleted, or reordered once annotation begins.

---

## 5. Independent Reference Annotation Protocol

1. `[DECISION]` **Ten Decoupled Evaluation Dimensions:**  
   Annotators independently evaluate ten orthogonal dimensions:
   1. Substantive Prediction Correctness (`CORRECT`, `PARTIALLY_CORRECT`, `INCORRECT`, `UNCLEAR`, `NOT_ASSESSABLE`).
   2. Evidence Support (`SUPPORTED`, `PARTIALLY_SUPPORTED`, `UNSUPPORTED`, `INSUFFICIENT_INFO`, `NOT_APPLICABLE`).
   3. Evidence Sufficiency (`SUFFICIENT`, `INSUFFICIENT`, `CONFLICTING`, `MISSING`, `NOT_APPLICABLE`).
   4. Source Authenticity (`VERIFIED_RESEARCH_PROTOCOL`, `PARTIALLY_VERIFIED`, `UNVERIFIED`, `NOT_APPLICABLE`).
   5. Textual Concordance (`CONCORDANT`, `TEXT_DIFFERENCE`, `EDITORIAL_NOTES_PRESENT`, `NOT_APPLICABLE`).
   6. Source Currentness (`IN_FORCE_CONFIRMED`, `COMMENCEMENT_PENDING`, `REPEALED_OR_SUPERSEDED`, `JUDICIALLY_INVALIDATED`).
   7. Legal Applicability (`APPLICABLE_TO_CONTRACT`, `INAPPLICABLE_SCOPE`, `CONTRACTUAL_OVERRIDE_PERMITTED`).
   8. Document-Version Consistency (`CONSISTENT`, `STALE`, `UNKNOWN`, `NOT_APPLICABLE`).
   9. Reference Disposition (`RETAIN`, `WITHHOLD`, `HUMAN_REVIEW_REQUIRED`, `NOT_ASSESSABLE`).
   10. Input Assessability (`ASSESSABLE`, `NOT_ASSESSABLE`).

2. `[DECISION]` **Independence from Policy Decision Rules:**  
   Reference labels must be assigned based on substantive legal analysis and factual evidence, **never** by applying the evidence-aware policy's 5-tier decision code. The policy output must not serve as the reference answer.

3. `[DECISION]` **Handling Partially Correct Findings:**  
   Partially correct findings must not be automatically defaulted to `RETAIN` or `WITHHOLD`. Annotators must record explicit written reasoning. If the finding contains actionable risk but minor framing defects, it routes to `HUMAN_REVIEW_REQUIRED` (or adjudicated by Senior Counsel).

4. `[DECISION]` **Safety Separation:**  
   Substantive correctness is strictly separated from automated disclosure safety. An accurate high-severity risk prediction that lacks verified statutory backing must not be automatically disclosed to a client without lawyer sign-off (`HUMAN_REVIEW_REQUIRED`).

---

## 6. Annotator Blinding and Storage Integrity

1. `[DECISION]` **Presentation Firewall Rules:**  
   During independent annotation, annotators must be strictly blinded to:
   - Model identity and checkpoint version.
   - Numerical confidence scores, logits, and calibrated probabilities.
   - Retrieval ranking, similarity scores, and BM25 metrics.
   - System-assigned evidence quality statuses (`TRACEABLE`, `PARTIAL`, etc.).
   - Baseline and evidence-aware policy recommendations (`ACCEPT`, `WITHHOLD`, `REVIEW_REQUIRED`).
   - Peer annotator ratings, rationales, and identity.

2. `[PREREQUISITE]` **Server-Side Blinding Implementation:**  
   Blinding must be enforced at the server-side API layer (`src/review/`). The client interface must not receive sensitive fields in HTTP responses.

3. `[PREREQUISITE]` **Independent Annotation Storage & Locking:**  
   Annotator submissions must be stored in independent staging tables. Upon submission, records are cryptographically sealed with a SHA-256 digest and timestamped. Locked submissions cannot be edited.

4. `[DECISION]` **Adjudication Access Gate:**  
   Senior Counsel adjudication is unlocked only after *both* primary annotators have submitted locked records. Senior Counsel sees both primary rationales, but remains strictly blinded to model confidence and policy recommendations.

---

## 7. Comparative Policy Evaluation Design

1. `[DECISION]` **Compared Policies:**  
   - **Policy A (Baseline):** Continuous confidence-only thresholding ($\pi_{\text{conf}}$). Retains candidate $F$ if $c(F) \ge \tau_{\text{conf}}$; else withholds.
   - **Policy B (Intervention):** Five-tier hierarchical precedence policy ($\pi_{\text{evid}}$) implemented in `src/abstention/evidence_policy.py`.

2. `[DECISION]` **Contract-Clustered Split Separation:**  
   The candidate pool must be partitioned at the **Contract Document Cluster** level:
   - **Validation Split (40%):** Used exclusively to sweep and select the baseline threshold $\tau_{\text{conf}}^*$ matching Policy B's validation coverage.
   - **Held-Out Test Split (60%):** Evaluated once with frozen policies and frozen $\tau_{\text{conf}}^*$. Test-split reference labels must never be used to adjust thresholds.

3. `[DECISION]` **Matched-Coverage Protocol:**  
   - Coverage tolerance is prespecified at $\epsilon = \pm 0.02$ on Useful-Finding Coverage ($\text{UFC}$).
   - If $|\text{UFC}_{\text{conf}}(\tau^*, \text{test}) - \text{UFC}_{\text{evid}}(\text{test})| \le 0.02$, comparison is valid; report $\Delta\text{UFR}$.
   - If $|\Delta\text{UFC}| > 0.02$, $\Delta\text{UFR}$ is suppressed, and `MATCHED_COVERAGE_UNACHIEVED` is reported. Continuous interpolation across discontinuous coverage points is strictly forbidden.

4. `[DECISION]` **Deterministic Non-Outcome Tie-Breaking:**  
   When ranking candidates for quantile thresholds, ties must be resolved strictly using:
   $$\text{SortKey}(F) = (-c(F), \text{candidate\_finding\_id})$$
   Sorting must never inspect reference labels or policy outcomes.

5. `[DECISION]` **Treatment of Operational Outcomes:**  
   - `REVIEW_REQUIRED`: Candidates routed to human review are **not** counted as automatically retained in UFC or UFR. They are tracked as Human-Review Workload ($\text{HRW}$).
   - `NOT_ASSESSABLE`: Excluded from evaluable denominators in UFR and UFC; tracked under Unassessable Rate ($\text{UR}$).
   - Safety Discrepancies: Candidates labeled `HUMAN_REVIEW_REQUIRED` by reference annotators but automatically retained by a policy are tracked as a distinct safety discrepancy metric.

---

## 8. Prespecified Outcomes and Metrics

All metrics are computed via `src/evaluation/abstention_eval.py`:

| Metric Name | Mathematical Definition | Evaluation Role | Target / Direction |
| :--- | :--- | :---: | :---: |
| **Unsupported-Finding Rate ($\text{UFR}$)** | $\frac{\sum \mathbb{I}(y_{\text{ref}} = \text{WITHHOLD})}{\|\text{Retained}_{\text{eval}}\|}$ | **Primary Safety Metric** | Lower is better; undefined if denominator $= 0$. |
| **Matched Coverage Difference ($\Delta\text{UFR}$)** | $\text{UFR}(\pi_{\text{conf}}) - \text{UFR}(\pi_{\text{evid}})$ | **Primary Contrast Estimand** | Strictly $> 0$ at matched UFC ($\pm 0.02$). |
| **Useful-Finding Coverage ($\text{UFC}$)** | $\frac{\sum \mathbb{I}(y_{\text{ref}} = \text{RETAIN} \land \text{Retained})}{\sum \mathbb{I}(y_{\text{ref}} = \text{RETAIN})}$ | **Primary Utility Constraint** | Target matched within $\pm 0.02$. |
| **Human-Review Workload ($\text{HRW}$)** | $\frac{\|\text{Review\_Required}\|}{\|\mathcal{F}\|}$ | **Operational Cost Metric** | Feasibility pilot target: $\le 35.0\%$. |
| **Stale-Evidence Acceptance ($\text{SEAR}_{\text{stale}}$)** | $\frac{\sum \mathbb{I}(\text{Version} = \text{STALE} \land \text{Retained})}{\|\text{Retained}\|}$ | **Fatal Defect Metric** | Must equal $0.0\%$ under Policy B. |
| **Unknown-Lineage Acceptance ($\text{SEAR}_{\text{unknown}}$)** | $\frac{\sum \mathbb{I}(\text{Version} = \text{UNKNOWN} \land \text{Retained})}{\|\text{Retained}\|}$ | **Provenance Gap Metric** | Tracked separately from stale errors. |
| **Unnecessary Abstention Rate ($\text{UAR}$)** | $\frac{\sum \mathbb{I}(y_{\text{ref}} = \text{RETAIN} \land \text{Abstained})}{\|\mathcal{F}_{\text{eval}}\|}$ | **Utility Loss Metric** | Broken down into withheld and review counts. |
| **Unassessable Rate ($\text{UR}$)** | $\frac{\sum \mathbb{I}(y_{\text{ref}} = \text{NOT\_ASSESSABLE})}{\|\mathcal{F}\|}$ | **Data Quality Metric** | Must be $\le 5.0\%$ of total candidate pool. |
| **Inter-Annotator Agreement** | Cohen's $\kappa$ on dual annotations | **Reliability Gate** | $\kappa \ge 0.70$ on disposition; $\ge 0.75$ on correctness. |

---

## 9. Feasibility Pilot Scope and Limitations

1. `[DECISION]` **Provisional Planning Scope:**  
   The feasibility pilot targets 15–20 eligible public Indian commercial contracts (~60–80 clauses, 150–200 candidate findings).

2. `[EXISTING LIMITATION]` **Non-Confirmatory Nature:**  
   These sample targets are provisional planning heuristics, not a validated power calculation. The pilot does **not** establish statistical superiority.

3. `[DECISION]` **Pilot Assessment Objectives:**  
   The feasibility pilot is authorized exclusively to assess:
   - Contract acquisition, parsing, and PII redaction feasibility.
   - Candidate generator diversity across all seven archetypes.
   - Annotation completion time (target: 10–15 min/finding).
   - Inter-annotator agreement ($\kappa$) and adjudication frequency.
   - Unassessable rate ($\text{UR}$) and data quality defects.
   - Verification of the evaluation script on real human annotations.
   - Empirical estimation of within-contract cluster correlation ($\rho$).

4. `[DECISION]` **Strict Ban on Label Recycling:**  
   If the feasibility pilot results in modifications to the annotation schema, guidelines, prompt templates, candidate generator, or policy thresholds, **pilot annotations cannot be reused as test data in the subsequent confirmatory study.** Reusing pilot labels to confirm a modified policy constitutes circular confirmation bias.

---

## 10. Legal, Statutory, and Data Governance Constraints

1. `[EXISTING LIMITATION]` **Curated Statutory Scope:**  
   The reference corpus contains exactly 40 commercial provisions across six central Acts (`data/legal_sources/corpus_manifest.json`). It does not represent comprehensive Indian commercial law. Candidate findings outside these 40 provisions will trigger retrieval omissions.

2. `[DECISION]` **Epistemic Anti-Assumptions:**  
   The protocol explicitly enforces that:
   - Missing retrieved evidence does not prove a clause is legally safe.
   - A cryptographic checksum does not prove sovereign statutory authority.
   - A textual match does not establish legal applicability to a given transaction.
   - A high model confidence score does not establish finding correctness.
   - Routing to human review is never counted as automated acceptance.

3. `[DECISION]` **Data Governance Invariants:**  
   - Only contracts with documented open licenses (CC-BY, CC0, public domain) may be acquired.
   - Raw documents must be hashed (SHA-256) and stored in read-only volumes.
   - Automated and manual redaction of natural names, corporate entities, commercial figures, and identifiers is mandatory prior to annotation.
   - Corpus sources and redaction logs require explicit project-owner authorization.

---

## 11. Required Prerequisites Before Real-Contract Annotation

Real-contract acquisition and legal annotation remain strictly blocked until the following eight engineering and governance prerequisites are verified:

1. `[PREREQUISITE]` **P1: Server-Side Blinding:** Implement presentation firewall endpoints in `src/review/routes.py` stripping confidence, model IDs, and policy recommendations.
2. `[PREREQUISITE]` **P2: Independent Storage & Locking:** Implement database tables and services in `src/persistence/` for independent annotator submissions with SHA-256 sealing.
3. `[PREREQUISITE]` **P3: Deduplication Key Patch:** Update `src/candidates/deduplication.py` to prevent false collisions when candidate finding text is null.
4. `[PREREQUISITE]` **P4: Corpus Acquisition & Redaction Sign-Off:** Source 15–20 public contracts, execute redaction, and obtain project-owner governance approval.
5. `[PREREQUISITE]` **P5: Candidate Benchmark Freezing:** Generate 150–200 candidates across all 7 archetypes, serialize to immutable JSONL, and record top-level SHA-256 hash.
6. `[PREREQUISITE]` **P6: Contract-Clustered Partitioner:** Implement clustered 40% validation / 60% test split logic in `src/evaluation/` with zero cross-split contract overlap.
7. `[PREREQUISITE]` **P7: Clustered Inferential Estimators:** Implement cluster bootstrap or GEE estimators in `src/evaluation/abstention_eval.py` to calculate cluster-adjusted standard errors.
8. `[PREREQUISITE]` **P8: Advocate Verification & Onboarding:** Verify Bar Council of India enrollment of annotators and complete onboarding calibration.

---

## 12. Statistical Integrity and Confirmatory Roadmap

1. `[DECISION]` **No Fabricated Power Claims:**  
   No statistical power calculation or required confirmatory sample size ($N_{\text{conf}}$) will be declared until the feasibility pilot provides empirical estimates of:
   - Baseline unsupported rate ($p_0$).
   - Intra-cluster correlation coefficient ($\rho$).
   - Average cluster size ($m$, findings per contract).
   - Observed human-review workload ($\text{HRW}$).

2. `[DECISION]` **Confirmatory Study Gateway:**  
   A full confirmatory study will be proposed if and only if the feasibility pilot satisfies:
   - Inter-annotator agreement $\kappa \ge 0.70$ on disposition.
   - Unassessable rate $\text{UR} \le 5.0\%$.
   - Observed $\Delta\text{UFR}_{@\text{MatchedUFC}} > 0$ on the held-out test split.
   - Human-review workload $\text{HRW} \le 35.0\%$.
   - $\text{SEAR}_{\text{stale}} = 0.0\%$ under Policy B.

---

## 13. Governance Confirmations

- **Document Location:** `docs/research_decision_record_v1.md`
- **Application Code Status:** Unmodified.
- **Database Status:** Unmodified.
- **Test Invariants:** Existing test suite (572 passing tests) remains untouched.
- **Task Locks:**
  - **Task 028:** Strictly `🔒 LOCKED`.
  - **Task 029:** Strictly `🔒 LOCKED`.
  - **Task 041 and Task 041A:** Historical records preserved without modification.
  - **Task 042:** Strictly `NOT STARTED`.
- **Task Board:** `PROJECT_TASK_BOARD.md` remains completely unmodified.

---

**END OF DECISION RECORD — AWAITING EXPLICIT PROJECT-OWNER AUTHORIZATION FOR SUBSEQUENT TASKS.**
