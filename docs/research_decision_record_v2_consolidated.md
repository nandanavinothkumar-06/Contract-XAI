# RESEARCH DECISION RECORD (RDR-002)
## Strategy A: Indian Public-Sector Model Commercial Agreement Pilot Corpus (IPS-MCAP) Specification & Ingestion Governance

**Document Identifier:** `RDR-002-STRATEGY-A-PILOT-CORPUS-CONSOLIDATED-V1`  
**Version:** 1.0.0 (Consolidated)  
**Date:** 2026-10-18  
**Status:** APPROVED METHODOLOGICAL RESEARCH DESIGN SPECIFICATION  
**Scope:** CONTRACTRISK-XAI Methodological Protocol & Pilot Corpus Architecture  
**Parent Document:** [`docs/research_decision_record_v1.md`](file:///c:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/docs/research_decision_record_v1.md)  

---

> [!WARNING]
> **RESEARCH METHODOLOGICAL DECISION RECORD ONLY — NOT EXPERIMENTAL RESULTS OR LEGAL CLEARANCE**  
> This document formalizes binding research invariants, corpus clustering rules, extraction boundaries, and governance controls approved for the `CONTRACTRISK-XAI` project. It does **not** constitute experimental validation, empirical superiority, statutory completeness, legal clearance, or authorization to acquire or ingest documents. Tasks 028 and 029 remain strictly `🔒 LOCKED`. Task 042 remains strictly `NOT STARTED`.

---

## 1. Context, Strategy A Invariants & Primary Estimand

1. `[DECISION]` **Preservation of Strategy A:**  
   The project proceeds with Strategy A: evaluating the triage reliability of an evidence-aware abstention policy against a confidence-only thresholding baseline on a common, frozen candidate benchmark derived from authentic Indian commercial contract clauses. Strategy B (large-scale bespoke model pre-training) remains formally deferred.

2. `[DECISION]` **Primary Estimand & Matched Coverage Invariant:**  
   The primary contrast estimand is the Matched-Coverage Unsupported-Finding Rate Difference:
   $$\Delta\text{UFR}_{@\text{MatchedUFC}} = \text{UFR}(\pi_{\text{conf}}) - \text{UFR}(\pi_{\text{evid}})$$
   * Coverage tolerance is prespecified at $\epsilon = \pm 0.02$ on Useful-Finding Coverage ($\text{UFC}$).
   * Continuous interpolation across discontinuous coverage thresholds is strictly prohibited. If $|\Delta\text{UFC}| > 0.02$, $\Delta\text{UFR}$ is suppressed, and `MATCHED_COVERAGE_UNACHIEVED` must be reported.

3. `[DECISION]` **Operational Meaning of WITHHOLD:**  
   The decision `WITHHOLD` indicates that a candidate risk finding is unsuitable for automated disclosure or client presentation due to evidence insufficiency, statutory invalidity, or document-version mismatch. It does **not** signify that the underlying legal risk is intrinsically false.

4. `[DECISION]` **Engineering Nature of Synthetic Results:**  
   All synthetic candidate generator results and rule-based fixtures remain strictly for pipeline verification and regression testing. They do not constitute empirical evidence of model performance on Indian commercial contracts.

---

## 2. Template Macro-Family Grouping & Partition Isolation

1. `[DECISION]` **Conservative Initial Consolidation:**  
   All model commercial contract components extracted from the Department of Expenditure (DoE), Ministry of Finance procurement manuals—specifically:
   * *Manual for Procurement of Goods* (e.g., June 2022 edition)
   * *Manual for Procurement of Non-Consultancy Services* (2025 edition)
   * *Manual for Procurement of Consultancy & Other Services* (2025 edition)
   
   must be consolidated into a single macro-family: **`MACRO-FAM-DOE-PPD`**.

2. `[DECISION]` **Multi-Factor Independence Requirement:**  
   Lexical similarity metrics (such as $\text{Jaccard}_{5\text{-gram}} < 0.15$) represent a necessary negative screening check but **do not, by themselves, establish family independence**. Finer sub-family partitioning within an issuing authority is strictly prohibited unless supported by:
   * **Administrative Provenance Review:** Establishing independent drafting authorities and non-overlapping model tender lineages.
   * **Structural & Lexical Overlap Analysis:** Evaluating both cross-clause n-gram similarity and structural clause-taxonomy alignment.
   * **Documented Technical Justification:** A formal audit note demonstrating that shared standard boilerplate (e.g., Force Majeure, Arbitration, Governing Law, Termination) will not induce circular policy or model leakage.

3. `[DECISION]` **Strict Cross-Partition Isolation Invariant:**  
   Any template families deemed related through shared administrative origin, statutory parentage, or common boilerplate **must never cross evaluation partitions**. All documents belonging to `MACRO-FAM-DOE-PPD` must reside 100% within a single evaluation split.

---

## 3. Feasibility Pilot Boundary & Partition Allocation

1. `[DECISION]` **Feasibility Boundary:**  
   The proposed 15–20-document pilot corpus (comprising DoE manuals, NITI Aayog model concession agreements, and municipal smart city contracts) is formally designated as **Non-Confirmatory Feasibility Research**.

2. `[DECISION]` **Allocation to Validation / Development:**  
   The entire `MACRO-FAM-DOE-PPD` macro-family is allocated exclusively to the **Validation / Development Partition**. It will be used strictly for candidate generator calibration, prompt tuning, parser verification, and baseline threshold sweep ($\tau_{\text{conf}}^*$).

3. `[DECISION]` **Absence of Independent Confirmatory Test Set & Superiority Prohibition:**  
   The feasibility pilot does not establish an independent confirmatory test set. Any exploratory results from other document families must identify their provenance, limitations, and potential distribution shift. No statistical superiority claim is permitted.

4. `[DECISION]` **Authorized Feasibility Objectives:**  
   The feasibility pilot is authorized exclusively to measure:
   * PDF text extraction fidelity, character-offset invariance, and bracketed placeholder preservation under Policy A (Literal Preservation).
   * Candidate finding generator yield across the seven risk archetypes.
   * Advocate review completion latency, annotation UI ergonomics, and inter-annotator agreement ($\kappa$).
   * Preliminary empirical estimation of intra-cluster correlation ($\rho$) and unassessable rates ($\text{UR}$).

---

## 4. Structural Representation of Mutually Exclusive Drafting Alternatives

1. `[DECISION]` **Single-Source Provenance:**  
   Where a model contract provides mutually exclusive drafting options within the same section (e.g., `Option A [Institutional Arbitration]` vs. `Option B [Ad-Hoc Arbitration]`), both alternatives must retain identical parent document provenance (`document_id`, `source_pdf_sha256`, publication date, and page range).

2. `[DECISION]` **Structured Variant Lineage:**  
   Drafting alternatives must be represented as distinct clause instances carrying explicit variant metadata:
   * `clause_id`: Suffix-indexed identifier (e.g., `GCC-24.2#OPT-A`, `GCC-24.2#OPT-B`).
   * `parent_section_id`: Common parent section reference (`GCC-24.2`).
   * `alternative_group_id`: Common group tag (`ALT-GCC-24.2-DISPUTE-RESOLUTION`).
   * `is_drafting_alternative`: Boolean flag set to `true`.
   * `selection_instruction`: Verbatim instructional guidance for contracting authorities.

3. `[DECISION]` **Single Active Option Configuration Invariant:**  
   In any instantiated contract configuration evaluated by the pipeline, **exactly one alternative per `alternative_group_id` may be active**. Contradictory alternatives must never be simultaneously active in the same evaluation contract instance. Both alternatives inherit the parent document's `template_family_id` and must remain co-located in the same evaluation partition.

---

## 5. Confirmatory Study Prerequisite Specification

1. `[DECISION]` **Pre-Registered Statistical Analysis Plan Mandatory:**  
   No confirmatory study, formal hypothesis testing ($H_1$), or claim of statistical superiority ($\Delta\text{UFR}_{@\text{MatchedUFC}} > 0$) may be initiated without a pre-registered statistical analysis plan formally approved by the project owner.

2. `[DECISION]` **Required Statistical Design Elements:**  
   The confirmatory statistical plan must explicitly model:
   * **Clustered Variance Structure:** Intra-cluster correlation ($\rho$), variable cluster sizes ($m_k$), and finite-sample corrections for cluster-robust standard errors.
   * **Empirical Outcome Variability:** Baseline risk finding rates and variance observed during the feasibility pilot.
   * **Annotation Sampling Plan:** Total candidate finding sample size ($N$), verified advocate dual-annotation coverage, and Senior Counsel adjudication capacity.
   * **Common Empirical Support:** Verified existence of common empirical support between baseline and evidence-aware policies without threshold extrapolation.

---

## 6. Data Governance, Existing Limitations & External Blockers Ledger

1. `[DECISION]` **Strict Non-Inference Rule:**  
   The project enforces that **public web accessibility does not constitute legal permission to download, preprocess, store, evaluate, or redistribute copyright-protected text**.

2. `[PREREQUISITE]` **Qualified Legal Review Prerequisite:**  
   Independent, qualified legal review of the applicable copyright framework under the Indian Copyright Act, 1957 (including Government copyright ownership under Section 17, fair dealing under Section 52(1)(a)(i), and the absence of a statutory Text and Data Mining exception) remains a **mandatory prerequisite** before any physical contract corpus ingestion, local storage, or multi-user server processing is authorized.

3. `[EXISTING LIMITATION]` **Preservation of Repository Limitations:**  
   * The reference statutory corpus contains exactly 40 commercial provisions across six central Acts (`data/legal_sources/corpus_manifest.json`) and does not represent comprehensive Indian commercial law.
   * The unadapted Legal-BERT weights (`nlpaueb/legal-bert-base-uncased`) possess zero domain adaptation to Indian commercial drafting and must not be represented as a validated Indian-law classifier.
   * The evaluation evaluates triage reliability over proposed candidate findings; it does not evaluate clause-level false negatives or end-to-end recall.

4. `[DECISION]` **Pre-Ingestion External Blockers Ledger:**  
   The following four external blockers remain logged and isolated, barring corpus ingestion until formally resolved:

| Blocker ID | Domain | Issue Description | Prerequisite for Resolution |
| :--- | :--- | :--- | :--- |
| **BLK-LEGAL-01** | Copyright / Statutory Law | Scope of Indian Copyright Act, 1957 (§52(1)(a)(i) vs. lack of statutory TDM exception) regarding multi-user server processing. | Qualified advocate legal review. |
| **BLK-LICENSE-02** | Sovereign Terms of Use | Official terms on `doe.gov.in` and `niti.gov.in` restrict open redistribution of full raw text without written permission. | Formal administrative clarification or internal-only research protocol sign-off. |
| **BLK-ACCESS-03** | Network / WAF | DEA portal (`https://www.pppinindia.gov.in`) returns `HTTP 403 Forbidden` to automated HTTP user-agents. | Validated manual download protocol or verified alternative mirror. |
| **BLK-PROVENANCE-04** | CMS Dynamics | NITI Aayog MCA reports are accessed via dynamic CMS endpoints rather than static immutable URLs. | Session-pinned provenance logging protocol. |

---

## 7. State Invariants & Implementation Controls

1. `[DECISION]` **Task Board State Invariants:**  
   * Task 028 remains strictly **`🔒 LOCKED`**.  
   * Task 029 remains strictly **`🔒 LOCKED`**.  
   * Task 042 remains strictly **`NOT STARTED`**.  

2. `[DECISION]` **Corpus Ingestion Prohibition:**  
   No physical contract documents may be downloaded, scraped, preprocessed, or committed to the repository until Blockers BLK-LEGAL-01 through BLK-PROVENANCE-04 are formally cleared and Task 042 is explicitly authorized by the project owner.

3. `[DECISION]` **Document Lineage Preservation:**  
   Original research records [`docs/research_decision_record_v1.md`](file:///c:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/docs/research_decision_record_v1.md) and preceding audit logs remain immutable historical records and are preserved without modification.
