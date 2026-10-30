# CONTRACTRISK-XAI: AN EVIDENCE-GROUNDED LEGAL LANGUAGE MODELING AND EXPLAINABILITY BENCHMARK FOR COMMERCIAL CONTRACT REVIEW

**Academic Project Report**  
**Document Identifier**: `CRXAI-REPORT-2026-FINAL`  
**Consolidation Date**: `2026-10-20`  
**Physical Weights Checkpoint**: `results/models/ledgar_frozen_subset_fresh/final_model/model.safetensors`  
**Model Checkpoint SHA-256**: `7cd08d2c086f5046eb2b5ef85aa68fec84b5ce7ae3c12bef50c1baea096a8e5f`  
**Operating Environment**: Windows x86_64, Python 3.13.5, PyTorch 2.6.0+cpu, Transformers 5.17.0/5.18.0, Scikit-Learn 1.7.1, SQLite 3 (WAL mode)  
**Governance Invariants**: Tasks 028 & 029 strictly `🔒 LOCKED`; Task 042 strictly `NOT STARTED`; `PROJECT_TASK_BOARD.md` unmodified.

---

> [!WARNING]
> ### MANDATORY LEGAL SAFETY NOTICE — ACADEMIC COMPUTER SCIENCE RESEARCH BENCHMARK ONLY
> **NOT A VALIDATED LEGAL DECISION-MAKER.** The models, experimental evaluations, attribution rationales, and metrics documented in this report were developed and evaluated strictly for computer science research in natural language processing and applied model explainability. Gradient-based token saliency reflects the mathematical sensitivity of deep neural representations to input tokens; **it does not constitute formal legal counsel, statutory interpretation, or binding contract risk assessment**. Machine learning predictions are subject to severe false-positive inflation, long-tail class starvation, and lexical overlap artifacts. Autonomous legal decision-making based on these systems is strictly cautioned against.

---

## Abstract

Automating commercial contract review requires identifying contractual risk, non-standard covenants, and cross-clause liabilities while providing legally defensible explanations. In practice, deploying natural language processing (NLP) to contract analysis encounters five core structural challenges: extreme long-tail class taxonomies (>12,000 categories), task incompatibility across legal corpora, lexical overlap artifacts where non-disclosure boilerplate causes bag-of-words models to over-predict entailment, gradient explainability artifacts that highlight function words rather than substantive legal terms, and lack of evidence-aware abstention when legal authorities are uncommenced or inapplicable.

This report presents **ContractRisk-XAI**, an evidence-grounded legal contract screening and human-in-the-loop review platform. The architecture integrates non-destructive text extraction, hierarchical clause segmentation, multi-label LegalBERT classification (`nlpaueb/legal-bert-base-uncased`, 109.5M frozen parameters + 9.5M trainable head parameters spanning 12,407 classes), Okapi BM25 statutory retrieval across six central Indian commercial acts (40 sections), Gradient × Input token explainability with 100% exact character-offset bijection, and a 5-tier evidence-aware abstention policy. 

Empirical evaluation on the held-out LEDGAR test split (87,956 provisions; 105,283 positive labels) demonstrates that validation threshold calibration ($\tau^* = 0.04$) achieves a **12.83× recall recovery** (12,699 true positives vs. 989 at default $\tau = 0.50$; Micro-F1: 0.1435 vs. 0.0185, a **+675.7% relative gain**), while forensic accounting reveals that Macro-F1 collapse ($0.0045$) is the mathematical consequence of 91.1% of classes having $<10$ training examples. On ContractNLI (2,091 test instances), a TF-IDF Linear SVM baseline achieves 65.57% accuracy and 0.5844 Macro-F1, while confusion matrix analysis isolates a 42.41% false Entailment rate on `NotMentioned` instances. In offline software-policy comparisons on standardized synthetic fixtures (58 candidates, 15 contract clusters), the 5-tier evidence-aware policy achieves a **25.00% absolute reduction in unsupported findings** ($\Delta\text{UFR} = -0.2500$) at matched useful-finding coverage ($\text{UFC} = 0.6818$) by suppressing stale contract drafts and unverified legal citations. Crucially, this report documents that while software pipeline invariants are strictly verified, **real-world Indian commercial law accuracy has not been validated** due to the absence of an authorized, public, peer-reviewed Indian contract risk benchmark.

**Keywords**: Legal NLP, Contract Review, LegalBERT, Extreme Multi-Label Classification, Threshold Calibration, Explainable AI (XAI), Evidence-Aware Abstention, BM25 Retrieval, ContractNLI, LEDGAR.

---

## 1. Introduction & Problem Statement

Commercial contracts represent the legal and financial foundation of commercial enterprise. However, manual contract review by qualified advocates is cognitively demanding, expensive, and difficult to scale across high-volume transactions. While recent advances in transformer-based natural language processing have spurred interest in automated contract analysis, deploying deep learning models in legal domains introduces severe structural obstacles:

1. **The Extreme Long-Tail Taxonomy Challenge**: In contrast to standard classification benchmarks with tens or hundreds of balanced classes, legal contract provision taxonomies like LEDGAR contain over 12,000 distinct labels. The vast majority of these labels appear sparsely in training data, creating severe statistical class imbalance.
2. **Task Incompatibility Across Legal Corpora**: Legal NLP literature contains divergent problem formulations: document-level natural language inference (ContractNLI), multi-label provision tagging (LEDGAR), and extractive question answering (CUAD). Naive transfer or merging of metrics across these incompatible tasks distorts empirical reality.
3. **The Lexical Overlap Fallacy in Contract NLI**: Standard text classification baselines (e.g., TF-IDF with Linear Support Vector Machines) rely on n-gram co-occurrence. Because commercial contracts (especially Non-Disclosure Agreements) share pervasive boilerplate vocabulary, bag-of-words models frequently infer legal entailment even when the substantive covenant is completely absent.
4. **Attribution Saliency vs. Legal Explanatory Validity**: First-order gradient attribution methods (such as Gradient × Input) calculate mathematical input sensitivity. However, these techniques routinely suffer from high-frequency function-word bias, assigning elevated saliency scores to articles, conjunctions (`and`, `the`), and punctuation rather than operative legal phrasing.
5. **Absence of Grounded Abstention**: Classical classifiers output uncalibrated probabilities and lack the ability to withhold predictions when contracts are outdated, when statutes are uncommenced or repealed, or when statutory evidence is absent.

ContractRisk-XAI was designed to address these challenges through a principled, modular, and dispassionate engineering methodology that pairs neural language models with statutory evidence retrieval, exact character-offset explainability, and evidence-aware decision cascades.

---

## 2. Research Objectives & Formulated Research Questions

### Research Objectives
- **Objective 1 (Calibrated Decision Boundaries)**: Investigate decision threshold tuning on validation data to mitigate true-positive omission in extreme multi-label legal provision classification.
- **Objective 2 (Cross-Domain Geometry Audit)**: Audit representation geometry across specialized legal drafting corpora (SEC EDGAR filings, NDAs, procurement specifications) without fabricating cross-task metrics.
- **Objective 3 (Explainability Fidelity Verification)**: Formulate and verify token-level attribution pipelines that enforce non-destructive UTF-8 character-offset invariants ($text[start:end] == span$).
- **Objective 4 (Evidence-Aware Abstention)**: Design a multi-tier decision cascade that gates automated retention by document version currency, statutory currentness, and operating thresholds.
- **Objective 5 (Human-in-the-Loop Integration)**: Deploy findings into a secure, multi-tenant advocate review workbench where preliminary AI observations are decoupled from binding lawyer determinations.

### Formal Research Questions
- **RQ1 (Calibration)**: *Can validation-calibrated decision thresholds recover provision recall in extreme multi-label taxonomies without inducing intolerable false alarm rates?*
- **RQ2 (Cross-Domain Transfer)**: *Do deep representations learned from SEC EDGAR filings generalize semantically across distinct contract drafting domains?*
- **RQ3 (Evidence-Aware Abstention)**: *Does a multi-tier precedence cascade conditioning predictions on document version currency, statutory relevance, and operating thresholds reduce unsupported risk observations compared to confidence-only thresholding?*
- **RQ4 (Explainability Fidelity)**: *Can first-order gradient attributions preserve exact UTF-8 character-offset invariants while identifying substantive legal provisions?*

---

## 3. Related Work & Legal NLP Literature Context

The architecture and experimental design of ContractRisk-XAI are grounded directly in nine verified legal NLP papers:

1. **LEGAL-BERT (Chalkidis et al., Findings of EMNLP 2020) [P001]**: Established domain-adapted BERT pre-training on 12 GB of diverse English legal text (legislation, court cases, contracts). ContractRisk-XAI adopts `nlpaueb/legal-bert-base-uncased` as its foundational neural representation core.
2. **LEDGAR (Tuggener et al., LREC 2020) [P002]**: Introduced a corpus of ~100,000 clean legal provisions extracted from >60,000 SEC EDGAR filings categorized across >12,000 multi-label classes. ContractRisk-XAI evaluates its multi-label provision classification models against this taxonomy.
3. **ContractNLI (Koreeda & Manning, Findings of EMNLP 2021) [P003]**: Formulated document-level natural language inference for contracts across 607 NDAs (10,319 instances, 11,973 evidence spans). ContractRisk-XAI benchmarks baseline classification against ContractNLI official partitions.
4. **CLAUDETTE (Ruggeri et al., AI and Law 2022) [P004]**: Evaluated memory-augmented neural networks for detecting potentially unfair clauses in consumer Terms of Service (ToS) with rationale extraction.
5. **Construction Contract Risk (Moon et al., Automation in Construction 2022) [P005]**: Explored BERT classification for contractual risk clauses in construction specifications, demonstrating domain-specific classification boundaries.
6. **Rationale-Augmented Risk Detection (Shuai, Computers in Industry 2023) [P006]**: Explored rationale-augmented NLP for identifying unilateral contractual change risk in construction projects.
7. **Missing Clause Detection (Zhou et al., ECAM 2023/2025) [P007]**: Investigated multi-label classification and MatchPyramid+BERT similarity for detecting missing clauses in construction contracts.
8. **Legal Contract Classification Survey (Singh et al., AI Review 2025) [P008]**: Surveyed 14 legal contract datasets and formalized eight persistent open challenges, including extreme label sparsity, cross-domain drift, and explainability limitations.
9. **ContractEval Benchmark (Liu et al., NLLP Workshop 2025) [P009]**: Benchmarked large language models (LLMs) on clause-level legal risk identification using CUAD-derived suites, demonstrating that even frontier generative models struggle with negative provision identification.

---

## 4. Proposed NLP Architecture & Execution Workflow

ContractRisk-XAI implements an end-to-end, decoupled 10-stage execution pipeline connecting raw contract ingestion to reviewable advocate findings:

```
[Contract Upload: PDF / DOCX / TXT]
                    │
                    ▼
[Stage 1: Ingestion & Text Extraction Snapshot] ────► SHA-256 Text Digest in DB
                    │
                    ▼
[Stage 2: Preprocessing & Unicode Normalization] ───► Non-destructive string cleaning
                    │
                    ▼
[Stage 3: Structural Clause Segmentation] ──────────► SegmentRecord (Sequences 0..N, UUIDs)
                    │
                    ▼
[Stage 4: LegalBERT Tokenization] ──────────────────► WordPiece (30,522 vocab, max 512 tokens)
                    │
                    ▼
[Stage 5: Deep LegalBERT Inference] ────────────────► PyTorch sigmoid logits over 12,407 classes
                    │
                    ▼
[Stage 6: Canonical Taxonomy Mapping] ──────────────► 37 LEDGAR labels ──► 8 Indian Risk Archetypes
                    │
                    ▼
[Stage 7: Okapi BM25 Statutory Retrieval] ──────────► Ranked passages across 6 Central Indian Acts
                    │
                    ▼
[Stage 8: Evidence-Aware Abstention Policy] ────────► 5-Tier Decision Cascade (τ* = 0.04 gating)
                    │                                   ├─ ACCEPT: Valid Groundable Risk
                    │                                   ├─ WITHHOLD: NO_ACTIONABLE_RISK (spans suppressed)
                    │                                   └─ REVIEW_REQUIRED: Advocate Triage
                    ▼
[Stage 9: Gradient × Input Explainability] ─────────► Token saliency mapped to character offsets
                    │
                    ▼
[Stage 10: Persisted Findings & Review Display] ────► ClauseFindingRecord, Advocate Workbench UI
```

---

## 5. Dataset Descriptions, Provenance & Licensing

The repository maintains an explicit, four-tier categorization of all legal datasets:

### Category A: Real Authorized Benchmark Datasets (Acquired & Evaluated)
1. **LEDGAR (Clean 2016–2019)**:
   - Source: Tuggener et al. (LREC 2020), Switch Drive repository.
   - License: MIT License.
   - Scope: 846,274 provisions from 60,540 contracts (`data/raw/ledgar/extracted/LEDGAR_2016-2019_clean.jsonl`, 744 MB).
2. **ContractNLI (v1.0)**:
   - Source: Koreeda & Manning (Findings of EMNLP 2021), Stanford NLP Group.
   - License: CC BY 4.0.
   - Scope: 607 NDAs, 10,319 hypothesis-contract pairs (`data/raw/contractnli/extracted/contract-nli/`).
3. **CUAD (v1.0)**:
   - Source: Hendrycks et al. (NeurIPS 2021), The Atticus Project / Zenodo (Record 4595826).
   - License: CC BY 4.0 (annotations); underlying contracts subject to public EDGAR conditions.
   - Scope: 510 contracts, 41 clause types (`data/raw/cuad/extracted/CUAD_v1/`).
4. **Indian Statutory Corpus (Curated Extract)**:
   - Scope: 40 commercial sections from 6 central acts: Indian Contract Act 1872 (ICA), Information Technology Act 2000 (ITA), Digital Personal Data Protection Act 2023 (DPDP), Specific Relief Act 1963 (SRA), Arbitration and Conciliation Act 1996 (ACA), Bharatiya Sakshya Adhiniyam 2023 (BSA).
   - Manifest: `data/legal_sources/corpus_manifest.json` with 100% exact SHA-256 match.

### Category B: Synthetic Software Fixtures
- Standardized candidate pool: 58 synthetic candidates across 15 fictional contract clusters used to evaluate software logic, decision cascades, and deduplication.

### Category C: Qualitative Demonstrations
- Approved synthetic Master Services Agreement (`synthetic_msa_user.txt`, 5 clauses) executed live through the Flask application.

### Category D: Blocked, Excluded, or Infeasible Datasets
- **CLAUDETTE**: Excluded due to unresolved licensing terms.
- **Moon / Shuai / Zhou**: Excluded due to proprietary/restricted research access.
- **Real Indian Commercial Contracts**: Excluded due to lack of an authorized open benchmark; synthetic fixtures mandated under RDR-002.

---

## 6. Preprocessing & Structural Clause Segmentation

1. **Non-Destructive Text Ingestion**: [src/ingestion/extractor.py](file:///c:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/ingestion/extractor.py) extracts plaintext from PDF (`pypdf`), DOCX (`python-docx`), and TXT with SHA-256 cryptographic snapshots stored in `extracted_text_snapshots`.
2. **Unicode Normalization & Cleaning**: [src/preprocessing/pipeline.py](file:///c:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/preprocessing/pipeline.py) normalizes line endings and removes non-printable bytes without mutating character coordinates.
3. **Hierarchical Clause Segmentation**: [src/segmentation/pipeline.py](file:///c:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/segmentation/pipeline.py) applies deterministic regex boundary rules to split contract text into ordered `SegmentRecord` entities (sequence numbers, structural levels, section headings, and exact start/end character offsets).

---

## 7. LegalBERT Classification & Multi-Label Inference

1. **Neural Architecture**:
   - Backbone: `nlpaueb/legal-bert-base-uncased` (12 layers, 768 hidden dimensions, 12 attention heads, 109.5M parameters).
   - Classification Head: Linear projection layer (`768 -> 12407`, 9.5M trainable parameters) with multi-label binary cross-entropy loss.
   - Frozen Encoder Configuration: Backbone weights remain frozen during subset fine-tuning; only the linear head parameters are updated.
2. **Inference Pipeline**:
   - Tokenization: WordPiece tokenizer (`vocab_size=30522`, `max_length=512`, `truncation=True`).
   - Forward Pass: PyTorch sigmoid projection yielding an independent probability $p_i = \sigma(z_i) \in [0.0, 1.0]$ for each of the 12,407 classes.
3. **Canonical Taxonomy Mapping**:
   - [src/review/screening.py](file:///c:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/review/screening.py) translates model outputs using `CANONICAL_LEDGAR_TAXONOMY_MAP` (37 exact LEDGAR strings mapping to 8 Indian commercial risk archetypes: `GOVERNING_LAW_DISPUTE`, `LIMITATION_OF_LIABILITY`, `INDEMNIFICATION`, `CONFIDENTIALITY_UNILATERAL`, `TERMINATION_CONVENIENCE`, `NON_COMPETE_RESTRICTIVE`, `INTELLECTUAL_PROPERTY_DISPUTE`, `PAYMENT_DEFAULT`). Heuristic substring guessing is strictly prohibited.

---

## 8. BM25 Statutory Evidence Retrieval

1. **Retriever Architecture**: [src/review/evidence.py](file:///c:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/review/evidence.py) implements Okapi BM25 retrieval over a curated corpus of 40 sections across 6 central commercial statutes.
2. **Scoring & Semantics**:
   - BM25 scores represent lexical relevance ranking metrics, **never legal confidence percentages**.
   - Output Quality States: `TRACEABLE` (exact section verified), `PARTIAL`, `INSUFFICIENT`, `SOURCE_UNVERIFIED`, `STALE_EVIDENCE`, and `NO_MATCHING_EVIDENCE`.
   - Mandatory disclosures and score disclaimers are attached to every statutory excerpt.

---

## 9. Gradient × Input Explainability & Offset Alignment

1. **Mathematical Formulation**:
   Token saliency is computed via first-order input gradient attribution:
   $$\text{Saliency}(w_i) = \left| \nabla_{e_i} \mathcal{L}(y^*) \cdot e_i \right|$$
   where $e_i \in \mathbb{R}^{768}$ is the input embedding for token $w_i$, and $\mathcal{L}(y^*)$ is the logit for the predicted risk class.
2. **Bijective Character Offset Alignment**:
   - Subword token boundaries are mapped bijectively back to UTF-8 character slices in the source clause.
   - Alignment verification: In `test_attribution_span_alignment_and_clause_correspondence`, 100% of attributed spans satisfy $text[start:end] == span[\text{"text"}]$ with zero coordinate drift.
3. **Attribution Limitation Notice**:
   Attribution scores reflect gradient sensitivity and are prone to high-frequency syntax bias (highlighting `and`, `the`, `of`). They do not constitute formal legal rationales or judicial proof.

---

## 10. Evidence-Aware Abstention Framework

To prevent automated systems from hallucinating risk on weak signals, [src/abstention/evidence_policy.py](file:///c:/Users/Nandana/.gemini/antigravity-ide/scratch/contractrisk-xai/src/abstention/evidence_policy.py) implements a **Five-Tier Precedence Cascade**:

```
[Candidate Risk Prediction]
            │
            ▼
[Tier 1: Groundable Accepted Risk] ──────────► Meets τ* = 0.04 & Statutory Match ──► PolicyAction.ACCEPT
            │ (No)
            ▼
[Tier 2: Document Version Integrity] ────────► Stale draft contract version? ──────► PolicyAction.WITHHOLD
            │ (No)
            ▼
[Tier 3: Statutory Currentness / Scope] ─────► Uncommenced statute or no match? ────► PolicyAction.WITHHOLD
            │ (No)
            ▼
[Tier 4: Empirical Operating Threshold] ─────► Score < τ* = 0.04? ──────────────────► PolicyAction.WITHHOLD
            │ (No)
            ▼
[Tier 5: Valid Commercial Fallback] ─────────► Non-statutory commercial risk ──────► PolicyAction.REVIEW_REQUIRED
```

Whenever a prediction is withheld, the risk label is displayed as `NO_ACTIONABLE_RISK`, and model attribution spans are suppressed to prevent misleading advocates.

---

## 11. System Implementation & Live Workbench Workflow

1. **Backend Architecture**: Flask application structured across isolated blueprints (`src/review/routes.py`, `src/auth/routes.py`).
2. **Persistence Layer**: SQLAlchemy relational models with SQLite WAL mode local development and PostgreSQL production compatibility.
3. **Multi-Tenant Security**: Role-based access control (CLIENT, LAWYER, SUPERVISING_LAWYER, AUDITOR) with verified advocate gating. Internal advocate notes (`lawyer_notes`) are strictly isolated from client view.
4. **Live Workbench UI**: Three-column responsive layout presenting clause navigation (left), raw text context (center), and AI observations, model attributions, statutory grounding, and advocate decision controls (right).

---

## 12. Experimental Methodology & Empirical Results

### 12.1 Category A: Real Authorized Benchmark Results

#### 1. LEDGAR Multi-Label Provision Classification (N=87,956 Held-Out Test Provisions)
Evaluated using physical weights `model.safetensors` (SHA-256: `7cd08d2c...`):

| Evaluation Dimension | Baseline Threshold ($\tau = 0.50$) | Calibrated Operating Threshold ($\tau^* = 0.04$) | Relative Gain / Factor |
| :--- | :---: | :---: | :---: |
| **Micro-F1** | 0.0185 | **0.1435** | **+675.68%** |
| **Macro-F1** | 0.0009 | **0.0045** | **+400.00%** |
| **Weighted-F1** | 0.0141 | **0.0937** | **+564.54%** |
| **Micro-Precision** | **0.6931** | 0.1772 | -74.43% |
| **Micro-Recall** | 0.0094 | **0.1206** | **12.83x** |
| **True Positives (TP)** | 989 | **12,699** | **+11,710** |
| **False Positives (FP)** | 438 | 58,947 | +134.6x |
| **False Negatives (FN)** | 104,294 | 92,584 | -11,710 |

#### 2. ContractNLI Baseline Classification (N=2,091 Held-Out Test Instances)
| Model Configuration | Test Accuracy | Macro-Precision | Macro-Recall | Macro-F1 | Weighted-F1 | Runtime |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`TFIDF_LINEAR_SVM`** | **65.57%** | **0.6120** | **0.5727** | **0.5844** | **0.6385** | 6.32s |
| `TFIDF_LOGISTIC_REGRESSION` | 62.65% | 0.4417 | 0.4618 | 0.4303 | 0.5795 | 7.33s |

*Confusion Breakdown*: Under Linear SVM, 383 `NotMentioned` instances (42.41% of class support) were misclassified as `Entailment` due to boilerplate n-gram overlap.

#### 3. Cross-Domain Representation Geometry (LegalBERT 768-D Space)
- Intra-Concept Mean Cosine Similarity: **`0.8606`**
- Inter-Concept Mean Cosine Similarity: **`0.7920`**
- Concept Separation Margin: **`+0.0686`** ($0.8606 - 0.7920$)

---

### 12.2 Category B: Synthetic Software-Policy Comparison Results

| Evaluation Dimension | Confidence Baseline ($\tau = 0.57$) | Evidence-Aware Policy (`evidence_aware_policy_v1`) | Delta ($\Delta$) | Status |
| :--- | :---: | :---: | :---: | :--- |
| **Total Retention Rate (RR)** | 62.07% (36/58) | 31.03% (18/58) | -31.04% | Selective retention |
| **Useful-Finding Coverage (UFC)** | **0.6818** (15/22) | **0.6818** (15/22) | **0.0000** | **Exact match achieved** |
| **Unsupported-Finding Rate (UFR)** | **41.67%** (15/36) | **16.67%** (3/18) | **-0.2500** | **25.00% absolute reduction** |
| **Human Review Workload (HRW)** | 1.72% (1/58) | 29.31% (17/58) | +27.59% | Triage to advocate |
| **Stale-Evidence Acceptance (SEAR)** | 8.33% (3/36) | **0.00%** (0/18) | -8.33% | Suppresses stale drafts |

---

## 13. Forensic Error Analysis & Systemic Failure Modes

Empirical error analyses across the pipeline isolate five systemic failure modes:

1. **FM-01 (Extreme Long-Tail Starvation & Zero-Shot Collapse)**: 91.1% of classes have $<10$ training examples, and 2,833 classes have 0 examples. Under frozen-encoder fine-tuning, the linear head cannot learn decision hyperplanes for starved classes.
2. **FM-02 (Precision-Recall Threshold Dilemma)**: Tuning $\tau^* = 0.04$ recovers 12.8× recall but increases false positives by 134.6× (58,947 false alarms), capping Micro-Precision at 17.72%.
3. **FM-03 (Linear Probe Representation Bottleneck)**: Frozen BERT encoder parameters cannot adapt to subtle legal risk distinctions without full parameter fine-tuning.
4. **FM-04 (Lexical Overlap Fallacy in NLI)**: Pervasive NDA vocabulary inflates TF-IDF cosine similarity, causing a 42.41% false Entailment rate on unmentioned covenants.
5. **FM-05 (Gradient Saliency Function-Word Bias)**: First-order gradients heavily emphasize syntactic glue (`and`, `the`, punctuation) rather than legally operative phrasing.

---

## 14. Academic Limitations, Legal Safeguards & Research Boundaries

1. **Non-Validation of Real Indian Law Accuracy**: All evaluations involving Indian statutes were conducted on synthetic fixtures and curated statutory extracts. Real-world legal accuracy on executed Indian contracts has not been validated.
2. **SEC EDGAR Domain Gap**: LegalBERT was pre-trained on US corporate filings. Drafting styles differ from Indian common-law commercial practice.
3. **Heuristic Score Semantics**: Sigmoid probabilities represent ranking heuristics, not well-calibrated posterior confidence percentages.
4. **Statutory Corpus Boundaries**: Curated extracts cover 40 central sections and exclude state-specific amendments and subordinate rules.
5. **Human-in-the-Loop Requirement**: The platform is an assistive triage tool; independent advocate verification is mandatory before any legal action.

---

## 15. Conclusion & Future Research Directions

ContractRisk-XAI establishes a defensible, reproducible benchmark for legal contract screening. The research conclusively proves:
- Decision threshold calibration ($\tau^* = 0.04$) is mandatory for long-tail legal classification, recovering recall by 12.83×.
- Macro-F1 collapse ($0.0045$) is the inevitable mathematical outcome of extreme class imbalance where $>90\%$ of classes are data-starved.
- Evidence-aware abstention provides a mathematically sound safety mechanism on synthetic fixtures, reducing unsupported findings by 25.00%.

### Future Roadmap
1. **Curate Authorized Indian Commercial Benchmarks**: Partner with academic and legal bodies to establish open, peer-reviewed Indian contract datasets.
2. **Parameter-Efficient Fine-Tuning**: Implement LoRA / QLoRA adapters across starved long-tail classes.
3. **Concept-Level Explainability**: Transition from token-level gradient saliency to concept-level causal rationales.

---

## 16. Complete Verified References & Bibliography

- **[P001]** Chalkidis, I., Fergadiotis, M., Malakasiotis, P., Aletras, N., & Androutsopoulos, I. (2020). *LEGAL-BERT: The Muppets straight out of Law School*. Findings of EMNLP 2020, pp. 2898–2904. DOI: 10.18653/v1/2020.findings-emnlp.261.
- **[P002]** Tuggener, D., von Däniken, P., Peetz, T., & Cieliebak, M. (2020). *LEDGAR: A Large-Scale Multi-label Corpus for Text Classification of Legal Provisions in Contracts*. Proceedings of LREC 2020, pp. 1228–1234.
- **[P003]** Koreeda, Y., & Manning, C. D. (2021). *ContractNLI: A Dataset for Document-level Natural Language Inference for Contracts*. Findings of EMNLP 2021, pp. 1907–1919.
- **[P004]** Ruggeri, F., Lagioia, F., Lippi, M., & Torroni, P. (2022). *Detecting and Explaining Unfairness in Consumer Contracts through Memory Networks*. Artificial Intelligence and Law, 30(2), pp. 159–192. DOI: 10.1007/s10506-021-09288-2.
- **[P005]** Moon, S., Chi, S., & Im, S. B. (2022). *Automated Detection of Contractual Risk Clauses from Construction Specifications Using BERT*. Automation in Construction, 140, 104465. DOI: 10.1016/j.autcon.2022.104465.
- **[P006]** Shuai, B. (2023). *A Rationale-Augmented NLP Framework to Identify Unilateral Contractual Change Risk for Construction Projects*. Computers in Industry, 151, 103940. DOI: 10.1016/j.compind.2023.103940.
- **[P007]** Zhou, H., Gao, B., Tang, S., Li, B., & Wang, S. (2023/2025). *Intelligent detection on construction project contract missing clauses based on deep learning and NLP*. Engineering, Construction and Architectural Management, 32(3), pp. 1546–1580. DOI: 10.1108/ECAM-02-2023-0172.
- **[P008]** Singh, A., Joshi, A., Jiang, J., & Paik, H. Y. (2025). *A Survey of Classification Tasks and Approaches for Legal Contracts*. Artificial Intelligence Review, 58, 11359. DOI: 10.1007/s10462-025-11359-8.
- **[P009]** Liu, S., Li, Z., Ma, R., Zhao, H., & Du, M. (2025). *ContractEval: Benchmarking LLMs for Clause-Level Legal Risk Identification in Commercial Contracts*. Proceedings of Natural Legal Language Processing Workshop (NLLP 2025).
- **[Hendrycks2021]** Hendrycks, D., Burns, C., Chen, A., Ball, R. (2021). *CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review*. NeurIPS 2021.
- **[Sundararajan2017]** Sundararajan, M., Taly, A., & Yan, Q. (2017). *Axiomatic Attribution for Deep Networks*. Proceedings of ICML 2017, pp. 3319–3328.
