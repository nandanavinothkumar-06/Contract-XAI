# Formal Annotation Protocol and Guidelines: Evidence-Aware vs. Confidence-Only Abstention Evaluation

**Document Version:** 1.1.0  
**Status:** DRAFT SPECIFICATION (RESEARCH PLANNING ONLY — POST-AUDIT REVISED)  
**Target Repository:** `CONTRACTRISK-XAI`  
**Associated Machine-Readable Schema:** [`docs/schemas/candidate_finding_annotation.schema.json`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/docs/schemas/candidate_finding_annotation.schema.json)  
**Applicable Legal Framework:** Indian Commercial Contract Law (Central Acts: ICA 1872, IT Act 2000, DPDP Act 2023, SRA 1963, Arbitration Act 1996, BSA 2023)

---

## 1. Executive Overview and Objective

The primary research objective of this evaluation is to empirically determine:
> **Primary Research Question:**  
> Does an evidence-aware abstention policy that conditions decisions on model confidence, statutory evidence sufficiency, source authenticity/currentness, and document-version consistency reduce unsupported legal risk findings compared with a confidence-only baseline policy at comparable useful-finding coverage?

To answer this question without bias, circularity, or data leakage, candidate model findings must be evaluated against **independent, human-annotated ground-truth standards**.

This protocol defines:
1. The formal annotation guidelines, boundary criteria, and decision rubrics.
2. The independent annotation dimensions that decouple prediction accuracy from evidence sufficiency and source provenance.
3. The operational rules for handling curated and partially verified statutory extracts.
4. An explicit decision truth-table resolving edge cases between withholding and human review.
5. The blinding, multi-annotator, presentation firewall, and adjudication workflows.
6. The future evaluation protocol, metrics suite, edge-case math, and statistical power requirements.
7. An explicitly labeled, non-authoritative synthetic test instance for software verification.

---

## 2. Core Epistemic Principles and Firewall Rules

A recurring vulnerability in legal AI benchmarking is circularity: treating system heuristics as empirical proof of truth. This protocol mandates five strict epistemic firewalls. Annotators, adjudicators, and evaluation scripts must strictly respect these boundaries.

```
+---------------------------------------------------------------------------------------------------+
|                                  INDEPENDENT EPISTEMIC FIREWALLS                                  |
+===================================================================================================+
| 1. TRACEABLE != CORRECT                                                                           |
|    A passage link (even exact statutory text) does NOT prove that a model finding is legally or   |
|    commercially correct.                                                                          |
+---------------------------------------------------------------------------------------------------+
| 2. BM25 RANKING SCORE != EVIDENCE SUFFICIENCY                                                     |
|    Lexical keyword match scores reflect string token co-occurrence, NOT substantive legal         |
|    sufficiency, statutory relevance, or sound judicial reasoning.                                 |
+---------------------------------------------------------------------------------------------------+
| 3. LOCAL SHA-256 CHECKSUM != SOVEREIGN AUTHENTICITY                                               |
|    A cryptographic SHA-256 digest proves local file immutability. It does NOT prove official      |
|    sovereign gazette authority or certified Government of India publication.                      |
+---------------------------------------------------------------------------------------------------+
| 4. SOURCE AUTHENTICITY != LEGAL APPLICABILITY                                                     |
|    An authentic, in-force statute (e.g., ICA 1872 s. 28) may be completely inapplicable to a      |
|    specific contract clause due to party exclusions, non-arbitrability, or contractual override. |
+---------------------------------------------------------------------------------------------------+
| 5. POLICY DECISION != REFERENCE GROUND TRUTH                                                      |
|    The output of the abstention policy under test must NEVER serve as the evaluation label.       |
|    Annotators must remain strictly blinded to automated policy recommendations.                   |
+---------------------------------------------------------------------------------------------------+
```

---

## 3. Unit of Analysis and Candidate Metadata

To prevent aggregation errors and unit mismatches, every level of the analysis hierarchy is formally distinguished:

1. **Contract Document Cluster ($C$):** A group of contracts sharing identical boilerplate, counterparties, or template origin (`contract_cluster_id`). Enforces the strict cross-validation firewall.
2. **Contract Document ($D$):** An individual contract instrument with a specific file hash and metadata (`contract_id`).
3. **Contract Document Version ($V$):** A temporal snapshot of document $D$ (e.g., initial draft $v1$, revised draft $v2$; `contract_version`).
4. **Clause Segment ($S$):** An individual segmented provision or clause within $(D, V)$, bounded by character offsets (`clause_id`, `clause_text`).
5. **Candidate Model Finding ($F$):** A specific risk assertion, category, or label generated for clause segment $S$ by model $M$ (`candidate_finding_id`, `candidate_finding_text`, `prediction_category`). **This is the primary unit of analysis.**
6. **Statutory Passage ($P$):** A retrieved excerpt from an authoritative legal source (e.g., Section 28 of ICA 1872; `passage_id`, `passage_text`).
7. **Statutory Source ($A$):** The overarching Act or legislative snapshot (`statute_id`).

### Candidate Confidence Metric Types
In the `candidate_confidence` object, the numerical score is recorded alongside its exact origin:
- `SOFTMAX_PROBABILITY`: Normalized multiclass probability over all labels.
- `SIGMOID_PROBABILITY`: Independent binary probability per label.
- `MARGIN_SCORE`: Difference between top probability and second probability.
- `NORMALIZED_LOGIT`: Transformed raw logit output.

> [!IMPORTANT]
> Because clauses within the same contract share context, jurisdiction clauses, and drafting style, candidate findings within a contract document are **statistically clustered**. Evaluations must use cluster-adjusted standard errors or cluster bootstrap methods.

---

## 4. Annotation Dimensions and Rubrics

Every candidate finding $F$ is evaluated across independent dimensions. Annotators must never collapse these dimensions into a single blended score.

### Dimension A: Prediction Correctness (`prediction_assessment`)

Assesses whether the candidate finding accurately characterizes the legal or commercial risk present in the clause text, independent of whether evidence was retrieved.

| Label (`status`) | Definition | Boundary Criteria & Examples |
| :--- | :--- | :--- |
| `CORRECT` | The candidate finding accurately and substantively characterizes an operative legal or commercial risk present in the clause text. | A clause prohibits either party from approaching a court or tribunal in the event of dispute; model correctly flags an unlawful restraint of legal proceedings under Indian contract law. |
| `PARTIALLY_CORRECT` | The finding identifies a genuine risk theme or clause topic, but misstates the specific legal mechanism, severity, or operational scope. | Clause contains an employee non-compete covenant; model flags an unlawful restraint of trade under Section 27 ICA 1872, but overstates that the clause is per se criminal rather than void and unenforceable civilly. |
| `INCORRECT` | The candidate finding asserts a risk not present in the text, misidentifies the clause type, or generates a hallucinated/spurious risk. | The clause is an ordinary severability clause; the model flags a high-risk uncapped indemnity obligation. |
| `UNCLEAR` | The contractual language is genuinely ambiguous, internally contradictory, or missing critical exhibit context, preventing definitive assessment. | A cross-reference points to "Schedule 4 (Excluded Liabilities)" which is omitted from the contract text. |
| `NOT_ASSESSABLE` | The clause text is corrupt, unintelligible, severely truncated by the tokenizer, or non-English text. | Clause consists of broken character encoding fragments or OCR artifacts. |

#### Identified Risk Severity Enum (`identified_risk_severity`)
- `HIGH`: Severe legal exposure (e.g., void covenants under s. 27/28 ICA 1872, uncapped indemnities, severe statutory penal sanctions).
- `MEDIUM`: Moderate commercial risk (e.g., ambiguous cure periods, non-mutual termination rights, unilateral fee adjustments).
- `LOW`: Minor drafting ambiguity or administrative defect with low probability of litigation impact.
- `NEGLIGIBLE`: Standard boilerplate without material liability implications.
- `NOT_APPLICABLE`: Finding is incorrect, unclear, or not assessable.

---

### Dimension B: Evidence Support (`evidence_support` & `passages`)

Assesses whether the retrieved statutory passages substantively substantiate the premises of the candidate finding.

| Overall Status (`status`) | Definition | Boundary Criteria & Examples |
| :--- | :--- | :--- |
| `SUPPORTED` | The cited passages directly articulate the legal rule, statutory restriction, or standard that governs the candidate finding. | Finding claims an absolute restraint on legal proceedings is void; cited evidence is Section 28 of the Indian Contract Act 1872. |
| `PARTIALLY_SUPPORTED` | The cited passages relate to the same general topic or statutory chapter, but fail to substantiate the specific risk assertion made by the model. | Finding asserts that a liquidated damages clause is an unenforceable penalty; cited evidence is Section 73 (general damages) rather than Section 74 (liquidated damages and penalty). |
| `UNSUPPORTED` | The cited passages do not substantiate the finding, address an unrelated legal subject, or contradict the finding. | Finding claims a data privacy violation; cited evidence is Section 10 of Specific Relief Act 1963 (specific performance of contracts). |
| `INSUFFICIENT_INFORMATION`| The passage excerpt is truncated or incomplete such that substantive relevance cannot be established without consulting external text. | Passage contains only section heading without operative subsections. |
| `NOT_APPLICABLE` | The candidate finding asserts a purely commercial, contractual, or drafting risk that does not purport to invoke or rely upon an external statutory enactment. | Finding evaluates the commercial ambiguity of a 15-day versus 30-day notice period; external statutory evidence is not applicable. |
| `NOT_ASSESSABLE` | No evidence was linked, passage text is missing, or retrieval returned empty results when statutory evidence was expected. | Passage list is empty or corrupted. |

#### Passage Support Assessment Enum (`support_status`)
Each passage within `passages` is assigned an individual support status:
- `DIRECTLY_SUPPORTS`: Passage contains the explicit statutory rule or standard invoked by the finding.
- `ANALOGOUS_PRINCIPLE`: Passage articulates a general common law or statutory doctrine closely analogous to the finding.
- `TOPICALLY_RELATED_ONLY`: Passage touches the same broad domain (e.g., intellectual property or damages) but does not provide legal backing for the specific risk asserted.
- `IRRELEVANT`: Passage is completely unrelated to the contractual clause or risk asserted.
- `CONTRADICTS`: Passage directly refutes the model finding (e.g., explicit statutory exception permitting the exact practice flagged as unlawful).
- `NOT_APPLICABLE`: Passage evaluation is not applicable (e.g., non-statutory commercial risk).

---

### Dimension C: Evidence Sufficiency (`evidence_sufficiency`)

Assesses whether the available evidence base is complete enough to justify retaining the finding without requiring speculative inferences.

| Label (`status`) | Definition | Boundary Criteria & Examples |
| :--- | :--- | :--- |
| `SUFFICIENT` | The retrieved evidence provides all necessary legal definitions, operative tests, and statutory boundaries required to sustain the risk finding. | Cited provision contains the rule, statutory exceptions, and applicable legal threshold. |
| `INSUFFICIENT` | The evidence provides a partial clue but omits essential statutory exceptions, saving clauses, or required jurisdictional conditions. | Cited text mentions Section 43A of the IT Act 2000 but omits the SPDI Rules 2011 defining "reasonable security practices." |
| `CONFLICTING` | The evidence citations contain mutually contradictory statutory mandates or opposing legal principles that negate a simple conclusion. | One cited section states an obligation is mandatory, while another cited section grants an exemption for commercial entities of this class. |
| `MISSING` | Zero relevant statutory evidence exists in the citations or repository corpus when statutory backing is required. | No statutory provision addressing this contractual risk is present in the evidence panel. |
| `NOT_APPLICABLE` | The candidate finding asserts a purely commercial drafting risk where external statutory sufficiency is not an applicable concept. | Contractual clarity or commercial risk not governed by specific statute. |
| `NOT_ASSESSABLE` | The evidence base cannot be evaluated due to corrupted text or unresolvable ambiguities. | Corrupted evidence records. |

---

### Dimension D: Source Authenticity & Verification (`source_status`)

Audits the cryptographic and provenance pedigree of the reference legal artifact from which the passage was retrieved.

| Label (`status`) | Definition | Verification Criteria |
| :--- | :--- | :--- |
| `VERIFIED_RESEARCH_PROTOCOL` | Source snapshot matches verified official text with authenticated provenance and matching SHA-256 under project protocol. | Reference artifact PDF matches official gazette/India Code layout and recomputed SHA-256 matches manifest. |
| `PARTIALLY_VERIFIED` | Source snapshot is verified against official text, but contains noted editorial annotations, missing schedules, or curated extract boundaries. | All 6 current repository statutory snapshots (curated commercial extracts; e.g., IT Act 2000 has 4/6 concordant sections and 2 with editorial notes). |
| `UNVERIFIED` | Source lacks documented provenance, failed hash verification, or originated from an unauthenticated third-party source. | Modified snapshot bytes, unknown URL source, or unverified web scrape. |
| `HISTORICAL_CURRENTNESS_UNCERTAIN` | Reference snapshot is an archival historical version whose ongoing applicability has not been verified against subsequent amendments. | Pre-2018 Specific Relief Act snapshot without verification of 2018 amendment changes. |
| `NOT_APPLICABLE` | Finding is purely factual or contractual drafting analysis without statutory citation. | Finding evaluates clarity of clause wording without invoking statutory provisions. |
| `NOT_ASSESSABLE` | Source metadata is missing or corrupted. | Corrupted repository manifest entry. |

#### Provenance Classification Enum (`provenance_classification`)
- `OFFICIAL_SOVEREIGN_PKCS7_VERIFIED`: Source PDF bears a valid cryptographic digital signature from the Government of India or Controller of Certifying Authorities.
- `OFFICIAL_ORIGIN_SUPPORTED_BUT_NOT_INDEPENDENTLY_CONFIRMED`: Source PDF downloaded from official domain (e.g., `indiacode.nic.in`, `egazette.gov.in`) and visually verified, but lacks external PKCS#7 signature (current status of Task 041/041A artifacts).
- `CURATED_EDITORIAL_EXTRACT`: Researcher-curated text excerpt containing partial provisions or researcher editorial notes.
- `UNVERIFIED_THIRD_PARTY`: Scraped from commercial or unverified third-party websites without official gazette corroboration.
- `NOT_APPLICABLE`: Non-statutory findings.

---

### Dimension E: Source Currentness & Applicability (`source_applicability`)

Decoupled from authenticity. Assesses whether the statutory provision is currently in force and whether it legally applies to the contract.

#### E1: Currentness Sub-dimension (`currentness_status`)
- `IN_FORCE_CONFIRMED`: Provision is enacted, commenced by official notification, and verified as unamended/current.
- `COMMENCEMENT_PENDING`: Statute has received Presidential assent but operative sections are not yet notified (e.g., substantive penalty sections of DPDP Act 2023).
- `REPEALED_OR_SUPERSEDED`: Provision has been repealed by Parliament or superseded (e.g., ICA 1872 sections 76–123 replaced by Sale of Goods Act 1930).
- `JUDICIALLY_INVALIDATED`: Provision struck down or read down by Supreme Court of India or competent High Court (e.g., IT Act 2000 Section 66A struck down in *Shreya Singhal v. Union of India*).
- `CURRENTNESS_UNVERIFIED`: Legislative currentness has not been formally audited by an advocate.

#### E2: Applicability Sub-dimension (`applicability_status`)
- `APPLICABLE_TO_CONTRACT`: Advocate confirms the provision directly governs contracts of this subject matter and jurisdiction.
- `INAPPLICABLE_JURISDICTION_OR_SCOPE`: Provision does not apply (e.g., invoking consumer protection rules on a negotiated inter-enterprise commercial lease).
- `CONTRACTUAL_OVERRIDE_PERMITTED`: Statutory provision is a non-mandatory default rule which the parties have validly contracted out of under Indian law.
- `REQUIRES_ADVOCATE_DETERMINATION`: Complex conflict-of-laws or disputed interpretation requiring bespoke legal counsel.
- `NOT_APPLICABLE`: Non-statutory finding.

---

### Dimension F: Document-Version Consistency (`version_consistency`)

Audits whether the finding and its evidence pertain to the active version of the contract.

| Label (`status`) | Definition | Boundary Criteria |
| :--- | :--- | :--- |
| `CONSISTENT` | The candidate finding and its evidence were generated from the exact text of the currently active contract version. | Finding hash matches current document text hash; contract version is identical. |
| `STALE` | The finding or evidence was generated on a previous version (e.g., $v1$), and the clause has since been revised, deleted, or renumbered in $v2$. | Text hash mismatch; clause was amended during negotiation. |
| `UNKNOWN` | Version history or document lineage cannot be definitively traced from metadata. | Missing document version metadata. |
| `NOT_APPLICABLE` | Static single-document evaluation where revisions do not exist. | Single-pass evaluation benchmark. |

---

### Dimension G: Final Reference Decision (`final_reference_decision`)

The ground-truth benchmark decision for policy evaluation. **This represents what an ideal legal AI assistant should do with this candidate finding.**

| Label (`reference_action`) | Operational Standard | Required Conditions |
| :--- | :--- | :--- |
| `RETAIN` | The finding should be presented to the user / legal practitioner as an actionable risk finding. | Must satisfy ALL conditions in the Decision Table (Section 6). |
| `WITHHOLD` | The finding must be actively suppressed/withheld by the system to protect the user from false or misleading advice. | Triggered by any fatal disqualifier (incorrect prediction, stale version, repealed/invalidated law, or unsupported risk). |
| `HUMAN_REVIEW_REQUIRED` | The finding should not be directly disclosed without mandatory review and sign-off by an advocate. | Borderline cases: high-severity risk with partial/insufficient evidence, genuine ambiguity, or non-mandatory statutory override. |
| `NOT_ASSESSABLE` | The record is corrupted, unintelligible, or missing prerequisites. | Corrupted record. |

#### Confidence in Decision Enum (`confidence_in_decision`)
- `HIGH`: Unambiguous legal determination under well-settled Indian contract jurisprudence.
- `MODERATE`: Well-reasoned determination with minor interpretative nuances.
- `LOW`: Highly disputed or novel contractual scenario with split authority.

#### Root-Cause Failure Categories (`failure_category_if_withhold`)
When `reference_action` is `WITHHOLD`, the primary reason for withholding is classified:
- `INCORRECT_PREDICTION`: Model generated an inaccurate, hallucinated, or irrelevant finding.
- `UNSUPPORTED_FINDING`: Model generated a plausible finding, but the linked evidence fails to support it.
- `INSUFFICIENT_EVIDENCE`: Available statutory extract lacks operative clauses or necessary exceptions.
- `UNVERIFIED_SOURCE`: Cited statutory artifact failed cryptographic integrity or provenance verification.
- `INAPPLICABLE_OR_SUPERSEDED_STATUTE`: Cited provision is repealed, struck down, or legally inapplicable to this transaction.
- `STALE_DOCUMENT_VERSION`: Finding pertains to an outdated clause version superseded by a revision.
- `MULTIPLE_FAILURES`: Two or more independent failures are concurrently present.
- `NOT_APPLICABLE`: Used when `reference_action` is `RETAIN`, `HUMAN_REVIEW_REQUIRED`, or `NOT_ASSESSABLE`.

---

## 5. Treatment of Partially Verified Sources

A critical finding of Task 041A is that 100% of the active statutory reference sources in `data/legal_sources/corpus_manifest.json` have `verification_status: PARTIALLY_VERIFIED`. To avoid either improperly accepting unverified text or collapsing evaluation by rejecting all findings, the following six evidentiary dimensions must be distinguished:

```
+----------------------------------------------------------------------------------------------------+
|                         SIX EVIDENTIARY DIMENSIONS OF STATUTORY ARTIFACTS                         |
+====================================================================================================+
| 1. Local File Integrity:            Cryptographic SHA-256 matches manifest exactly.                |
| 2. Provision Concordance:           Target section exhibits 100% textual match against gazette.   |
| 3. Source Origin Authenticity:      Portal provenance supported; sovereign PKCS#7 unconfirmed.    |
| 4. Corpus Completeness:             Curated commercial extract (40 provisions), not full code.    |
| 5. Currentness & Commencement:      Legislative in-force status audited for post-enactment changes.|
| 6. Contractual Applicability:       Substantive legal relevance to this contract and jurisdiction. |
+----------------------------------------------------------------------------------------------------+
```

### Operational Rules for `PARTIALLY_VERIFIED` Sources
1. **Provision-Level Concordance Rule:** A statutory passage retrieved from a `PARTIALLY_VERIFIED` source **CAN** satisfy the source-verification condition for `RETAIN` *if and only if*:
   - The individual section cited has **100% textual concordance** against the verified reference extract (zero diff).
   - The section text contains no unverified researcher editorial notes or bracketed annotations.
   - The provision is confirmed to be commenced and currently in force in India.
2. **Text Difference / Editorial Annotation Rule:** If the specific cited section exhibits `TEXT_DIFFERENCE` (e.g., IT Act s. 43A or Specific Relief Act s. 10 notes) or unverified historical amendments:
   - The source status must be marked `PARTIALLY_VERIFIED`.
   - The finding **CANNOT** be directly labeled `RETAIN`.
   - It must be routed to `HUMAN_REVIEW_REQUIRED` (or `WITHHOLD` if substantively incorrect).
3. **Curated Extract Missing Provisions:** If a finding is legally sound but cites a provision absent from the repository's curated extract (e.g., Section 2 definitions or Section 85 IT Act):
   - `evidence_sufficiency` is marked `MISSING` or `INSUFFICIENT`.
   - If risk severity is `HIGH`, route to `HUMAN_REVIEW_REQUIRED`. If low/medium, route to `WITHHOLD` (failure category: `INSUFFICIENT_EVIDENCE`).
4. **Automated Evidence-Aware Policy Mapping:**
   - In `src/review/evidence.py`, passages with unverified commencement or unknown status trigger `SOURCE_UNVERIFIED`.
   - Passages missing section numbers or titles trigger `PARTIAL`.
   - Under `src/abstention/policy.py`, `PARTIAL` status routes the candidate finding to `REVIEW_REQUIRED`, while `SOURCE_UNVERIFIED` forces `ABSTAIN`.

---

## 6. Comprehensive Reference-Decision Rules and Precedence Protocol

### 6.1 Hierarchical Precedence Protocol and Conflict Resolution Cascade

When evaluating candidate findings, annotators and automated evaluation scripts must distinguish between two related concepts:
1. **Procedural Evaluation Order:** The operational sequence of checks applied to determine whether a finding can be assessed and which evidentiary dimensions apply.
2. **Label Conflict Resolution Order (Precedence):** The deterministic priority cascade that governs which reference label (`NOT_ASSESSABLE`, `WITHHOLD`, `HUMAN_REVIEW_REQUIRED`, or `RETAIN`) takes precedence when a finding matches multiple rule conditions due to wildcard fields.

To eliminate ambiguity across competing conditions, findings must be evaluated under the following strict **5-Tier Hierarchical Cascade**:

```
+----------------------------------------------------------------------------------------------------+
|                         5-TIER HIERARCHICAL PRECEDENCE CASCADE                                     |
+====================================================================================================+
| TIER 1: INPUT ASSESSABILITY (Terminating)                                                          |
|         Rule R14: If clause text or input finding is corrupt, unintelligible, or missing,           |
|         the outcome is NOT_ASSESSABLE. Terminates all substantive legal evaluation.                |
+----------------------------------------------------------------------------------------------------+
| TIER 2: FATAL FINDING DEFECTS (Mandatory Suppression)                                              |
|         If input is assessable, fatal safety disqualifiers supersede substantive ambiguity:        |
|         - Rule R04: STALE document version -> WITHHOLD (STALE_DOCUMENT_VERSION)                    |
|         - Rule R05: REPEALED / INVALIDATED statute -> WITHHOLD (INAPPLICABLE_OR_SUPERSEDED_STATUTE) |
|         - Rule R03: INCORRECT prediction assertion -> WITHHOLD (INCORRECT_PREDICTION)              |
|         (If multiple fatal defects coincide, root cause is logged as MULTIPLE_FAILURES).           |
+----------------------------------------------------------------------------------------------------+
| TIER 3: HIGH-SEVERITY SAFETY NET & LEGAL NUANCE (Mandatory Human Sign-off)                         |
|         If finding survives Tier 1 and Tier 2, genuine risks with incomplete evidence are routed   |
|         to an enrolled advocate rather than being dropped or retained unreviewed:                  |
|         - Rule R13: UNCLEAR contract text on active version -> HUMAN_REVIEW_REQUIRED               |
|         - Rule R07: CORRECT prediction with HIGH severity, but UNSUPPORTED -> HUMAN_REVIEW_REQUIRED |
|         - Rule R08: CORRECT prediction with HIGH severity, but INSUFFICIENT -> HUMAN_REVIEW_REQUIRED|
|         - Rule R10: Cited provision has TEXT_DIFFERENCE / notes -> HUMAN_REVIEW_REQUIRED           |
|         - Rule R11: CONTRACTUAL_OVERRIDE_PERMITTED on default rule -> HUMAN_REVIEW_REQUIRED        |
|         - Rule R12: PARTIALLY_CORRECT prediction with High/Med severity -> HUMAN_REVIEW_REQUIRED   |
+----------------------------------------------------------------------------------------------------+
| TIER 4: LOW/MEDIUM EVIDENTIARY DEFICIENCIES (Noise Suppression)                                    |
|         If finding is CORRECT but severity is LOW or MEDIUM and evidence fails:                    |
|         - Rule R06: UNSUPPORTED evidence -> WITHHOLD (UNSUPPORTED_FINDING)                         |
|         - Rule R09: INSUFFICIENT evidence -> WITHHOLD (INSUFFICIENT_EVIDENCE)                       |
+----------------------------------------------------------------------------------------------------+
| TIER 5: FULLY GROUNDED RETENTION (Actionable Presentation)                                         |
|         Survives all tiers with full factual, evidentiary, and temporal validity:                 |
|         - Rule R01: CORRECT + SUPPORTED + SUFFICIENT + Concordant Source + IN_FORCE -> RETAIN      |
|         - Rule R02: CORRECT + Non-statutory commercial drafting risk (NOT_APPLICABLE) -> RETAIN    |
+----------------------------------------------------------------------------------------------------+
```

> [!IMPORTANT]
> **Preservation of Epistemic Firewalls:**
> - `WITHHOLD` indicates that the candidate finding cannot be surfaced to a client by a reliable AI assistant. It does **NOT** prove that the underlying commercial risk is nonexistent in the transaction.
> - Missing statutory evidence is **NOT** treated as evidence that the contractual claim is legally false; rather, under Tier 3 (R07/R08), genuine high-severity risks with missing evidence are routed to `HUMAN_REVIEW_REQUIRED`.
> - High model confidence ($c(F) \ge 0.90$) exerts **ZERO** influence over reference labels.

### 6.2 Synthetic Conflict Resolution Examples

The following explicitly synthetic hypothetical examples illustrate deterministic conflict resolution under the 5-Tier Precedence Cascade:

#### Synthetic Conflict 1: Substantive Ambiguity vs. Stale Version
- **Scenario:** On an initial draft ($v1$), a clause contained ambiguous cure periods flagged by the model (`prediction_assessment: UNCLEAR`). However, revision history confirms the clause was completely rewritten in active draft $v2$ (`version_consistency: STALE`).
- **Competing Rules:** Rule R13 (`UNCLEAR` $\implies$ `HUMAN_REVIEW_REQUIRED`) vs. Rule R04 (`STALE` $\implies$ `WITHHOLD`).
- **Deterministic Outcome:** **`WITHHOLD`** (Failure Category: `STALE_DOCUMENT_VERSION`).
- **Rationale:** Tier 2 (Fatal Finding Defects) strictly takes precedence over Tier 3 (Legal Ambiguity). Presenting or reviewing findings based on superseded draft text creates severe operational confusion. The active document version must govern.

#### Synthetic Conflict 2: Hallucinated Claim with High Model Severity
- **Scenario:** The model flags an "Extreme Uncapped Liquidated Damages Liability" with high severity (`identified_risk_severity: HIGH`, confidence $0.92$) on an ordinary severability clause. The clause text contains zero damages provisions (`prediction_assessment: INCORRECT`), and cited statutory evidence is irrelevant (`evidence_support: UNSUPPORTED`).
- **Competing Rules:** Rule R03 (`INCORRECT` $\implies$ `WITHHOLD`) vs. Rule R07 (`HIGH` Severity Unsupported $\implies$ `HUMAN_REVIEW_REQUIRED`).
- **Deterministic Outcome:** **`WITHHOLD`** (Failure Category: `INCORRECT_PREDICTION`).
- **Rationale:** Tier 2 takes precedence over Tier 3. The human review safety net in Rule R07 protects *genuine* contractual risks (`CORRECT` predictions) from retrieval failures; it does NOT route hallucinated or factually false assertions to human review. False findings must be withheld.

#### Synthetic Conflict 3: High-Severity Genuine Risk with Incomplete Statutory Extract
- **Scenario:** The model correctly identifies an absolute uncapped indemnity obligation (`prediction_assessment: CORRECT`, `identified_risk_severity: HIGH`) on an active clause (`version_consistency: CONSISTENT`). The retrieval engine returns Section 124 of ICA 1872, but the repository extract omits essential judicial exceptions and limitation cross-references (`evidence_sufficiency: INSUFFICIENT`).
- **Competing Rules:** Rule R08 (`HIGH` Severity Insufficient $\implies$ `HUMAN_REVIEW_REQUIRED`) vs. Rule R09 (`INSUFFICIENT` $\implies$ `WITHHOLD`).
- **Deterministic Outcome:** **`HUMAN_REVIEW_REQUIRED`**.
- **Rationale:** Tier 3 takes precedence over Tier 4. Under Indian commercial practice, uncapped indemnities create existential commercial liability. Discarding a true, high-severity finding merely because the local statutory corpus contains a partial extract is an unacceptable legal risk. The finding must be flagged for advocate review.

#### Synthetic Conflict 4: Valid Statutory Baseline with Contractual Override
- **Scenario:** The model identifies a contractual notice timeline differing from statutory default provisions (`prediction_assessment: CORRECT`, `evidence_support: SUPPORTED`, `evidence_sufficiency: SUFFICIENT`). However, the statutory rule is a non-mandatory default which the parties have validly varied under freedom of contract (`source_applicability: CONTRACTUAL_OVERRIDE_PERMITTED`).
- **Competing Rules:** Rule R01 (Grounded Statutory Baseline $\implies$ `RETAIN`) vs. Rule R11 (`CONTRACTUAL_OVERRIDE` $\implies$ `HUMAN_REVIEW_REQUIRED`).
- **Deterministic Outcome:** **`HUMAN_REVIEW_REQUIRED`**.
- **Rationale:** Tier 3 takes precedence over Tier 5. Even when a statutory section is authentic and supported, an active contractual override requires advocate determination as to whether the variation violates Indian public policy (e.g., Section 23/28 ICA 1872). It cannot be retained as an unqualified violation without legal sign-off.

### 6.3 Rule-by-Rule Reference Decision Table

The following explicit decision table resolves all edge cases and boundary conflicts between `RETAIN`, `WITHHOLD`, `HUMAN_REVIEW_REQUIRED`, and `NOT_ASSESSABLE`, mapped to their respective precedence tiers:

| Rule # | Precedence Tier | Prediction Correctness | Evidence Support | Evidence Sufficiency | Source Status | Source Applicability | Version Status | Risk Severity | Final Reference Decision | Primary Rationale / Failure Category |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **R01** | Tier 5 | `CORRECT` | `SUPPORTED` | `SUFFICIENT` | `VERIFIED` / Concordant `PARTIAL` | `IN_FORCE` + `APPLICABLE` | `CONSISTENT` | Any | **`RETAIN`** | Ideal actionable finding; fully grounded. |
| **R02** | Tier 5 | `CORRECT` | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `NOT_APPLICABLE` | `CONSISTENT` | Any | **`RETAIN`** | Valid non-statutory commercial drafting finding. |
| **R03** | Tier 2 | `INCORRECT` | Any | Any | Any | Any | Any | Any | **`WITHHOLD`** | `INCORRECT_PREDICTION`. Fatal defect. |
| **R04** | Tier 2 | Any | Any | Any | Any | Any | `STALE` | Any | **`WITHHOLD`** | `STALE_DOCUMENT_VERSION`. Superseded text. |
| **R05** | Tier 2 | Any | Any | Any | Any | `REPEALED` / `INVALIDATED` | Any | Any | **`WITHHOLD`** | `INAPPLICABLE_OR_SUPERSEDED_STATUTE`. Bad law. |
| **R06** | Tier 4 | `CORRECT` | `UNSUPPORTED` | Any | Any | Any | `CONSISTENT` | `LOW`/`MED` | **`WITHHOLD`** | `UNSUPPORTED_FINDING`. Unsubstantiated. |
| **R07** | Tier 3 | `CORRECT` | `UNSUPPORTED` | Any | Any | Any | `CONSISTENT` | `HIGH` | **`HUMAN_REVIEW_REQUIRED`** | Real high risk, but model cited wrong statute. |
| **R08** | Tier 3 | `CORRECT` | `SUPPORTED` | `INSUFFICIENT` | Any | Any | `CONSISTENT` | `HIGH` | **`HUMAN_REVIEW_REQUIRED`** | Real high risk with incomplete evidence. |
| **R09** | Tier 4 | `CORRECT` | `SUPPORTED` | `INSUFFICIENT` | Any | Any | `CONSISTENT` | `LOW`/`MED` | **`WITHHOLD`** | `INSUFFICIENT_EVIDENCE`. Inadequate baseline. |
| **R10** | Tier 3 | `CORRECT` | Any | Any | Differs on Cited Section | `IN_FORCE` + `APPLICABLE` | `CONSISTENT` | Any | **`HUMAN_REVIEW_REQUIRED`** | Cited provision contains text discrepancies. |
| **R11** | Tier 3 | `CORRECT` | `SUPPORTED` | `SUFFICIENT` | Concordant | `CONTRACTUAL_OVERRIDE` | `CONSISTENT` | Any | **`HUMAN_REVIEW_REQUIRED`** | Default rule overridden by contract terms. |
| **R12** | Tier 3 | `PARTIALLY_CORRECT` | `SUPPORTED`/`PARTIAL` | `SUFFICIENT`/`PARTIAL` | Concordant | `IN_FORCE` + `APPLICABLE` | `CONSISTENT` | `HIGH`/`MED` | **`HUMAN_REVIEW_REQUIRED`** | Flawed mechanism; requires advocate adjustment.|
| **R13** | Tier 3 | `UNCLEAR` | Any | Any | Any | Any | `CONSISTENT` | Any | **`HUMAN_REVIEW_REQUIRED`** | Genuine contractual or statutory ambiguity. |
| **R14** | Tier 1 | `NOT_ASSESSABLE`| Any | Any | Any | Any | Any | Any | **`NOT_ASSESSABLE`** | Corrupt text, broken encoding, or invalid input.|

---

## 7. Annotator Qualifications, Blinding, and Presentation Firewall

### 7.1 Annotator Qualifications
- `ENROLLED_ADVOCATE_INDIA`: Practicing advocate enrolled with a State Bar Council under the Advocates Act 1961 with minimum 2 years of active commercial contracting experience.
- `SENIOR_LEGAL_COUNSEL`: Advocate or corporate legal counsel with minimum 7 years of commercial dispute or transactional experience (eligible for adjudicator role).
- `LEGAL_RESEARCHER`: LL.M. graduate or dedicated legal research scholar with demonstrated publication record in Indian commercial or statutory law.
- `TRAINED_STUDENT_ANNOTATOR`: Final-year LL.B. student who has completed comprehensive training and passed benchmark qualification testing (pilot calibration only).

### 7.2 Annotation Phases
Records track the research phase under `annotation_phase`:
- `PILOT_CALIBRATION`: Initial 20–50 finding pilot to refine guidelines and calibrate annotator understanding.
- `MAIN_STUDY`: Primary evaluation annotation phase.
- `HELD_OUT_BENCHMARK`: Annotation of the frozen, held-out test split.
- `ADJUDICATION_DISAGREEMENT`: Secondary adjudication phase triggered by annotator divergence.

### 7.3 Disagreement and Formal Adjudication
Disagreements on `final_reference_decision`, `prediction_assessment.status`, or `evidence_sufficiency.status` are automatically flagged (`disagreement_flag = true`) and routed to a Senior Adjudicator who records an `adjudication_record` with an explicit `outcome`:
- `CONFIRMED_PRIMARY_1`: Upheld Annotator 1's decision with documented rationale.
- `CONFIRMED_PRIMARY_2`: Upheld Annotator 2's decision with documented rationale.
- `CONSENSUS_COMPROMISE`: Reached a synthesized decision balancing both perspectives.
- `EXCLUDED_GENUINE_AMBIGUITY`: Excluded the finding from benchmark scoring due to genuine, unresolvable statutory or judicial ambiguity.

### 7.4 Field-Visibility Matrix per Annotation Stage

To prevent cognitive anchoring, confirmation bias, and circular policy leakage, the annotation interface must enforce the following field-visibility matrix:

| Annotation Stage | Visible Fields to Annotator | Strictly Hidden Fields |
| :--- | :--- | :--- |
| **1. Prediction Correctness** | `clause_text`, `candidate_finding_text`, `prediction_category` | `model_identifier`, `candidate_confidence`, policy decisions, retrieved passages |
| **2. Evidence Support** | `clause_text`, `candidate_finding_text`, cited passage text, section title | BM25 ranking scores, `evidence_quality_status`, model confidence, policy decisions |
| **3. Evidence Sufficiency** | `clause_text`, `candidate_finding_text`, totality of retrieved passages | BM25 ranking scores, `evidence_quality_status`, model confidence, policy decisions |
| **4. Source Status** | Statute title, section number, official portal URL, local snapshot SHA-256 | Model prediction text, candidate finding, confidence score, policy decisions |
| **5. Version Consistency** | Active clause text, finding clause text, version numbers, text SHA-256 | Model confidence scores, policy recommendations |
| **6. Final Reference Decision** | Annotator's own ratings (Dims A–F), clause text, finding text, statutory extract | Baseline policy decision ($\pi_{\text{conf}}$), evidence-aware policy decision ($\pi_{\text{evid}}$), model confidence |
| **7. Peer Independent Labeling**| Independent annotation form | Peer annotator's ratings and rationales (blinded until both submit) |
| **8. Disagreement Adjudication** | Annotator 1 ratings & rationale, Annotator 2 ratings & rationale, clause text, finding text | Baseline and evidence-aware policy recommendations |

### 7.5 Presentation Firewall Architecture
Although [`candidate_finding_annotation.schema.json`](file:///C:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/docs/schemas/candidate_finding_annotation.schema.json) bundles `candidate_confidence` and `model_identifier` for master evaluation tracking, **the annotation interface must NEVER render the complete raw JSON record to the user.** The backend service must project a filtered "Annotator View" that strips confidence scores and model metadata before sending payloads to the browser.

---

## 8. Future Evaluation Protocol and Metrics Suite

### 8.1 Primary and Secondary Metrics Suite

| Metric | Mathematical Formula | Valid Denominator | Primary / Secondary | Edge-Case Definition & Interpretation |
| :--- | :--- | :--- | :--- | :--- |
| **Unsupported-Finding Rate (UFR)** | $\frac{\sum_{F \in \text{Retained}_{\text{eval}}} \mathbb{I}(y_{\text{ref}}(F) = \text{WITHHOLD})}{\|\text{Retained}_{\text{eval}}\|}$ | $\|\text{Retained}_{\text{eval}}\| = \sum_{F \in \text{Retained}} \mathbb{I}(y_{\text{ref}} \neq \text{NOT\_ASSESSABLE})$ | **PRIMARY** | If $\|\text{Retained}_{\text{eval}}\| = 0$, $\text{UFR} = \text{UNDEFINED}$ (reported alongside $\text{RR} = 0.0$). Never silently report 0.0%. Excludes unassessable findings. |
| **Useful-Finding Coverage (UFC)** | $\frac{\sum_{F \in \text{Retained}_{\text{eval}}} \mathbb{I}(y_{\text{ref}}(F) = \text{RETAIN})}{\sum_{F \in \mathcal{F}_{\text{eval}}} \mathbb{I}(y_{\text{ref}}(F) = \text{RETAIN})}$ | Total True Retainable Findings in Corpus | **PRIMARY** | Recall of genuinely valid, supported risk findings. Denominator is total true retainable findings. |
| **Matched-Coverage UFR Diff ($\Delta\text{UFR}_{@\text{MatchedUFC}}$)** | $\text{UFR}(\pi_{\text{conf}})_{@\text{UFC}=k} - \text{UFR}(\pi_{\text{evid}})_{@\text{UFC}=k}$ | Matched Coverage Point within $\pm \epsilon$ | **PRIMARY** | Direct test of whether evidence-awareness lowers error rate at identical utility. Higher is better. |
| **Retention Rate (RR)** | $\frac{\|\text{Retained}\|}{\|\mathcal{F}\|}$ | All Candidate Predictions | Secondary | Overall proportion of candidates retained. |
| **Abstention Precision (AP)** | $\frac{\sum_{F \in \text{Abstained}_{\text{eval}}} \mathbb{I}(y_{\text{ref}}(F) \neq \text{RETAIN})}{\|\text{Abstained}_{\text{eval}}\|}$ | Total Evaluable Abstained Findings | Secondary | Accuracy of withholding decisions. |
| **Abstention Recall (AR)** | $\frac{\sum_{F \in \text{Abstained}_{\text{eval}}} \mathbb{I}(y_{\text{ref}}(F) = \text{WITHHOLD})}{\sum_{F \in \mathcal{F}_{\text{eval}}} \mathbb{I}(y_{\text{ref}}(F) = \text{WITHHOLD})}$ | Total Findings Warranting Withholding | Secondary | Completeness of withholding harmful findings. |
| **Unnecessary Abstention Rate (UAR)** | $\frac{\sum_{F \in \text{Abstained}_{\text{eval}}} \mathbb{I}(y_{\text{ref}}(F) = \text{RETAIN})}{\|\mathcal{F}_{\text{eval}}\|}$ | Total Evaluable Candidate Predictions | Secondary | Absolute false-negative abstention rate across all candidates. Note: Relative false-negative rate is $1 - \text{UFC}$. |
| **Stale-Evidence Acceptance (SEAR)** | $\frac{\sum_{F \in \text{Retained}} \mathbb{I}(\text{Version}(F) = \text{STALE})}{\|\text{Retained}\|}$ | Total Retained Findings | Secondary | Safety violation: surfacing findings on outdated contract text. |
| **Unverified-Source Acceptance (USAR)**| $\frac{\sum_{F \in \text{Retained}} \mathbb{I}(\text{Source}(F) = \text{UNVERIFIED})}{\|\text{Retained}\|}$ | Total Retained Findings | Secondary | Safety violation: surfacing findings from unauthenticated law. |
| **Human-Review Workload (HRW)** | $\frac{\|\text{Review\_Required}\|}{\|\mathcal{F}\|}$ | All Candidate Predictions | Secondary | Operational burden placed on supervising advocates. |
| **Unassessable Rate (UR)** | $\frac{\sum_{F \in \mathcal{F}} \mathbb{I}(y_{\text{ref}}(F) = \text{NOT\_ASSESSABLE})}{\|\mathcal{F}\|}$ | All Candidate Predictions | Data Quality | Data quality metric tracking unusable or corrupted records. |

### 8.2 Operational Specification for Matched-Coverage Comparison ($\Delta\text{UFR}_{@\text{MatchedUFC}}$)

Because $\pi_{\text{evid}}$ incorporates discrete categorical gates (`TRACEABLE`, `PARTIAL`, `INSUFFICIENT`, etc.), its coverage does not vary continuously across the unit interval. To ensure scientific reproducibility, the following evaluation protocol must be strictly enforced:

#### 8.2.1 Unit of Analysis Across Metrics
1. **Primary Unit of Analysis:** The **Candidate Model Finding ($F$)**. All primary and secondary metrics ($\text{UFR}$, $\text{UFC}$, $\text{RR}$, $\text{UAR}$, $\text{AP}$, $\text{AR}$, $\text{HRW}$, $\text{UR}$) evaluate sets of individual candidate findings ($F \in \mathcal{F}_{\text{eval}}$).
2. **Clustering Unit:** The **Contract Document Cluster ($C$)** or **Contract Document ($D$)**. Because findings within a single contract share drafting context and jurisdiction, all statistical hypothesis tests (GEE and paired cluster bootstrap) must resample at the contract cluster level.

#### 8.2.2 Duplicate-Finding Policy and Deduplication Protocol
A distinction must be maintained between **exact duplicate records** and **distinct findings on the same clause segment**:
- **Distinct Risk Assertions Preserved:** If a model generates multiple distinct risk categories for the same clause segment (e.g., both an `INDEMNIFICATION` finding and a `LIMITATION_OF_LIABILITY` finding on Clause 14.2), both records represent distinct candidate findings ($F_1, F_2$) and must be retained and evaluated independently. Deduplication must never collapse distinct risk categories.
- **Exact Duplicate Finding Records:** An exact duplicate occurs when an inference pipeline produces redundant prediction records sharing identical text and category for the same clause segment.
- **Deduplication Key:** Deduplication must be executed strictly during the **Data Ingestion Preprocessing Stage** prior to blinding, annotation, or policy thresholding:
  $$\text{DeduplicationKey}(F) = (\text{contract\_id}, \text{contract\_version}, \text{clause\_id}, \text{prediction\_category}, \text{normalize}(\text{candidate\_finding\_text}))$$
  Where $\text{normalize}(\cdot)$ trims whitespace, case-folds ASCII text, and standardizes punctuation.
- **Audit Logging:** Removed duplicates are assigned a canonical finding ID, and their occurrences are recorded in an immutable audit table (`duplicate_finding_log`) recording `canonical_finding_id`, `duplicate_finding_id`, `model_instance`, and `ingestion_timestamp`. Deduplication must NEVER depend on ground-truth correctness labels or policy outcomes.
- **Prerequisite Note:** If an evaluation corpus lacks stable candidate finding IDs, deterministic SHA-256 digests of the `DeduplicationKey` must be generated at ingestion as an engineering prerequisite before evaluation.

#### 8.2.3 Deterministic Confidence-Score Tie-Breaking Protocol
When evaluating confidence-only baseline policies ($\pi_{\text{conf}}$) across continuous sweeps:
1. **Threshold Boundary Evaluation:** In the operational policy decision $\pi_{\text{conf}}(F) = \mathbb{I}(c(F) \ge \tau_{\text{conf}})$, tied candidates at the threshold boundary are evaluated symmetrically as a group. All candidates with $c(F) \ge \tau_{\text{conf}}$ are retained; all candidates below are abstained.
2. **Ranking and Quantile Sort Protocol:** When candidate predictions must be ordered linearly (e.g., to trace precision-coverage curves or locate empirical quantiles), ties in numerical confidence scores must be resolved using a strictly non-outcome-based, deterministic sort key:
   $$\text{SortKey}(F) = (-c(F), \text{candidate\_finding\_id})$$
   (Primary sort: numerical confidence score descending; Secondary tie-breaker: candidate finding identifier lexicographically ascending).
3. **Firewall on Tie-Breaking:** The tie-breaker must **NEVER** inspect reference labels ($y_{\text{ref}}$), prediction correctness, evidence quality status, or policy outcomes. The sort order is 100% deterministic, immutable, and fixed prior to label evaluation.

#### 8.2.4 Protocol for Matched-Coverage Sweeps
1. **Identical Candidate Sets:** Both policies are evaluated on the exact same candidate prediction set $\mathcal{F}_{\text{test}}$.
2. **Validation Split Only:** Confidence operating threshold $\tau_{\text{conf}}^*$ is selected strictly on the 40% validation split ($\mathcal{F}_{\text{val}}$). Test set labels are never observed during threshold calibration.
3. **Prespecified Tolerance Band ($\epsilon = \pm 0.02$):** For a target coverage $k$ achieved by $\pi_{\text{evid}}(\tau^*)$ on $\mathcal{F}_{\text{val}}$, the baseline threshold $\tau_{\text{conf}}$ is swept on the validation set to locate the nearest point $k_{\text{conf}}$ such that $|k_{\text{conf}} - k| \le 0.02$.
4. **Failure to Match Disclosure:** If no threshold on the validation curve falls within $\pm 0.02$ of $k$, the evaluator must report `MATCHED_COVERAGE_UNACHIEVED` and plot the complete Precision-Coverage Pareto frontier rather than claiming an exact matched comparison.
5. **Reporting Requirement:** Evaluators must report achieved coverage for both policies ($k_{\text{conf}}$ and $k_{\text{evid}}$) alongside the difference $\Delta\text{UFR}$.
6. **Scientific Integrity Disclaimer:** The tolerance band $\epsilon = \pm 0.02$ is a prespecified operational protocol parameter, NOT an empirically validated constant.

---

## 9. Illustrative Synthetic Annotation Examples (Non-Authoritative Pedagogy)

> [!CAUTION]
> THE FOLLOWING RECORDS ARE EXPLICITLY SYNTHETIC PEDAGOGICAL EXAMPLES FOR SOFTWARE TESTING AND SCHEMA DEMONSTRATION ONLY. THEY DO NOT CONSTITUTE LEGAL ADVICE, AN AUTHENTIC ADVOCATE ANNOTATION, OR AN OFFICIAL STATUTORY DETERMINATION.

### Example 1: Statutory Restraint of Legal Proceedings (Section 28 ICA 1872)

```json
{
  "schema_version": "1.0.0",
  "annotation_id": "00000000-0000-4000-8000-000000000001",
  "is_synthetic_fixture": true,
  "identification": {
    "contract_id": "HYPO-CONTRACT-2026-001",
    "contract_cluster_id": "CLUSTER-HYPO-TECH-01",
    "contract_version": 1,
    "clause_id": "SEC-18.4",
    "clause_text": "Neither party shall under any circumstances commence, prosecute, or maintain any suit, action, or proceeding in any court of law or tribunal against the other party arising out of or relating to this Agreement.",
    "candidate_finding_id": "HYPO-FIND-001",
    "candidate_finding_text": "Risk: Clause imposes an absolute bar on legal proceedings, which is void under Section 28 of the Indian Contract Act 1872.",
    "prediction_category": "DISPUTE_RESOLUTION_RESTRAINT",
    "model_identifier": "hypothetical-model-bert-legal",
    "model_version": "1.0.0-demo",
    "candidate_confidence": {
      "score": 0.895,
      "metric_type": "SIGMOID_PROBABILITY",
      "is_calibrated": false
    }
  },
  "prediction_assessment": {
    "status": "CORRECT",
    "rationale": "The clause explicitly extinguishes both parties' rights to enforce contract rights in ordinary tribunals. Under Indian law, an absolute restraint on legal proceedings is void.",
    "identified_risk_severity": "HIGH"
  },
  "evidence_support": {
    "status": "SUPPORTED",
    "rationale": "Section 28 of the Indian Contract Act 1872 directly provides that every agreement by which any party thereto is restricted absolutely from enforcing his rights under or in respect of any contract is void to that extent.",
    "passages": [
      {
        "passage_id": "HYPO-ICA-SEC-28",
        "statute_id": "IN_ACT_1872_09",
        "section_number": "Section 28",
        "passage_text": "Every agreement, by which any party thereto is restricted absolutely from enforcing his rights under or in respect of any contract, by the usual legal proceedings in the ordinary tribunals... is void to that extent.",
        "support_status": "DIRECTLY_SUPPORTS",
        "key_phrases": [
          "restricted absolutely from enforcing his rights",
          "void to that extent"
        ]
      }
    ]
  },
  "evidence_sufficiency": {
    "status": "SUFFICIENT",
    "rationale": "Section 28 provides the complete statutory operative rule and standard. The exceptions (arbitration agreements) do not apply because the clause does not provide for arbitration.",
    "missing_elements": []
  },
  "source_status": {
    "status": "PARTIALLY_VERIFIED",
    "source_repository": "India Code / Ministry of Law and Justice",
    "provenance_classification": "OFFICIAL_ORIGIN_SUPPORTED_BUT_NOT_INDEPENDENTLY_CONFIRMED",
    "source_sha256": "90d97034c568ec532ae30c9e685f00a5a3a4c49d68c92a95267ff61ffbead90a",
    "notes": "Curated extract snapshot; Section 28 exhibits 100% concordance against official publication."
  },
  "source_applicability": {
    "currentness_status": "IN_FORCE_CONFIRMED",
    "applicability_status": "APPLICABLE_TO_CONTRACT",
    "rationale": "Section 28 ICA 1872 is in force and directly governs commercial agreements subject to Indian law."
  },
  "version_consistency": {
    "status": "CONSISTENT",
    "finding_contract_version": 1,
    "active_contract_version": 1,
    "text_hash_matches": true
  },
  "final_reference_decision": {
    "reference_action": "RETAIN",
    "decision_rationale": "The finding correctly identifies an absolute statutory restraint on legal proceedings under Section 28 ICA 1872, is fully supported by sufficient, concordant statutory text, and pertains to the active contract version.",
    "confidence_in_decision": "HIGH",
    "failure_category_if_withhold": "NOT_APPLICABLE"
  },
  "epistemic_firewall_attestation": {
    "rule_traceable_not_treated_as_correct": true,
    "rule_bm25_not_treated_as_ground_truth_sufficiency": true,
    "rule_checksum_not_treated_as_official_authenticity": true,
    "rule_authenticity_not_treated_as_applicability": true,
    "rule_policy_output_not_treated_as_reference_decision": true
  },
  "annotation_provenance": {
    "annotator_code": "ANN-999",
    "annotator_qualification": "ENROLLED_ADVOCATE_INDIA",
    "annotation_phase": "PILOT_CALIBRATION",
    "blinding_conditions": {
      "blinded_to_model_identity": true,
      "blinded_to_confidence_score": true,
      "blinded_to_policy_decisions": true
    },
    "disagreement_flag": false,
    "created_at": "2026-10-17T17:30:00Z"
  }
}
```

### Example 2: Non-Statutory Commercial Drafting Finding (`NOT_APPLICABLE`)

```json
{
  "schema_version": "1.0.0",
  "annotation_id": "00000000-0000-4000-8000-000000000002",
  "is_synthetic_fixture": true,
  "identification": {
    "contract_id": "HYPO-CONTRACT-2026-002",
    "contract_cluster_id": "CLUSTER-HYPO-TECH-01",
    "contract_version": 1,
    "clause_id": "SEC-08.1",
    "clause_text": "Supplier may adjust fees upon notice to Customer without specified advance time or objective benchmark.",
    "candidate_finding_id": "HYPO-FIND-002",
    "candidate_finding_text": "Commercial Drafting Risk: Unilateral price adjustment mechanism lacking notice timeline or cost index ceiling.",
    "prediction_category": "COMMERCIAL_PRICE_ADJUSTMENT",
    "model_identifier": "hypothetical-model-bert-legal",
    "model_version": "1.0.0-demo",
    "candidate_confidence": {
      "score": 0.760,
      "metric_type": "SIGMOID_PROBABILITY",
      "is_calibrated": false
    }
  },
  "prediction_assessment": {
    "status": "CORRECT",
    "rationale": "Clause permits unilateral price escalation without advance notice or commercial index caps. Accurately highlights commercial risk.",
    "identified_risk_severity": "MEDIUM"
  },
  "evidence_support": {
    "status": "NOT_APPLICABLE",
    "rationale": "Finding is a commercial contract drafting risk that does not assert statutory illegality. External statutory retrieval is not applicable.",
    "passages": []
  },
  "evidence_sufficiency": {
    "status": "NOT_APPLICABLE",
    "rationale": "Statutory evidence sufficiency is not applicable to non-statutory commercial drafting terms.",
    "missing_elements": []
  },
  "source_status": {
    "status": "NOT_APPLICABLE",
    "source_repository": "N/A",
    "provenance_classification": "NOT_APPLICABLE",
    "notes": "Non-statutory finding."
  },
  "source_applicability": {
    "currentness_status": "CURRENTNESS_UNVERIFIED",
    "applicability_status": "NOT_APPLICABLE",
    "rationale": "Non-statutory finding."
  },
  "version_consistency": {
    "status": "CONSISTENT",
    "finding_contract_version": 1,
    "active_contract_version": 1,
    "text_hash_matches": true
  },
  "final_reference_decision": {
    "reference_action": "RETAIN",
    "decision_rationale": "Accurate, actionable commercial drafting risk evaluated on consistent contract text; external statutory evidence is not applicable.",
    "confidence_in_decision": "HIGH",
    "failure_category_if_withhold": "NOT_APPLICABLE"
  },
  "epistemic_firewall_attestation": {
    "rule_traceable_not_treated_as_correct": true,
    "rule_bm25_not_treated_as_ground_truth_sufficiency": true,
    "rule_checksum_not_treated_as_official_authenticity": true,
    "rule_authenticity_not_treated_as_applicability": true,
    "rule_policy_output_not_treated_as_reference_decision": true
  },
  "annotation_provenance": {
    "annotator_code": "ANN-999",
    "annotator_qualification": "ENROLLED_ADVOCATE_INDIA",
    "annotation_phase": "PILOT_CALIBRATION",
    "blinding_conditions": {
      "blinded_to_model_identity": true,
      "blinded_to_confidence_score": true,
      "blinded_to_policy_decisions": true
    },
    "disagreement_flag": false,
    "created_at": "2026-10-17T17:30:00Z"
  }
}
```

---

## 10. Threats to Validity and Scientific Limitations

1. **Curated Extract Statutory Denominator:** The current statutory corpus consists of 40 provisions across 6 central Acts, rather than comprehensive Indian legal codes. If a commercial finding cites an omitted Act (e.g., Companies Act 2013, Sale of Goods Act 1930), retrieval will return `NO_MATCHING_EVIDENCE`.
2. **Subjective Boundary in "Partially Correct":** Commercial contract risk assessments often involve nuances where reasonable advocates differ (e.g., distinguishing an employee non-compete void under Section 27 ICA 1872 from an enforceable non-solicitation restriction). A pilot study is required to establish whether human inter-annotator agreement reaches $\kappa \ge 0.70$.
3. **Discrete Policy Coverage Matching:** Because the evidence-aware policy relies on discrete categorical statuses, coverage sweeps do not form a smooth curve. The prespecified tolerance band $\epsilon = \pm 0.02$ must be strictly evaluated during validation tuning.

---

## 11. Document Provenance and Invariants

- **Tasks 028 and 029:** Remain strictly `🔒 LOCKED`.
- **Task 042:** Remains strictly **NOT STARTED**.
- **Repository Impact:** Pure documentation and schema specification. Zero application code, model weights, database schemas, or test suites modified.
